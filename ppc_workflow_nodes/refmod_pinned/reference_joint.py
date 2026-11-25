"""Joint ordinary-media + author-native RefMod conditioning, without old prompts.

Ordinary preparation follows frozen ComfyUI fd734e9 nodes_minimax_h3.py.
RefMod reconstruction follows author 517e8c4 prompt.py. This module is an
integration adapter, not a preinstalled RH node and not a model-capacity claim.
No file, network, credentials, global configuration or model is loaded at import.
"""
from __future__ import annotations

import math
import re


def _integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(name + ' must be an integer >= ' + str(minimum))
    return value


def _slots(value, prefix, count):
    if value is None:
        return {}
    if type(value) is not dict:
        raise ValueError(prefix + ' inputs must be the numbered dictionary')
    allowed = {prefix + str(i) for i in range(1, count + 1)}
    if set(value) - allowed:
        raise ValueError('Unknown or over-capacity ordinary slot: ' + prefix)
    # Stable numeric ordering, independent of API object insertion order.
    return {prefix + str(i): value[prefix + str(i)] for i in range(1, count + 1)
            if value.get(prefix + str(i)) is not None}


def _visual(value, name, image=False):
    shape = tuple(getattr(value, 'shape', ()))
    if len(shape) != 4 or shape[-1] != 3 or min(shape) < 1 or (image and shape[0] != 1):
        raise ValueError(name + ' requires RGB [frames,height,width,3]; an image slot is exactly one image')
    return shape


def frames_at_24fps(frames, source_fps):
    """Ordinary nearest-frame temporal sampling; no AI frames or motion claim."""
    _visual(frames, 'ordinary video')
    if type(source_fps) not in (int, float) or not math.isfinite(source_fps) or not 1 <= source_fps <= 240:
        raise ValueError('Explicit real source video FPS in1..240 is required')
    duration = frames.shape[0] / source_fps
    if not 2 <= duration <= 15:
        raise ValueError('Ordinary reference video duration must be2..15seconds')
    count = max(1, round(duration * 24))
    indices = [min(round(i * source_fps / 24), frames.shape[0] - 1) for i in range(count)]
    return frames[indices]


def _audio_seconds(audio):
    if type(audio) is not dict or type(audio.get('sample_rate')) is not int or audio['sample_rate'] <= 0:
        raise ValueError('Native AUDIO requires a positive integer sample_rate')
    shape = tuple(getattr(audio.get('waveform'), 'shape', ()))
    if len(shape) != 3 or shape[0] != 1 or shape[1] not in (1, 2) or shape[-1] < 1:
        raise ValueError('Native AUDIO requires one actual [1,channels,samples] waveform')
    duration = shape[-1] / audio['sample_rate']
    if not 2 <= duration <= 15:
        raise ValueError('Each ordinary audio reference must be2..15seconds')
    return duration


def _runtime():
    from comfy_extras import nodes_minimax_h3 as native
    from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
    def validate_video_vae(vae):
        if not isinstance(getattr(vae, 'first_stage_model', None), MiniMaxH3VideoVAE):
            raise ValueError('Visual references require the native MiniMax H3 video VAE')
    audio = getattr(native, '_encode_ref_audio', None)
    if audio is None:
        # Older installed native schema has the same helper as a class method.
        audio = native.MiniMaxH3ReferenceToVideo._encode_ref_audio
    return {'empty': native._empty_av_latent, 'resize': native._resize,
            'canvas': native.adapt_canvas, 'audio': audio, 'validate_vae': validate_video_vae}


def block_tokens(block):
    """Actual PackedLayout rows, including a video's attached soundtrack."""
    kind = block.get('kind')
    if kind not in ('image', 'video', 'video_audio', 'audio'):
        raise ValueError('Unsupported native ref kind')
    total = 0
    if kind != 'audio':
        z = block.get('latent')
        shape = tuple(getattr(z, 'shape', ()))
        h = _integer(block.get('latent_h'), 'latent_h')
        w = _integer(block.get('latent_w'), 'latent_w')
        t = 1 if kind == 'image' else _integer(block.get('latent_t'), 'latent_t')
        if h % 2 or w % 2 or shape != (1, 24, t, h, w):
            raise ValueError('Visual ref metadata must match actual [1,24,T,H,W], with even H/W')
        total += t * (h // 2) * (w // 2)
    if kind in ('audio', 'video', 'video_audio'):
        rt = _integer(block.get('ref_audio_t'), 'ref_audio_t', 0)
        az = block.get('audio_latent')
        if rt and tuple(getattr(az, 'shape', ())) != (1, 32, 2, rt):
            raise ValueError('Audio ref metadata must match actual [1,32,2,T]')
        if kind == 'audio' and rt == 0:
            raise ValueError('Empty standalone audio ref')
        if kind == 'video_audio' and rt == 0:
            raise ValueError('video_audio must have an audio latent')
        total += 2 * rt
    return total


def _target_tokens(latent):
    tensors = getattr(latent.get('samples'), 'tensors', None)
    if tensors is None or len(tensors) != 2:
        raise ValueError('Expected native H3 video/audio NestedTensor pair')
    video, audio = tensors
    if len(video.shape) != 5 or tuple(video.shape[:2]) != (1, 24) or len(audio.shape) != 4 or tuple(audio.shape[:3]) != (1, 32, 2):
        raise ValueError('Native AV latent shape mismatch')
    h, w = video.shape[-2:]
    if h % 2 or w % 2:
        raise ValueError('Target latent spatial shape must be even')
    return video.shape[2] * (h // 2) * (w // 2) + 2 * audio.shape[-1]


def encode_generation(clip, vae, audio_vae, prompt, width, height, length,
                      ref_image_size='match', ref_images=None, ref_videos=None,
                      ref_video_audios=None, ref_audios=None, *, max_ref_tokens,
                      max_packed_tokens, use_refmod=False, ref_video_fps=None,
                      asset_loader=None, strength=1.0, reference_fps=24.0,
                      runtime=None, asset_specs=None):
    """Return (positive CONDITIONING, native LATENT, reference-map/budget dict).

    `asset_loader` is a trusted no-argument closure over the asset-core's exact
    authorized immutable file. It is never inspected/called when use_refmod=False.
    Token budgets are mandatory trusted-server inputs; no guessed default or
    disabled limit. A configured budget is not a model/RH capacity promise.
    Caller must complete tenant/file authorization and media duration validation.
    Native reference videos retain the official output-length prefix and 17n+5
    alignment. No text, reference latent or prompt is truncated to meet budgets.
    """
    specs = [] if asset_specs is None else asset_specs
    asset_count = len(specs) if asset_specs is not None else int(use_refmod)
    if type(use_refmod) is not bool or type(prompt) is not str:
        raise ValueError('Explicit Boolean use_refmod and string prompt required')
    for name, value in (('width', width), ('height', height), ('length', length),
                        ('max_ref_tokens', max_ref_tokens), ('max_packed_tokens', max_packed_tokens)):
        _integer(value, name)
    if width % 32 or height % 32 or length < 5 or ref_image_size not in ('match', 'max'):
        raise ValueError('Native H3 geometry/ref_image_size contract')
    images = _slots(ref_images, 'ref_image_', 9)
    videos = _slots(ref_videos, 'ref_video_', 3)
    tracks = _slots(ref_video_audios, 'ref_video_audio_', 3)
    audios = _slots(ref_audios, 'ref_audio_', 3)
    if any('ref_video_' + key.rsplit('_', 1)[-1] not in videos for key in tracks):
        raise ValueError('A video soundtrack requires its same-numbered video slot')
    for name, value in images.items():
        _visual(value, name, True)
    for name, value in videos.items():
        _visual(value, name)
    # The chosen eight-photo author stack is ONE video-kind ref, not eight
    # free extra image references. Video soundtracks consume audio allowance.
    expected_counts = {'image': len(images), 'video': len(videos) + asset_count,
                       'audio': len(audios) + len(tracks)}
    selected_files = len(images) + len(videos) + len(audios) + asset_count
    if expected_counts['image'] > 9 or expected_counts['video'] > 3 or expected_counts['audio'] > 3 or selected_files > 12:
        raise ValueError('Combined native contract exceeded: image<=9/video<=3/audio<=3/mixed<=12 including RefMod and soundtracks')
    if videos and (type(ref_video_fps) is not dict or set(ref_video_fps) != set(videos)):
        raise ValueError('Every ordinary video needs its exact source FPS by ref_video_N key')
    if use_refmod and (not callable(asset_loader) or type(strength) not in (int, float) or not math.isfinite(strength) or not 0 < strength <= 1):
        raise ValueError('Selected RefMod needs an authorized loader and finite strength in (0,1]')
    video_seconds = 0.0
    for name, frames in videos.items():
        fps = ref_video_fps[name]
        if type(fps) not in (int, float) or not math.isfinite(fps) or not 1 <= fps <= 240:
            raise ValueError('Explicit real source video FPS in1..240 is required')
        duration = frames.shape[0] / fps
        if not 2 <= duration <= 15:
            raise ValueError('Each ordinary reference video must be2..15seconds')
        video_seconds += duration
    audio_seconds = sum(_audio_seconds(audio) for audio in list(tracks.values()) + list(audios.values()))
    if video_seconds > 15 + 1e-6 or audio_seconds > 15 + 1e-6:
        raise ValueError('Per-class ordinary video/audio aggregate duration exceeds15seconds')
    # Reject an impossible target budget before allocating the native AV pair.
    aligned_frames = max(5, length)
    while aligned_frames % 17 != 5:
        aligned_frames += 1
    target_t = 2 + ((aligned_frames - 5) // 17) * 5
    target_lower_bound = target_t * (height // 32) * (width // 32) + 2 * round(aligned_frames / 24 * 40)
    if target_lower_bound + 1 > max_packed_tokens:
        raise ValueError('Target alone exceeds packed budget before latent allocation')
    rt = _runtime() if runtime is None else runtime
    if images or videos or asset_count:
        rt['validate_vae'](vae)
    if (tracks or audios) and audio_vae is None:
        raise ValueError('Connected audio references require the H3 audio VAE')
    latent, frame_count = rt['empty'](width, height, length)
    items, blocks, mapping, video_alignment = [], [], [], []
    counters = {'image': 0, 'video': 0, 'audio': 0}

    def add(item, source):
        kind = item['type']
        counters[kind] += 1
        label = {'image': 'Picture', 'video': 'Video', 'audio': 'Audio'}[kind]
        tag = '<%s %d>' % (label, counters[kind])
        items.append(item)
        mapping.append({'source': source, 'label': tag, 'type': kind})
        return tag

    for name, image in images.items():
        h, w = image.shape[1:3]
        scale = min(1.0, math.sqrt(width * height / (w * h))) if ref_image_size == 'match' else min(1.0, 2048 / min(w, h))
        tw, th = max(32, round(w * scale / 32) * 32), max(32, round(h * scale / 32) * 32)
        pixels = rt['resize'](image, tw, th, 'disabled')
        add({'type': 'image', 'data': pixels}, name)
        blocks.append({'kind': 'image', 'latent_h': th // 16, 'latent_w': tw // 16, 'latent': vae.encode(pixels)})
    for name, video in videos.items():
        original_frames = video.shape[0]
        source_fps = ref_video_fps[name]
        video = frames_at_24fps(video, source_fps)
        if video.shape[0] < 5:
            raise ValueError('Native reference video requires at least five frames after24fps sampling')
        vh, vw = video.shape[1:3]
        cw, ch = rt['canvas'](vw, vh)
        if vw * vh < cw * ch:
            cw, ch = max(32, round(vw / 32) * 32), max(32, round(vh / 32) * 32)
        frames = rt['resize'](video, cw, ch, 'disabled')
        n = min(frames.shape[0], frame_count)
        while n % 17 != 5:
            n -= 1
        frames = frames[:n]
        track_name = 'ref_video_audio_' + name.rsplit('_', 1)[-1]
        soundtrack = tracks.get(track_name)
        az, at = (None, 0) if soundtrack is None else rt['audio'](audio_vae, soundtrack)
        if soundtrack is not None:
            add({'type': 'audio'}, track_name)
        indices = list(range(0, n, 12))
        add({'type': 'video', 'data': frames[indices], 'timestamps': [i / 2 for i in range(len(indices))]}, name)
        z = vae.encode(frames)
        blocks.append({'kind': 'video_audio' if at else 'video', 'latent_t': z.shape[2],
                       'latent_h': ch // 16, 'latent_w': cw // 16,
                       'ref_audio_t': at, 'latent': z, 'audio_latent': az})
        video_alignment.append({'source': name, 'source_frames': original_frames,
                                'source_fps': source_fps, 'frames_at_24fps': video.shape[0], 'native_frames_used': n,
                                'policy': 'official_output_length_prefix_then_17n_plus_5'})
    for name, audio in audios.items():
        az, at = rt['audio'](audio_vae, audio)
        add({'type': 'audio'}, name)
        blocks.append({'kind': 'audio', 'ref_audio_t': at, 'audio_latent': az})

    character_label = None
    asset_report = None
    asset_reports, role_labels = {}, {}
    reconstructed_seconds = 0
    for role, asset_loader in specs:
        if not callable(asset_loader) or type(strength) not in (int, float) or not math.isfinite(strength) or not 0 < strength <= 1:
            raise ValueError('Selected RefMod needs an authorized loader and finite strength in (0,1]')
        if type(reference_fps) not in (int, float) or not math.isfinite(reference_fps) or not 1 <= reference_fps <= 120:
            raise ValueError('RefMod reference_fps must be finite in1..120')
        mod = asset_loader()
        if getattr(mod, 'kind', None) != 'video':
            raise ValueError('The selected eight-photo native stack must be author video-kind RefMod')
        block = mod.ref_block(float(strength))
        if block is None:
            raise ValueError('Selected RefMod produced no real reference block')
        block = dict(block)
        block['refmod'] = True
        actual_asset_tokens = block_tokens(block)
        if actual_asset_tokens != mod.token_count:
            raise ValueError('RefMod token metadata differs from actual packed latent shape')
        # Exactly the weakened latent used by DiT is decoded once for new Qwen
        # semantic encoding. It is never re-encoded by the video VAE.
        pixels = vae.decode(block['latent'])
        if pixels.ndim == 5 and pixels.shape[0] == 1:
            pixels = pixels[0]
        _visual(pixels, 'decoded RefMod')
        item = {'type': mod.kind}
        if mod.kind == 'image':
            item['data'] = pixels[:1].cpu().clone()
        else:
            times = [i / 2 for i in range(math.ceil(pixels.shape[0] * 2 / reference_fps))]
            indices = [min(round(t * reference_fps), pixels.shape[0] - 1) for t in times]
            item.update(data=pixels[indices].cpu(), timestamps=times)
        character_label = add(item, role + '_refmod')
        blocks.append(block)
        asset_report = {'kind': mod.kind, 'label': character_label, 'latent_frames': mod.latent_t,
                        'packed_tokens': actual_asset_tokens, 'vae_reencode_calls': 0,
                        'decoded_pixel_frames': pixels.shape[0], 'qwen_sampled_frames': item['data'].shape[0],
                        'reconstructed_seconds': pixels.shape[0] / reference_fps,
                        'source_clip_duration': None,
                        'timing': 'reconstructed RefMod at reference_fps; source-photo stack is not source motion'}
        reconstructed_seconds += pixels.shape[0] / reference_fps
        asset_reports[role] = asset_report
        role_labels[role] = character_label
        if video_seconds + reconstructed_seconds > 15 + 1e-6:
            raise ValueError('Video references plus reconstructed RefMod exceed15seconds')
    for role, label in role_labels.items():
        prompt = prompt.replace('{{' + role + '_ref}}', label)
    if '{{character_ref}}' in prompt:
        if 'person' not in role_labels:
            raise ValueError('Character placeholder requires person selection')
        prompt = prompt.replace('{{character_ref}}', role_labels['person'])
    if any('{{' + role + '_ref}}' in prompt for role in ('person','product')):
        raise ValueError('Role placeholder requires selected asset')
    for kind, number in re.findall(r'<(Picture|Video|Audio)\s+(\d+)>', prompt):
        key = {'Picture': 'image', 'Video': 'video', 'Audio': 'audio'}[kind]
        if not 1 <= int(number) <= counters[key]:
            raise ValueError('Prompt refers to an unavailable media label')
    ref_tokens = sum(block_tokens(block) for block in blocks)
    if counters != expected_counts or len(items) != sum(expected_counts.values()) or len(blocks) != selected_files or selected_files > 12 or ref_tokens > max_ref_tokens:
        raise ValueError('Actual joint reference count/token budget exceeded; no reference truncated')
    # One new full prompt + one combined presentation. No conditioning concat,
    # stale metadata copying, old prompt reuse, second Apply, or silent fallback.
    tokens = clip.tokenize(prompt, minimax_ref_items=items)
    conditioning = clip.encode_from_tokens_scheduled(tokens)
    if not conditioning:
        raise ValueError('H3 CLIP returned no conditioning')
    target_tokens = _target_tokens(latent)
    out, text_lengths = [], []
    for embedding, metadata in conditioning:
        length_now = embedding.shape[1]
        tags = metadata.get('minimax_token_tags')
        if tags is None or tuple(getattr(tags, 'shape', ())) != (length_now,):
            raise ValueError('New H3 minimax_token_tags must exactly match new embedding length')
        if metadata.get('minimax_refs') or metadata.get('maxapi_refmod_joint_v1'):
            raise ValueError('Encoder output already carries refs; duplicate Apply/merge refused')
        mask = metadata.get('attention_mask')
        if mask is not None and mask.shape[-1] != length_now:
            raise ValueError('New attention mask/embedding length mismatch')
        if length_now + ref_tokens + target_tokens > max_packed_tokens:
            raise ValueError('Actual packed sequence exceeds explicit budget; prompt not truncated')
        meta = dict(metadata)
        if blocks:
            meta['minimax_refs'] = list(blocks)
        meta['maxapi_refmod_joint_v1'] = True
        out.append([embedding, meta])
        text_lengths.append(length_now)
    return out, latent, {
        'reference_map': mapping, 'semantic_counts': counters, 'ref_block_count': len(blocks),
        'selected_file_count_including_refmod': selected_files,
        'semantic_item_count': len(items), 'reference_tokens': ref_tokens, 'target_tokens': target_tokens,
        'new_qwen_embedding_tokens': text_lengths, 'packed_tokens': [n + ref_tokens + target_tokens for n in text_lengths],
        'budget_policy': {'max_images': 9, 'max_videos': 3, 'max_audios_including_video_tracks': 3,
                          'max_mixed_selected_files': 12, 'video_track_is_additional_selected_file': False,
                          'max_ref_tokens': max_ref_tokens, 'max_packed_tokens': max_packed_tokens,
                          'token_budget_origin': 'mandatory_trusted_server_config_no_default_not_independently_validated_here',
                          'count_contract': 'official_H3_Base_Ref2VA_9I_3V_3A_mixed12; video_soundtracks_count_as_audio'},
        'durations_seconds': {'ordinary_video_total': video_seconds, 'audio_total_including_video_tracks': audio_seconds,
                              'refmod_reconstructed_video': reconstructed_seconds,
                              'refmod_reconstructed_frames_total': sum(a['latent_frames'] for a in asset_reports.values()),
                              'refmod_reconstructed_by_role': {role: {'seconds': a['reconstructed_seconds'], 'frames': a['latent_frames']} for role, a in asset_reports.items()},
                              'note': 'RefMod stack has no original clip duration. Its reconstruction is accounted but is not a verified ordinary2..15s source clip.'},
        'assets_by_role': asset_reports, 'asset': asset_report, 'video_alignment': video_alignment,
        'final_prompt': prompt, 'new_prompt_encoded_once': True, 'apply_again': False,
    }
