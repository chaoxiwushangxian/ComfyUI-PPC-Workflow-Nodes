"""Entrypoints embedded in two public-IDENode test workflows.

No installation, node registration, network, credentials or model operation at
import. All model execution is performed by the caller's RH Comfy process.
Owner, job and digest bindings must be set by MAX's authenticated backend.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
NONE = {"", "(none)", "None"}
MAX_MEDIA_BYTES = 64 * 1024 * 1024


def _read_media(path, binding, bridge):
    info = bridge._no_link(path)
    if info.st_size != binding["bytes"] or not path.is_file():
        raise ValueError("Media file differs from its exact upload binding")
    flags = os.O_RDONLY | getattr(os,"O_BINARY",0) | getattr(os,"O_NOFOLLOW",0)
    with os.fdopen(os.open(path,flags),"rb") as stream:
        if os.fstat(stream.fileno()).st_size != binding["bytes"]:
            raise ValueError("Opened media differs from binding")
        raw = stream.read(binding["bytes"]+1)
    if len(raw) != binding["bytes"] or hashlib.sha256(raw).hexdigest() != binding["sha256"]:
        raise ValueError("Media SHA256 mismatch")
    return raw


def _scope(bridge, owner_tag, job_id):
    import folder_paths
    return bridge.JobScope.create(folder_paths.get_output_directory(), owner_tag,
                                  job_id or uuid.uuid4().hex)


def create_asset(bridge, core_source, common_source, vae, images, *, owner_tag,
                 job_id="", ref_resolution=1024, max_asset_tokens=16384,
                 expected_pixel_shas_json="[]", source_bindings_json="[]"):
    """Eight required IMAGE ports. Report + annotated real binary output."""
    expected = json.loads(expected_pixel_shas_json)
    if expected:
        actual = [hashlib.sha256(x.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
                  for x in images]
        if len(expected) != 8 or actual != expected:
            raise ValueError("Eight decoded image digests do not match the frozen request")
    scope = _scope(bridge, owner_tag, job_id)
    source_receipts = _verify_photo_sources(scope, images, source_bindings_json, bridge)
    _, report, locator = bridge.create_eight(scope, images, vae, core_source, common_source,
                                            ref_resolution=ref_resolution, max_tokens=max_asset_tokens)
    report.update(success=True, operation="create_character_refmod", owner_tag=scope.owner_tag,
                  job_id=scope.job_id, asset_locator=locator, model_weights_trained=False,
                  original_source_bytes_verified=bool(source_receipts), original_sources=source_receipts,
                  authentication="MAX backend must bind owner; workflow only checks private paths and bytes")
    return json.dumps(report, ensure_ascii=False, indent=2), locator


def _verify_photo_sources(scope, images, source_bindings_json, bridge):
    """Bind original bytes and the deployed native decoder, not a local pixel ABI.

    The API graph must connect the same ordered eight upload filenames. Each
    SHA-verified byte snapshot is decoded privately with that worker's actual
    LoadImage class and compared with its connected IMAGE. No file search or
    image rewriting can replace a source that fails its original digest.
    """
    import folder_paths
    import nodes
    import torch
    bindings = json.loads(source_bindings_json)
    if bindings == []:
        return []  # Manual IMAGE-port mode; API backend must provide bindings.
    if type(bindings) is not list or len(bindings) != 8 or len(images) != 8:
        raise ValueError("Exactly eight ordered original-source bindings are required")
    input_root = Path(folder_paths.get_input_directory()).resolve(strict=True)
    seen, receipts = set(), []
    for index, (binding, image) in enumerate(zip(bindings, images), 1):
        if type(binding) is not dict or set(binding) != {"filename","sha256","bytes"}:
            raise ValueError("An original-source binding requires filename, sha256, bytes")
        name = binding["filename"]
        if type(name) is not str or name in seen or Path(name).suffix.lower() not in IMAGE_EXT:
            raise ValueError("Distinct exact uploaded image filenames are required")
        if type(binding["bytes"]) is not int or not 1 <= binding["bytes"] <= MAX_MEDIA_BYTES:
            raise ValueError("Original source exceeds this candidate's file-size contract")
        seen.add(name)
        raw = _read_media(bridge._contained(input_root, name), binding, bridge)
        snapshot = bridge._contained(scope.checked(), f"source_{index:02d}_" + binding["sha256"] + Path(name).suffix.lower(), exists=False)
        with snapshot.open("xb") as out:
            out.write(raw)
        selector = snapshot.relative_to(scope.output_root).as_posix() + " [output]"
        loader_class = nodes.NODE_CLASS_MAPPINGS["LoadImage"]
        loader = loader_class()
        decoded = getattr(loader, loader_class.FUNCTION)(selector)[0]
        if not isinstance(image, torch.Tensor) or not isinstance(decoded, torch.Tensor) or image.dtype != decoded.dtype or image.shape != decoded.shape or not torch.equal(image.detach().cpu(), decoded.detach().cpu()):
            raise ValueError(f"Photo {index} IMAGE differs from its verified original bytes")
        receipts.append({"index":index,"filename":name,"sha256":binding["sha256"],"bytes":len(raw),
                         "deployed_decoder_matches_connected_image":True,
                         "decoded_pixel_sha256":hashlib.sha256(decoded.detach().cpu().contiguous().numpy().tobytes()).hexdigest()})
    return receipts


def _selected_files(files, bindings_json, bridge):
    """Exact path or explicit bounded inline bytes; never a path-failure fallback."""
    import base64
    import re
    max_json_bytes = 12 * 1024 * 1024
    max_inline_bytes = 8 * 1024 * 1024
    if type(bindings_json) is not str or len(bindings_json) > max_json_bytes:
        raise ValueError("Input bindings JSON exceeds its byte contract")
    if len(bindings_json.encode("utf-8")) > max_json_bytes:
        raise ValueError("Input bindings JSON exceeds its byte contract")
    bindings = bridge._json(bindings_json)  # duplicate keys and NaN are rejected.
    if type(bindings) is not dict or type(files) is not dict:
        raise ValueError("Input bindings and selected files must be objects")
    allowed = {f"{kind}_{i}" for kind, count in (("image",9),("audio",3),("video",3)) for i in range(1,count+1)}
    if set(files) - allowed:
        raise ValueError("Unknown ordinary input slot")
    prepared = {}
    inline_total = 0
    transports = set()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    for key in sorted(allowed):
        name = files.get(key, "")
        if type(name) is not str:
            raise ValueError("Media input must be the exact uploaded relative filename")
        if name in NONE:
            continue
        binding = bindings.get(key)
        legacy_keys = {"filename","sha256","bytes"}
        inline_keys = legacy_keys | {"transport","data_base64"}
        if type(binding) is not dict or set(binding) not in (legacy_keys, inline_keys) or binding["filename"] != name:
            raise ValueError("Every selected media requires its exact server-owned binding")
        bridge._relative(name)
        bridge._digest(binding["sha256"])
        ext = {"image":IMAGE_EXT,"audio":AUDIO_EXT,"video":VIDEO_EXT}[key.split("_")[0]]
        size = binding["bytes"]
        if Path(name).suffix.lower() not in ext or type(size) is not int or not 1 <= size <= MAX_MEDIA_BYTES:
            raise ValueError("Media file format/size outside this test workflow contract")
        transport = "input_file"
        if set(binding) == inline_keys:
            transport = binding["transport"]
            if transport != "inline_base64_v1":
                raise ValueError("Unsupported ordinary-media transport")
            inline_total += size
            if inline_total > max_inline_bytes:
                raise ValueError("Total inline ordinary media exceeds8MiB")
            encoded = binding["data_base64"]
            if type(encoded) is not str or len(encoded) != 4 * ((size + 2) // 3) or not encoded.isascii():
                raise ValueError("Inline base64 length/ASCII differs from byte binding")
            padding = (-size) % 3
            body = encoded[:-padding] if padding else encoded
            if (padding and encoded[-padding:] != "=" * padding) or re.fullmatch(r"[A-Za-z0-9+/]+", body) is None:
                raise ValueError("Inline media requires canonical base64")
            if (padding == 2 and alphabet.index(body[-1]) & 15) or (padding == 1 and alphabet.index(body[-1]) & 3):
                raise ValueError("Inline base64 has noncanonical padding bits")
        transports.add(transport)
        prepared[key] = (name, binding, transport)
    if set(bindings) != set(prepared):
        raise ValueError("Upload bindings must exactly match selected ordinary inputs")
    if len(transports) > 1:
        raise ValueError("Do not mix path and inline ordinary-media transports")
    # Every selected slot and the entire budget are checked before any byte read
    # or base64 decoding. Inline mode never consults folder_paths or the network.
    input_root = None
    if transports == {"input_file"}:
        import folder_paths
        input_root = Path(folder_paths.get_input_directory()).resolve(strict=True)
    chosen = {}
    for key, (name, binding, transport) in prepared.items():
        if transport == "inline_base64_v1":
            raw = base64.b64decode(binding["data_base64"], validate=True)
            if len(raw) != binding["bytes"] or hashlib.sha256(raw).hexdigest() != binding["sha256"]:
                raise ValueError("Inline media SHA256/size differs from its binding")
        else:
            raw = _read_media(bridge._contained(input_root, name), binding, bridge)
        chosen[key] = {"source_name":name,"raw":raw,"sha256":binding["sha256"],
                       "suffix":Path(name).suffix.lower(),"transport":transport}
    return chosen


def _decode(scope, selected, bridge, use_video_soundtracks):
    import nodes
    from comfy_api.input_impl import VideoFromFile
    from comfy_extras.nodes_audio import LoadAudio
    images, videos, audios, tracks, fps, receipts = {}, {}, {}, {}, {}, []
    for slot, entry in selected.items():
        path = bridge._contained(scope.checked(), slot + "_" + entry["sha256"] + entry["suffix"], exists=False)
        with path.open("xb") as out:
            out.write(entry["raw"])
        kind, number = slot.split("_")
        # Native image/audio loaders accept an annotated selector. A plain
        # absolute output path is rejected by their input-root containment gate.
        selector = path.relative_to(scope.output_root).as_posix() + " [output]"
        if kind == "image":
            image = nodes.LoadImage().load_image(selector)[0]
            if image.shape[0] != 1:
                raise ValueError("An ordinary image slot requires one still image")
            images["ref_image_" + number] = image
        elif kind == "audio":
            import av
            with av.open(str(path)) as container:
                stream = next(iter(container.streams.audio), None)
                if stream is None or stream.duration is None or stream.time_base is None or not 2 <= float(stream.duration * stream.time_base) <= 15:
                    raise ValueError("Audio needs a known2..15s duration before decoding")
            audios["ref_audio_" + number] = LoadAudio.execute(selector)[0]
        else:
            # Metadata gate precedes native full decoding. Unknown duration is
            # rejected in this bounded adapter rather than decoded without a cap.
            import av
            with av.open(str(path)) as container:
                stream = next(iter(container.streams.video), None)
                if stream is None or stream.duration is None or stream.time_base is None:
                    raise ValueError("Video needs a known duration before bounded decoding")
                seconds = float(stream.duration * stream.time_base)
                if not 2 <= seconds <= 15 or stream.width * stream.height > 1920 * 1080:
                    raise ValueError("Test adapter accepts ordinary video2..15s up to1080P")
                declared_audio = len(container.streams.audio) > 0
            parts = VideoFromFile(str(path)).get_components()
            videos["ref_video_" + number] = parts.images
            fps["ref_video_" + number] = float(parts.frame_rate)
            if use_video_soundtracks:
                if declared_audio and parts.audio is None:
                    raise ValueError("Selected video soundtrack was declared but could not be decoded")
                if parts.audio is not None:
                    tracks["ref_video_audio_" + number] = parts.audio
        receipts.append({"slot":slot,"source_name":entry["source_name"],"sha256":entry["sha256"],"bytes":len(entry["raw"]),"transport":entry["transport"]})
    return images, videos, audios, tracks, fps, receipts


def generate_conditioning(bridge, reference, core_source, clip, vae, audio_vae, *,
        owner_tag, job_id, prompt, width, height, length, files, input_bindings_json="{}",
        use_character=False, character_transport="input_file", character_file="",
        character_base64="", character_sha256="", character_bytes=0,
        character_owner_tag="", strength=1.0, max_ref_tokens=32768, max_packed_tokens=65536,
        use_video_soundtracks=False, ref_image_size="match"):
    if type(use_character) is not bool or type(use_video_soundtracks) is not bool:
        raise ValueError("Explicit Boolean character and soundtrack switches required")
    if use_character and character_owner_tag != owner_tag:
        raise ValueError("Character owner differs from the authenticated server job owner")
    selected_names = [key for key,value in files.items() if type(value) is str and value not in NONE]
    if sum(key.startswith("video_") for key in selected_names)+int(use_character)>3 or len(selected_names)+int(use_character)>12:
        raise ValueError("Selected references plus character exceed the documented video/mixed counts")
    selected = _selected_files(files, input_bindings_json, bridge)
    counts = {kind:sum(key.startswith(kind + "_") for key in selected) for kind in ("image","audio","video")}
    if counts["video"] + int(use_character) > 3 or len(selected) + int(use_character) > 12:
        raise ValueError("Selected references plus character exceed the documented video/mixed counts")
    scope = _scope(bridge, owner_tag, job_id)
    asset_info = None
    asset_loader = None
    if use_character:
        if character_transport == "input_file":
            if character_base64 not in NONE:
                raise ValueError("Select exactly one character transport")
            import folder_paths
            asset_info = bridge.import_input_file(scope, folder_paths.get_input_directory(),
                         character_file, character_sha256, character_bytes)
        elif character_transport == "base64":
            if character_file not in NONE:
                raise ValueError("Select exactly one character transport")
            asset_info = bridge.import_base64(scope, character_base64, character_sha256, character_bytes)
        else:
            raise ValueError("Unsupported character transport")
        asset_loader = lambda: bridge.load_job_asset(scope, character_sha256, character_bytes, core_source,
                                                     max_tokens=max_ref_tokens)
    images, videos, audios, tracks, fps, receipts = _decode(scope, selected, bridge, use_video_soundtracks)
    conditioning, latent, report = reference.encode_generation(clip, vae, audio_vae, prompt, width, height, length,
          ref_image_size=ref_image_size, ref_images=images, ref_videos=videos,
          ref_audios=audios, ref_video_audios=tracks, ref_video_fps=fps,
          use_refmod=use_character, asset_loader=asset_loader, strength=strength,
          max_ref_tokens=max_ref_tokens, max_packed_tokens=max_packed_tokens)
    report.update(success=True, operation="fresh_task_refmod_conditioning", owner_tag=owner_tag,
                  job_id=scope.job_id, ordinary_inputs=receipts, imported_asset=asset_info,
                  model_weights_trained=False, character_enabled=use_character,
                  token_budgets="Application safety quotas for this test candidate, not verified model hard caps",
                  authentication="MAX must supply authenticated owner and asset bindings; not implemented by path strings")
    prefix = scope.directory.relative_to(scope.output_root).as_posix() + "/video"
    return conditioning, latent, json.dumps(report, ensure_ascii=False, indent=2), prefix


def generate_dual_conditioning(bridge, reference, core_source, clip, vae, audio_vae, *,
        owner_tag, job_id, prompt, width, height, length, files, input_bindings_json="{}",
        use_character=False, character_transport="input_file", character_file="",
        character_base64="", character_sha256="", character_bytes=0,
        character_owner_tag="", strength=1.0, max_ref_tokens=32768, max_packed_tokens=65536,
        use_video_soundtracks=False, ref_image_size="match", use_product=False, product_base64="", product_sha256="", product_bytes=0, product_owner_tag=""):
    if type(use_product) is not bool or not use_product:
        raise ValueError("Product-enabled entry only")
    if product_owner_tag != owner_tag:
        raise ValueError("Product owner differs from authenticated job owner")
    if use_character and product_sha256 == character_sha256:
        raise ValueError("One file cannot silently occupy both asset roles")
    if type(use_character) is not bool or type(use_video_soundtracks) is not bool:
        raise ValueError("Explicit Boolean character and soundtrack switches required")
    if use_character and character_owner_tag != owner_tag:
        raise ValueError("Character owner differs from the authenticated server job owner")
    selected_names = [key for key,value in files.items() if type(value) is str and value not in NONE]
    if sum(key.startswith("video_") for key in selected_names)+(int(use_character)+1)>3 or len(selected_names)+(int(use_character)+1)>12:
        raise ValueError("Selected references plus character exceed the documented video/mixed counts")
    selected = _selected_files(files, input_bindings_json, bridge)
    counts = {kind:sum(key.startswith(kind + "_") for key in selected) for kind in ("image","audio","video")}
    if counts["video"] + (int(use_character)+1) > 3 or len(selected) + (int(use_character)+1) > 12:
        raise ValueError("Selected references plus character exceed the documented video/mixed counts")
    scope = _scope(bridge, owner_tag, job_id)
    asset_info = None
    asset_loader = None
    if use_character:
        if character_transport == "input_file":
            if character_base64 not in NONE:
                raise ValueError("Select exactly one character transport")
            import folder_paths
            asset_info = bridge.import_input_file(scope, folder_paths.get_input_directory(),
                         character_file, character_sha256, character_bytes)
        elif character_transport == "base64":
            if character_file not in NONE:
                raise ValueError("Select exactly one character transport")
            asset_info = bridge.import_base64(scope, character_base64, character_sha256, character_bytes)
        else:
            raise ValueError("Unsupported character transport")
        asset_loader = lambda: bridge.load_job_asset(scope, character_sha256, character_bytes, core_source,
                                                     max_tokens=max_ref_tokens)
    product_info = bridge.import_base64(scope, product_base64, product_sha256, product_bytes)
    product_loader = lambda: bridge.load_job_asset(scope, product_sha256, product_bytes, core_source, max_tokens=max_ref_tokens)
    specs = ([('person', asset_loader)] if use_character else []) + [('product', product_loader)]
    images, videos, audios, tracks, fps, receipts = _decode(scope, selected, bridge, use_video_soundtracks)
    conditioning, latent, report = reference.encode_generation(clip, vae, audio_vae, prompt, width, height, length,
          ref_image_size=ref_image_size, ref_images=images, ref_videos=videos,
          ref_audios=audios, ref_video_audios=tracks, ref_video_fps=fps,
          use_refmod=use_character, asset_loader=asset_loader, strength=strength,
          max_ref_tokens=max_ref_tokens, max_packed_tokens=max_packed_tokens, asset_specs=specs)
    report.update(success=True, operation="fresh_task_refmod_conditioning", owner_tag=owner_tag,
                  job_id=scope.job_id, ordinary_inputs=receipts, imported_asset=asset_info,
                  model_weights_trained=False, character_enabled=use_character, product_enabled=True, imported_product=product_info, asset_roles_trusted_server_binding_required=True,
                  token_budgets="Application safety quotas for this test candidate, not verified model hard caps",
                  authentication="MAX must supply authenticated owner and asset bindings; not implemented by path strings")
    prefix = scope.directory.relative_to(scope.output_root).as_posix() + "/video"
    return conditioning, latent, json.dumps(report, ensure_ascii=False, indent=2), prefix
