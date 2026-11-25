"""RefMod consumers for nodes 9482009 and 9482140.

The pinned pack is imported as normal modules. Nothing here execs, compiles,
or decompresses a source string. Reference video bytes are produced with PyAV
instead of an ffmpeg subprocess. The multi-window report stays on the returned
bundle and is not written onto builtins.
"""
from pathlib import Path

_MISSING = object()


def _pinned_core_bytes():
    path = Path(__file__).resolve().parent / "refmod_pinned" / "core.py"
    try:
        raw = path.read_bytes()
    except OSError:
        raise ValueError("pinned core source unreadable") from None
    from .refmod_pinned.bridge import CORE_SHA256, _sha
    if not raw or _sha(raw) != CORE_SHA256:
        raise ValueError("pinned author source mismatch: core")
    return raw


def invoke(fn, inputs):
    """Bind one call's inputs, then remove those names again."""
    namespace = fn.__globals__
    before = set(namespace)
    saved = {key: namespace[key] for key in inputs if key in namespace}
    namespace.update(inputs)
    try:
        return fn()
    finally:
        for key in list(namespace):
            if key not in before:
                del namespace[key]
        namespace.update(saved)


# RefMod reference assets; NOT LoRA training. Original core/common: MIT, Luisa2026.
def _maxapi_run(**values):
    from .refmod_pinned import bridge, reference_single, runtime_single
    core_source = _pinned_core_bytes()
    values = dict(values)
    values["prompt"] = values.pop("generation_prompt")
    files = {key: values.pop(key) for key in list(values) if key.startswith(("image_", "audio_", "video_")) and key.rsplit("_", 1)[-1].isdigit()}
    return runtime_single.generate_conditioning(
        bridge, reference_single, core_source,
        values.pop("clip"), values.pop("vae"), values.pop("audio_vae"), files=files, **values)
# Strict fixed34-control contract. Function-only source is safe to embed in the
# private IDE code namespace; no module globals, imports, files or models at load.

def _maxapi_normalize_controls(values):
    import math
    import re
    bool_fields = {'use_character', 'use_video_soundtracks'}
    int_fields = {'character_bytes', 'width', 'height', 'length', 'max_ref_tokens', 'max_packed_tokens'}
    float_fields = {'strength'}
    string_fields = {
        'character_file', 'character_transport', 'character_base64',
        'character_sha256', 'character_owner_tag', 'owner_tag', 'job_id',
        'input_bindings_json', 'generation_prompt', 'ref_image_size',
        'image_1', 'image_2', 'image_3', 'image_4', 'image_5',
        'image_6', 'image_7', 'image_8', 'image_9',
        'audio_1', 'audio_2', 'audio_3', 'video_1', 'video_2', 'video_3'}
    model_fields = {'clip', 'vae', 'audio_vae'}
    expected = bool_fields | int_fields | float_fields | string_fields | model_fields
    if type(values) is not dict or set(values) != expected:
        raise ValueError('Exactly34 fixed controls and3 model objects are required')
    result = dict(values)  # Shallow copy: actual model and string identities remain.
    converted = []
    for name in sorted(bool_fields):
        value = values[name]
        if type(value) is bool:
            continue
        if type(value) is str and value in ('true', 'false'):
            result[name] = value == 'true'
            converted.append(name)
        else:
            raise ValueError('Strict Boolean token required for ' + name)
    for name in sorted(int_fields):
        value = values[name]
        if type(value) is int and value >= 0:
            continue
        if type(value) is str and re.fullmatch(r'(?:0|[1-9][0-9]*)', value):
            result[name] = int(value)
            converted.append(name)
        else:
            raise ValueError('Canonical nonnegative integer required for ' + name)
    for name in sorted(float_fields):
        value = values[name]
        if type(value) is str:
            if re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value) is None:
                raise ValueError('Strict JSON number required for ' + name)
        elif type(value) not in (int, float):
            raise ValueError('Finite number excluding Boolean required for ' + name)
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise ValueError('Finite number required for ' + name) from None
        if not math.isfinite(number):
            raise ValueError('Finite number required for ' + name)
        result[name] = number
        if type(value) is not float:
            converted.append(name)
    for name in string_fields:
        if type(values[name]) is not str:
            raise ValueError('String required without rewriting for ' + name)
    for name in model_fields:
        if result[name] is not values[name]:
            raise AssertionError('Model identity changed')
    return result, sorted(converted)

"""Embedded IDE helper: one result object per node; no registration changes."""

def _maxapi_control_binding(values):
    import hashlib
    import json
    controls = {key:value for key,value in values.items()
                if key not in ('clip','vae','audio_vae')}
    if len(controls) != 34:
        raise ValueError('Exactly34 consumer controls required')
    json_types = {key:type(value).__name__ for key,value in sorted(controls.items())}
    base64_value = controls['character_base64']
    if type(base64_value) is not str:
        raise ValueError('Character base64 control must be a string')
    controls['character_base64'] = {
        'sha256':hashlib.sha256(base64_value.encode('utf-8')).hexdigest(),
        'chars':len(base64_value)}
    raw = json.dumps(controls,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return {'scheme':'single-socket-controls-v1','json_types':json_types,
            'sha256':hashlib.sha256(raw).hexdigest()}


def _maxapi_failure_bundle(error, values, binding=None):
    import json
    import traceback
    from .rejection import host_execution_blocker as _host_blocker
    ExecutionBlocker = _host_blocker()
    def scalar(name):
        value=values.get(name)
        return value if type(value) in (str,int,float,bool,type(None)) else {'received_type':type(value).__name__}
    report = {
        'success':False,'operation':'fresh_task_refmod_conditioning',
        'phase':'consumer_preparation','consumer_output_bridge':'single-socket-v2',
        'owner_tag':scalar('owner_tag'),'job_id':scalar('job_id'),
        'character_enabled':scalar('use_character'),
        'error_type':type(error).__name__,'error':str(error)[:2048],
        'traceback':[{'file':frame.filename.replace('\\','/').rsplit('/',1)[-1],
                      'line':frame.lineno,'function':frame.name}
                     for frame in traceback.extract_tb(error.__traceback__,limit=-12)],
        'request_control_binding':binding,
        'transport_control_binding':None,
        'api_input_normalization':{'scheme':'rh-strict-json-scalars-v1','converted_fields':[],'applied':False},
        'sampling_started':False,'actual_video_produced':False,
        'model_weights_trained':False}
    return {'positive':ExecutionBlocker(None),'latent':ExecutionBlocker(None),
            'report':json.dumps(report,ensure_ascii=False,indent=2),'video_prefix':''}


def _maxapi_safe_bundle(**values):
    import json
    binding = None
    transport_binding = None
    normalized = values
    normalization = {'scheme':'rh-strict-json-scalars-v1','converted_fields':[],'applied':False}
    try:
        transport_binding = _maxapi_control_binding(values)
        normalized, converted = _maxapi_normalize_controls(values)
        normalization = {'scheme':'rh-strict-json-scalars-v1','converted_fields':converted,'applied':True}
        binding = _maxapi_control_binding(normalized)
        positive, latent, text, video_prefix = _maxapi_run(**normalized)
        report = json.loads(text)
        if type(report) is not dict or report.get('success') is not True:
            raise ValueError('Conditioning helper did not return a successful report')
        report['request_control_binding'] = binding
        report['transport_control_binding'] = transport_binding
        report['api_input_normalization'] = normalization
        report['consumer_output_bridge'] = 'single-socket-v2'
        return {'positive':positive,'latent':latent,
                'report':json.dumps(report,ensure_ascii=False,indent=2),
                'video_prefix':video_prefix}
    except Exception as error:
        # File-mode must not swallow encoder failures as ExecutionBlocker:
        # that made t217u tasks 2120211944974802945/2493476519938/4497573699586
        # return SUCCESS with no SaveVideo output in ~14s. Photo mode still
        # returns blockers earlier in _vip_entry and never reaches this helper.
        bundle = _maxapi_failure_bundle(error,normalized,binding)
        report = json.loads(bundle['report'])
        report['transport_control_binding'] = transport_binding
        report['api_input_normalization'] = normalization
        bundle['report'] = json.dumps(report,ensure_ascii=False,indent=2)
        raise

def _maxapi_entry():
    try:
        return _maxapi_safe_bundle(clip=clip, vae=vae, audio_vae=audio_vae, use_character=use_character, character_file=character_file, character_transport=character_transport, character_base64=character_base64, character_sha256=character_sha256, character_bytes=character_bytes, character_owner_tag=character_owner_tag, owner_tag=owner_tag, job_id=job_id, input_bindings_json=input_bindings_json, strength=strength, generation_prompt=generation_prompt, width=width, height=height, length=length, max_ref_tokens=max_ref_tokens, max_packed_tokens=max_packed_tokens, use_video_soundtracks=use_video_soundtracks, ref_image_size=ref_image_size, image_1=image_1, image_2=image_2, image_3=image_3, image_4=image_4, image_5=image_5, image_6=image_6, image_7=image_7, image_8=image_8, image_9=image_9, audio_1=audio_1, audio_2=audio_2, audio_3=audio_3, video_1=video_1, video_2=video_2, video_3=video_3)
    except Exception as error:
        context = {name:globals().get(name) for name in ("owner_tag","job_id","use_character")}
        return _maxapi_failure_bundle(error,context)

def _vip_scene_prompt(source):
    # File mode + scene only. Person = RefMod {{character_ref}} (-> <Video 1>), environment = scene <Picture 1>.
    import re
    ch = "{{character_ref}}"
    sc = "\u0000VIPSCENE\u0000"
    p = re.sub(r"<(?:Video|Audio)\s+\d+>", "", source, flags=re.IGNORECASE)
    p = re.sub(r"<Picture\s+\d+>", ch, p, flags=re.IGNORECASE)
    pairs = (
        ("Retain the original environment, composition, visible physical lettering and original garments of " + ch + " throughout this one continuous shot. Keep the same location and outfit.",
         "Place the complete speaking person, with the face, hair and garments of " + ch + ", inside the room of " + sc + " throughout this one continuous shot. The layout, windows, furniture, plants, decor and lighting of " + sc + " stay recognizable and continuously visible around and behind the person. " + ch + " supplies identity, face, hair and clothing only; never reuse its plain backdrop or studio wall. Keep this location and outfit."),
        ("Maintain the illumination, brightness, color temperature, exposure, gain and white balance established by " + ch,
         "Maintain the illumination, brightness, color temperature, exposure, gain and white balance of the " + sc + " room, with the person lit consistently with that room"),
        ("retain the initial camera position, viewing angle, distance, framing and field of view of " + ch + " by default",
         "use a stable talking-head framing of the person, at the camera distance of " + ch + ", in front of the " + sc + " room by default"),
        ("With no scene reference, retain the environment, lighting and composition of " + ch + ", unless the original document describes an environment.",
         "Use the environment, layout and lighting of " + sc + " as the continuous background for the person from " + ch + "."),
        ("Treat the room in Picture 1", "Treat the room in " + sc),
        ("Keep the room in Picture 1", "Keep the room in " + sc),
        ("Preserve the original location,", "Preserve the " + sc + " location,"),
    )
    for a, b in pairs:
        p = p.replace(a, b)
    head = ("<Subject 2> is the environment from " + sc + ". It supplies background, room layout, windows, furniture, plants, decor and lighting only, never the speaker or garments; no person from " + sc + " appears.\n")
    if p.startswith("subject_definitions:\n"):
        first, sep, rest = p.partition("\n")
        line, sep2, rest2 = rest.partition("\n")
        p = first + "\n" + line + "\n" + head + rest2
    else:
        p = head + p
    keep = "<Subject 2> (appears in [Shot 1]): fully_preserved - environment, layout and lighting of " + sc + ".\n"
    if "retention_analysis:\n" in p:
        p = p.replace("retention_analysis:\n", "retention_analysis:\n" + keep, 1)
    rule = ("\nScene requirement for the entire shot: the background is the room shown in " + sc + ", with its windows, furniture, plants and decor as they appear there, not a plain wall or studio backdrop. The person from " + ch + " is placed naturally in that room at a believable scale, facing the camera.")
    if "\n\noverall_soundscape:" in p:
        p = p.replace("\n\noverall_soundscape:", rule + "\n\noverall_soundscape:", 1)
    else:
        p = p + rule
    p = p.replace(sc, "<Picture 1>")
    cn = ch + ": 本镜唯一人物身份参考（脸、发型、服装）。\n<Picture 1>: 本镜场景环境参考，只使用其中的背景、空间、陈设和光线；人物身份与外貌只来自" + ch + "，不要出现场景图里的任何人物。\n"
    if p.startswith("subject_definitions:\n"):
        return "subject_definitions:\n" + cn + p[len("subject_definitions:\n"):]
    return "subject_definitions:\n" + cn + p

def _vip_scene_prompt_r3(source, with_video):
    # Reference-only scene prompt. Person = {{character_ref}} (RefMod), environment = <Picture 1> (+ <Video 1> still-camera room clip).
    base = _vip_scene_prompt(source)
    if not with_video:
        return base
    base = base.replace("<Picture 1>: 本镜场景环境参考，只使用其中的背景、空间、陈设和光线；",
        "<Picture 1> 与 <Video 1>: 同一个房间的场景环境参考（<Video 1> 是该房间的固定机位空镜，不含人物、不代表运镜），只使用其中的背景、空间、陈设和光线；", 1)
    base = base.replace("<Subject 2> is the environment from <Picture 1>.",
        "<Subject 2> is the environment from <Picture 1> and <Video 1> (the same empty room; <Video 1> is a still-camera plate of it, not a camera move).", 1)
    base = base.replace("the background is the room shown in <Picture 1>,",
        "the background is the room shown in <Picture 1> and <Video 1>,", 1)
    return base

def _vip_scene_refs(arr, width, height, length, character_base64):
    # arr: uint8 HxWx3 scene. Returns (bindings dict, report). Reference slots only; no first frame, no compositing.
    import base64, hashlib, io, json, struct
    import numpy as np
    from PIL import Image
    im = Image.fromarray(arr, "RGB")
    w, h = im.size
    s = 768.0 / min(w, h)                      # mild normalisation: short edge 768, long edge <= 1536
    s = min(s, 1536.0 / max(w, h))
    pic = im.resize((max(64, round(w * s)), max(64, round(h * s))), Image.LANCZOS) if abs(s - 1.0) > 1e-3 else im
    buf = io.BytesIO(); pic.save(buf, "JPEG", quality=92); praw = buf.getvalue()
    def r32(v): return max(32, round(v / 32) * 32)
    pic_tok = (r32(pic.size[1]) // 32) * (r32(pic.size[0]) // 32)
    # Still-camera room plate as an ORDINARY video reference (same kind as the RefMod stack). 49 frames @24fps = 2.04 s.
    s2 = min(1.0, 576.0 / min(w, h))
    vw, vh = max(64, (round(w * s2) // 2) * 2), max(64, (round(h * s2) // 2) * 2)
    plate = np.ascontiguousarray(np.asarray(im.resize((vw, vh), Image.LANCZOS), dtype=np.uint8))
    vid_frames = 49
    n = vid_frames
    while n % 17 != 5:
        n -= 1
    vid_tok = (2 + ((n - 5) // 17) * 5) * (r32(vh) // 32) * (r32(vw) // 32)   # upper bound (own-size canvas)
    # Budget (encode_generation raises on overflow; never truncates). RefMod tokens from the character file header.
    ref_tok = 0
    try:
        head = base64.b64decode(character_base64[:16])[:8]
        hl = struct.unpack("<Q", head)[0]
        need = 8 + hl
        hdr = json.loads(base64.b64decode(character_base64[:4 * ((need + 2) // 3) + 4])[8:need])
        m = json.loads(hdr["__metadata__"]["refmod_meta"])
        ref_tok = int(m["latent_t"]) * (int(m["latent_h"]) // 2) * (int(m["latent_w"]) // 2)
    except Exception:
        ref_tok = 12288
    aligned = max(5, int(length))
    while aligned % 17 != 5:
        aligned += 1
    tgt_tok = (2 + ((aligned - 5) // 17) * 5) * (int(height) // 32) * (int(width) // 32) + 2 * round(aligned / 24 * 40)
    text_margin = 16000
    budget = 65536
    use_video = ref_tok + pic_tok + vid_tok <= 32768 and ref_tok + pic_tok + vid_tok + tgt_tok + text_margin <= budget
    rep = {"picture": list(pic.size), "picture_tokens": pic_tok, "refmod_tokens_est": ref_tok, "target_tokens_est": tgt_tok,
           "video_plate": [vw, vh, vid_frames], "video_tokens_est": vid_tok, "text_margin": text_margin, "video_ref": False}
    files = {"image_1": ("vip_scene_" + hashlib.sha256(praw).hexdigest()[:16] + ".jpg", praw)}
    if use_video:
        try:
            import av
            vb = io.BytesIO()
            with av.open(vb, "w", format="mp4") as out:
                st = None
                for codec in ("libx264", "h264", "mpeg4"):
                    try:
                        st = out.add_stream(codec, rate=24)
                        break
                    except Exception:
                        st = None
                if st is None:
                    raise RuntimeError("no mp4 video encoder")
                st.width, st.height, st.pix_fmt = vw, vh, "yuv420p"
                if st.codec_context.name in ("libx264", "h264"):
                    st.options = {"crf": "12", "preset": "veryfast"}
                else:
                    st.bit_rate = 6000000
                fr = av.VideoFrame.from_ndarray(plate, format="rgb24")
                for i in range(vid_frames):
                    fr.pts = None
                    for pkt in st.encode(fr):
                        out.mux(pkt)
                for pkt in st.encode():
                    out.mux(pkt)
            vraw = vb.getvalue()
            files["video_1"] = ("vip_scene_plate_" + hashlib.sha256(vraw).hexdigest()[:16] + ".mp4", vraw)
            rep["video_ref"] = True
            rep["video_codec"] = st.codec_context.name
            rep["video_bytes"] = len(vraw)
        except Exception as e:
            rep["video_ref_unavailable"] = type(e).__name__ + ": " + str(e)[:300]
    else:
        rep["video_ref_unavailable"] = "packed-token budget"
    bindings = {}
    for slot, (fname, raw) in files.items():
        bindings[slot] = {"filename": fname, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                          "transport": "inline_base64_v1", "data_base64": base64.b64encode(raw).decode("ascii")}
    return bindings, rep

def _vip_is_missing(value):
    if value is None:
        return True
    if type(value) is str and value in ("", "None", "(none)"):
        return True
    return False

def _vip_image_digest(img):
    import hashlib
    import numpy as np
    if img is None or not hasattr(img, "shape"):
        return None
    frame = img[0] if len(getattr(img, "shape", ())) >= 1 else img
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().float().numpy()
    arr = np.ascontiguousarray(np.clip(np.asarray(frame, dtype=np.float32)[..., :3], 0.0, 1.0))
    return hashlib.sha256(arr.tobytes()).hexdigest(), arr

def _vip_encode_image(img, prefix):
    import base64
    import hashlib
    import io
    import numpy as np
    from PIL import Image
    if not hasattr(img, "shape") or len(img.shape) < 3:
        raise ValueError("VIP_REF_IMAGE_INVALID")
    frame = img[0] if len(img.shape) == 4 else img
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().float().numpy()
    arr = (np.clip(np.asarray(frame, dtype=np.float32)[..., :3], 0.0, 1.0) * 255.0).round().astype(np.uint8)
    im = Image.fromarray(arr, "RGB")
    if min(im.size) < 16:
        raise ValueError("VIP_REF_IMAGE_TOO_SMALL")
    im.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    raw = buf.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    name = prefix + "_" + sha[:16] + ".jpg"
    return name, {"filename": name, "sha256": sha, "bytes": len(raw),
                  "transport": "inline_base64_v1", "data_base64": base64.b64encode(raw).decode("ascii")}

def _vip_encode_video(frames, prefix):
    import base64
    import hashlib
    import io
    import numpy as np
    from PIL import Image
    if not hasattr(frames, "shape") or len(frames.shape) != 4 or frames.shape[0] < 1:
        raise ValueError("VIP_REF_VIDEO_INVALID")
    batch = frames
    if hasattr(batch, "detach"):
        batch = batch.detach().cpu().float().numpy()
    arr = (np.clip(np.asarray(batch, dtype=np.float32)[..., :3], 0.0, 1.0) * 255.0).round().astype(np.uint8)
    if min(arr.shape[1], arr.shape[2]) < 16:
        raise ValueError("VIP_REF_VIDEO_TOO_SMALL")
    try:
        import av
        buf = io.BytesIO()
        container = av.open(buf, mode="w", format="mp4")
        stream = container.add_stream("libx264", rate=24)
        stream.width = int(arr.shape[2])
        stream.height = int(arr.shape[1])
        stream.pix_fmt = "yuv420p"
        for frame in arr:
            video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
            for packet in stream.encode(video_frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        raw = buf.getvalue()
    except Exception:
        raise ValueError("VIP_REF_VIDEO_ENCODE_FAILED")
    if not 0 < len(raw) <= 16 * 1024 * 1024:
        raise ValueError("VIP_REF_VIDEO_SIZE_INVALID")
    sha = hashlib.sha256(raw).hexdigest()
    name = prefix + "_" + sha[:16] + ".mp4"
    return name, {"filename": name, "sha256": sha, "bytes": len(raw),
                  "transport": "inline_base64_v1", "data_base64": base64.b64encode(raw).decode("ascii")}

def _vip_audio_error_slot(audio, prefix):
    # Error presentation only. Multi-window slots are compacted; recover the
    # original user slot by object identity without changing successful bindings.
    g = globals()
    original = [str(i) for i in range(1, 4)
                if audio is not None and g.get("user_audio_%d" % i) is audio]
    if original:
        return "上传参考音色槽位" + "、".join(original)
    import re
    match = re.fullmatch(r"vip_aud([1-3])", str(prefix))
    return "当前镜头参考音色槽位" + match.group(1) + "（第" + match.group(1) + "路编码，对应上传槽位未知）" if match else "当前镜头参考音色（对应上传槽位未知）"


def _vip_audio_input_failure(code, audio, prefix, seconds=None):
    slot = _vip_audio_error_slot(audio, prefix)
    if code == "VIP_MW_REF_AUDIO_TOO_SHORT":
        message = ("VIP_MW_REF_AUDIO_TOO_SHORT:" + slot + "的有效录音不足2秒（本流程编码后的有效时长"
                   + repr(float(seconds)) + "秒）。请检查已上传的各条参考音色，并换用2至15秒清晰、完整的说话录音；"
                   "如不需要参考音色，请清空相应参考音频。")
    elif code == "VIP_REF_AUDIO_INVALID":
        message = ("VIP_REF_AUDIO_INVALID:" + slot + "未能读取到有效录音。"
                   "请检查已上传的各条参考音色，重新上传2至15秒清晰、完整的说话录音；如不需要参考音色，请清空相应参考音频。")
    else:
        raise ValueError("Unsupported public reference-audio error category")
    error = ValueError(message)
    error._vip_public_reference_code = code
    error._vip_public_reference_message = message
    return error


def _vip_public_reference_failure(error, stage):
    code = getattr(error, "_vip_public_reference_code", None)
    message = getattr(error, "_vip_public_reference_message", None)
    if code in ("VIP_MW_REF_AUDIO_TOO_SHORT", "VIP_REF_AUDIO_INVALID") and type(message) is str and message.startswith(code + ":"):
        return message
    return ("VIP_REFERENCE_PROCESSING_FAILED:" + stage + "未能完成。"
            "请保留本次任务号，检查平台任务状态与权限；如仍失败，请提供任务号联系支持。请勿直接重复生成。")


def _vip_record_private_reference_failure(error, stage):
    # Private process memory only; never an IDE output or a user result file.
    import traceback
    _vip_record_private_reference_failure._last_report = {
        "stage": stage, "exception_type": type(error).__name__,
        "exception_message": str(error), "traceback": traceback.format_exc()}


def _vip_encode_audio(audio, prefix):
    import base64
    import hashlib
    import io
    import wave
    import numpy as np
    if audio is None:
        raise _vip_audio_input_failure("VIP_REF_AUDIO_INVALID", audio, prefix)
    waveform = None
    sr = 24000
    if type(audio) is dict:
        waveform = audio.get("waveform")
        sr = int(audio.get("sample_rate") or sr)
    elif hasattr(audio, "shape"):
        waveform = audio
    if waveform is None:
        raise _vip_audio_input_failure("VIP_REF_AUDIO_INVALID", audio, prefix)
    if hasattr(waveform, "detach"):
        waveform = waveform.detach().cpu().float().numpy()
    arr = np.asarray(waveform, dtype=np.float32)
    while arr.ndim > 2:
        arr = arr[0]
    if arr.ndim == 1:
        arr = arr[None, :]
    # arr: C x T
    # r4: runtime accepts reference audio of 2..15 s; keep the first 14.9 s of a longer one, refuse one under 2 s.
    rate = max(8000, sr)
    if arr.shape[-1] < 2 * rate:
        raise _vip_audio_input_failure("VIP_MW_REF_AUDIO_TOO_SHORT", audio, prefix, arr.shape[-1] / float(rate))
    if arr.shape[-1] > 15 * rate:
        arr = arr[:, :int(14.9 * rate)]
    pcm = np.clip(arr, -1.0, 1.0)
    interleaved = (pcm.T.reshape(-1) * 32767.0).round().astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(int(pcm.shape[0]))
        wf.setsampwidth(2)
        wf.setframerate(max(8000, sr))
        wf.writeframes(interleaved.tobytes())
    raw = buf.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    name = prefix + "_" + sha[:16] + ".wav"
    return name, {"filename": name, "sha256": sha, "bytes": len(raw),
                  "transport": "inline_base64_v1", "data_base64": base64.b64encode(raw).decode("ascii")}

def _vip_entry():
    import base64
    import hashlib
    import json
    import os
    import pathlib
    import re
    import uuid
    from .rejection import host_execution_blocker as _host_blocker
    ExecutionBlocker = _host_blocker()
    try:
        _guard = idenode_loop_guard
    except NameError:
        _guard = None
    else:
        from .host_boundary import coerce_dotted_unique_id
        _guard = coerce_dotted_unique_id(_guard)
    use = use_character
    if type(use) is str and use in ("true", "false"):
        use = use == "true"
    try:
        prod = use_product
    except NameError:
        prod = False
    if type(prod) is str and prod in ("true", "false"):
        prod = prod == "true"
    prod = prod is True
    if use is not True and not prod:
        # Photo/native mode: do not raise, so an eager ifElse cannot fail the #136 path.
        return {"positive": ExecutionBlocker(None), "latent": ExecutionBlocker(None),
                "report": json.dumps({"success": True, "skipped": "photo_mode"}, ensure_ascii=False),
                "video_prefix": ""}
    transport = character_transport
    name = character_file
    encoded = character_base64
    digest = character_sha256
    size = int(character_bytes)
    if use is not True:
        transport, name, encoded, digest, size = "base64", "", "", "", 0
    elif transport == "input_file":
        import folder_paths
        if encoded not in ("", "None", "(none)"):
            raise ValueError("VIP_CHOOSE_ONE_FILE_TRANSPORT")
        if type(name) is not str or name in ("", "None", "(none)"):
            raise ValueError("VIP_CHARACTER_FILE_REQUIRED")
        root = pathlib.Path(folder_paths.get_input_directory()).resolve(strict=True)
        rel = pathlib.PurePosixPath(name)
        if rel.is_absolute() or "\\" in name or not rel.parts or any(p in (".", "..") for p in rel.parts):
            raise ValueError("VIP_CHARACTER_UPLOAD_PATH_INVALID")
        path = root.joinpath(*rel.parts)
        for part in [path, *path.parents]:
            if part == root:
                break
            if part.is_symlink():
                raise ValueError("VIP_CHARACTER_SYMLINK_FORBIDDEN")
        path.resolve(strict=True).relative_to(root)
        if path.suffix.lower() != ".safetensors" or not path.is_file() or not 0 < path.stat().st_size <= 8 * 1024 * 1024:
            raise ValueError("VIP_CHARACTER_FORMAT_OR_SIZE_INVALID")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as f:
            raw = f.read(8 * 1024 * 1024 + 1)
        if not 0 < len(raw) <= 8 * 1024 * 1024:
            raise ValueError("VIP_CHARACTER_SIZE_INVALID")
        actual = hashlib.sha256(raw).hexdigest()
        if digest not in ("", actual) or size not in (0, len(raw)):
            raise ValueError("VIP_CHARACTER_UPLOAD_BINDING_MISMATCH")
        digest, size, encoded, name, transport = actual, len(raw), base64.b64encode(raw).decode("ascii"), "", "base64"
    elif transport == "base64":
        if name not in ("", "None", "(none)") or not digest or size <= 0:
            raise ValueError("VIP_CHARACTER_BASE64_BINDING_REQUIRED")
    else:
        raise ValueError("VIP_CHARACTER_TRANSPORT_INVALID")
    # Keep 0003 already-remapped <Picture N>/<Video N>/<Audio N> tokens. Do not rewrite them.
    model_prompt = generation_prompt if type(generation_prompt) is str else ""
    owner = "ea6d1efb1552512bb85994cefdd1d8c0"
    values = dict(clip=clip, vae=vae, audio_vae=audio_vae, use_character=(use is True),
        character_file=name, character_transport=transport, character_base64=encoded,
        character_sha256=digest, character_bytes=size, character_owner_tag=owner,
        owner_tag=owner, job_id=uuid.uuid4().hex, input_bindings_json="{}", strength=1.0,
        generation_prompt=model_prompt, width=width, height=height, length=length,
        max_ref_tokens=32768, max_packed_tokens=524288, use_video_soundtracks=False,
        ref_image_size="max")
    for kind, count in (("image", 9), ("audio", 3), ("video", 3)):
        for i in range(1, count + 1):
            values[kind + "_" + str(i)] = ""
    bindings = {}
    sentinel_digest = None
    try:
        sentinel = empty_image_sentinel
    except NameError:
        sentinel = None
    if sentinel is not None and hasattr(sentinel, "shape"):
        try:
            sentinel_digest, _ = _vip_image_digest(sentinel)
        except Exception:
            sentinel_digest = None
    def _is_empty_image(img):
        if _vip_is_missing(img):
            return True
        if sentinel_digest:
            try:
                d, _ = _vip_image_digest(img)
            except Exception:
                return True
            if d == sentinel_digest:
                return True
        return False
    g = globals()
    for i in range(1, 10):
        img = g.get("ref_image_" + str(i))
        if _is_empty_image(img):
            continue
        fname, binding = _vip_encode_image(img, "vip_img" + str(i))
        values["image_" + str(i)] = fname
        bindings["image_" + str(i)] = binding
    for i in range(1, 4):
        vid = g.get("ref_video_" + str(i))
        if _vip_is_missing(vid) or not hasattr(vid, "shape"):
            continue
        fname, binding = _vip_encode_video(vid, "vip_vid" + str(i))
        values["video_" + str(i)] = fname
        bindings["video_" + str(i)] = binding
    for i in range(1, 4):
        aud = g.get("ref_audio_" + str(i))
        if _vip_is_missing(aud):
            continue
        fname, binding = _vip_encode_audio(aud, "vip_aud" + str(i))
        values["audio_" + str(i)] = fname
        bindings["audio_" + str(i)] = binding
    n_img = sum(1 for i in range(1, 10) if values["image_" + str(i)])
    n_vid = sum(1 for i in range(1, 4) if values["video_" + str(i)])
    n_aud = sum(1 for i in range(1, 4) if values["audio_" + str(i)])
    # Character file occupies 1 video budget. Ordinary videos max 2 when file mode is on.
    if n_vid > 3 - int(use is True) - int(prod):
        raise ValueError("VIP_VIDEO_BUDGET_CHARACTER_ALLOWS_MAX_2_ORDINARY_VIDEOS" if not prod else "VIP_VIDEO_BUDGET_PERSON_PRODUCT_ALLOWS_MAX_1_ORDINARY_VIDEO")
    scene_slot = None
    try:
        scene = scene_image
    except NameError:
        scene = None
    if not _is_empty_image(scene):
        for i in range(1, 10):
            if not values["image_" + str(i)]:
                scene_slot = i
                break
        if scene_slot is None:
            raise ValueError("VIP_SCENE_NO_FREE_IMAGE_SLOT")
        fname, binding = _vip_encode_image(scene, "vip_scene")
        values["image_" + str(scene_slot)] = fname
        bindings["image_" + str(scene_slot)] = binding
        n_img += 1
    mixed = n_img + n_vid + n_aud + int(use is True) + int(prod)
    if mixed > 12:
        raise ValueError("VIP_MIXED_REF_BUDGET_EXCEEDED")
    values["input_bindings_json"] = json.dumps(bindings, separators=(",", ":")) if bindings else "{}"
    if prod:
        return _vip_product_bundle(values, model_prompt, scene_slot, use is True)
    preface = "subject_definitions:\n{{character_ref}}: 本镜人物身份与外貌只来自人物一致性文件，不要换成其他人。\n"
    preface += "台词约束：只说出提示词里已经写明的台词原文，不要增删、重复或改写任何字词，不要插入台词之外的音节、语气词或口头禅。句与句之间只按提示词标注的停顿保持静音，静音期间不要出声。\n"
    preface += "画面约束：桌面和画面中不要出现任何道具（包括手机、杯子、文具或其他可拿的物品），双手保持空着，桌面保持空手。\n"
    if scene_slot is not None:
        preface += "<Picture %d>: 本镜场景环境参考，只使用其中的背景、空间、陈设和光线；人物身份与外貌只来自人物一致性文件，不要出现场景图里的任何人物。\n" % scene_slot
    values["generation_prompt"] = preface + model_prompt
    return _maxapi_safe_bundle(**values)
# RefMod reference assets; NOT LoRA training. Original core/common: MIT, Luisa2026.
def _dual_run(**values):
    from .refmod_pinned import bridge, reference_joint, runtime_joint
    core_source = _pinned_core_bytes()
    values = dict(values)
    values["prompt"] = values.pop("generation_prompt")
    files = {key: values.pop(key) for key in list(values) if key.startswith(("image_", "audio_", "video_")) and key.rsplit("_", 1)[-1].isdigit()}
    return runtime_joint.generate_dual_conditioning(
        bridge, reference_joint, core_source,
        values.pop("clip"), values.pop("vae"), values.pop("audio_vae"), files=files, **values)
# Strict fixed34-control contract. Function-only source is safe to embed in the
# private IDE code namespace; no module globals, imports, files or models at load.

def _dual_normalize_controls(values):
    import math
    import re
    bool_fields = {'use_character', 'use_video_soundtracks', 'use_product'}
    int_fields = {'product_bytes', 'character_bytes', 'width', 'height', 'length', 'max_ref_tokens', 'max_packed_tokens'}
    float_fields = {'strength'}
    string_fields = {
        'product_base64', 'product_sha256', 'product_owner_tag', 'character_file', 'character_transport', 'character_base64',
        'character_sha256', 'character_owner_tag', 'owner_tag', 'job_id',
        'input_bindings_json', 'generation_prompt', 'ref_image_size',
        'image_1', 'image_2', 'image_3', 'image_4', 'image_5',
        'image_6', 'image_7', 'image_8', 'image_9',
        'audio_1', 'audio_2', 'audio_3', 'video_1', 'video_2', 'video_3'}
    model_fields = {'clip', 'vae', 'audio_vae'}
    expected = bool_fields | int_fields | float_fields | string_fields | model_fields
    if type(values) is not dict or set(values) != expected:
        raise ValueError('Exactly39 fixed controls and3 model objects are required')
    result = dict(values)  # Shallow copy: actual model and string identities remain.
    converted = []
    for name in sorted(bool_fields):
        value = values[name]
        if type(value) is bool:
            continue
        if type(value) is str and value in ('true', 'false'):
            result[name] = value == 'true'
            converted.append(name)
        else:
            raise ValueError('Strict Boolean token required for ' + name)
    for name in sorted(int_fields):
        value = values[name]
        if type(value) is int and value >= 0:
            continue
        if type(value) is str and re.fullmatch(r'(?:0|[1-9][0-9]*)', value):
            result[name] = int(value)
            converted.append(name)
        else:
            raise ValueError('Canonical nonnegative integer required for ' + name)
    for name in sorted(float_fields):
        value = values[name]
        if type(value) is str:
            if re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value) is None:
                raise ValueError('Strict JSON number required for ' + name)
        elif type(value) not in (int, float):
            raise ValueError('Finite number excluding Boolean required for ' + name)
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise ValueError('Finite number required for ' + name) from None
        if not math.isfinite(number):
            raise ValueError('Finite number required for ' + name)
        result[name] = number
        if type(value) is not float:
            converted.append(name)
    for name in string_fields:
        if type(values[name]) is not str:
            raise ValueError('String required without rewriting for ' + name)
    for name in model_fields:
        if result[name] is not values[name]:
            raise AssertionError('Model identity changed')
    return result, sorted(converted)

"""Embedded IDE helper: one result object per node; no registration changes."""

def _dual_control_binding(values):
    import hashlib
    import json
    controls = {key:value for key,value in values.items()
                if key not in ('clip','vae','audio_vae')}
    if len(controls) != 39:
        raise ValueError('Exactly39 consumer controls required')
    json_types = {key:type(value).__name__ for key,value in sorted(controls.items())}
    base64_value = controls['character_base64']
    if type(base64_value) is not str:
        raise ValueError('Character base64 control must be a string')
    controls['character_base64'] = {
        'sha256':hashlib.sha256(base64_value.encode('utf-8')).hexdigest(),
        'chars':len(base64_value)}
    raw = json.dumps(controls,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return {'scheme':'single-socket-controls-v1','json_types':json_types,
            'sha256':hashlib.sha256(raw).hexdigest()}


def _dual_failure_bundle(error, values, binding=None):
    import json
    import traceback
    from .rejection import host_execution_blocker as _host_blocker
    ExecutionBlocker = _host_blocker()
    def scalar(name):
        value=values.get(name)
        return value if type(value) in (str,int,float,bool,type(None)) else {'received_type':type(value).__name__}
    report = {
        'success':False,'operation':'fresh_task_refmod_conditioning',
        'phase':'consumer_preparation','consumer_output_bridge':'single-socket-v2',
        'owner_tag':scalar('owner_tag'),'job_id':scalar('job_id'),
        'character_enabled':scalar('use_character'),
        'error_type':type(error).__name__,'error':str(error)[:2048],
        'traceback':[{'file':frame.filename.replace('\\','/').rsplit('/',1)[-1],
                      'line':frame.lineno,'function':frame.name}
                     for frame in traceback.extract_tb(error.__traceback__,limit=-12)],
        'request_control_binding':binding,
        'transport_control_binding':None,
        'api_input_normalization':{'scheme':'rh-strict-json-scalars-v1','converted_fields':[],'applied':False},
        'sampling_started':False,'actual_video_produced':False,
        'model_weights_trained':False}
    return {'positive':ExecutionBlocker(None),'latent':ExecutionBlocker(None),
            'report':json.dumps(report,ensure_ascii=False,indent=2),'video_prefix':''}


def _dual_safe_bundle(**values):
    import json
    binding = None
    transport_binding = None
    normalized = values
    normalization = {'scheme':'rh-strict-json-scalars-v1','converted_fields':[],'applied':False}
    try:
        transport_binding = _dual_control_binding(values)
        normalized, converted = _dual_normalize_controls(values)
        normalization = {'scheme':'rh-strict-json-scalars-v1','converted_fields':converted,'applied':True}
        binding = _dual_control_binding(normalized)
        positive, latent, text, video_prefix = _dual_run(**normalized)
        report = json.loads(text)
        if type(report) is not dict or report.get('success') is not True:
            raise ValueError('Conditioning helper did not return a successful report')
        report['request_control_binding'] = binding
        report['transport_control_binding'] = transport_binding
        report['api_input_normalization'] = normalization
        report['consumer_output_bridge'] = 'single-socket-v2'
        return {'positive':positive,'latent':latent,
                'report':json.dumps(report,ensure_ascii=False,indent=2),
                'video_prefix':video_prefix}
    except Exception as error:
        bundle = _dual_failure_bundle(error,normalized,binding)
        report = json.loads(bundle['report'])
        report['transport_control_binding'] = transport_binding
        report['api_input_normalization'] = normalization
        bundle['report'] = json.dumps(report,ensure_ascii=False,indent=2)
        raise


def _vip_product_bundle(values, model_prompt, scene_slot, person_on):
    # Person + product (or product only): ONE joint encode of both RefMod assets via the 665 dual layer.
    # Constraints are English statements outside any <d> block so they are not spoken.
    import base64 as _b64, hashlib as _hl
    pb = product_base64
    ps = product_sha256
    pn = product_bytes
    if type(pn) is str and pn.isdigit():
        pn = int(pn)
    if type(pb) is not str or pb in ("", "None", "(none)") or type(ps) is not str or len(ps) != 64 or type(pn) is not int or pn <= 0:
        raise ValueError("VIP_PRODUCT_BASE64_BINDING_REQUIRED")
    raw = _b64.b64decode(pb, validate=True)
    if len(raw) != pn or _hl.sha256(raw).hexdigest() != ps:
        raise ValueError("VIP_PRODUCT_BINDING_MISMATCH")
    if person_on and ps == values["character_sha256"]:
        raise ValueError("VIP_ONE_FILE_CANNOT_BE_PERSON_AND_PRODUCT")
    owner = values["owner_tag"]
    lines = ["subject_definitions:"]
    if person_on:
        lines.append("{{person_ref}} is <Subject 1>, the only person in the video. Face, hair, body and clothing come only from {{person_ref}} and stay unchanged for the whole shot; the person is never replaced.")
    lines.append("{{product_ref}} is the product held and shown by <Subject 1>. Its shape, color, buttons, materials and printed details come only from {{product_ref}} and stay unchanged; it is the only handheld object, held naturally in one hand.")
    lines.append("No subtitles, captions, explanatory text or titles appear at any time. All spoken language is heard only, never rendered as text.")
    lines.append("Mouth logic: the lips open only while an assigned line is being spoken, with clearly visible mouth movement matching each syllable; as soon as each line ends the lips close and stay closed during every pause and every gesture, until the next assigned line begins.")
    lines.append("Only the assigned lines are spoken, word for word; no extra words, syllables or filler sounds.")
    if scene_slot is not None:
        lines.append("<Picture %d>: environment reference only (background, room layout and lighting); no person from <Picture %d> appears." % (scene_slot, scene_slot))
    v = dict(values)
    v["generation_prompt"] = "\n".join(lines) + "\n" + model_prompt
    v.update(use_product=True, product_base64=pb, product_sha256=ps, product_bytes=pn, product_owner_tag=owner)
    return _dual_safe_bundle(**v)



# ===== 多窗联合编码驱动（循环外运行；每窗：人物资产RefMod + 商品资产RefMod + 本窗场景图 + 本窗提示词）=====
# 不接上一窗末帧；资产 latent 直接作为参考块（不解码成 PNG 再编码）。
# 只在循环外执行一次（所有输入都不依赖 forLoopStart），因此不会碰到 IDENode 循环 unique_id 问题。
def _vip_mw_main():
    import builtins, json, re, traceback
    g = globals()
    rep = {"schema": "vip-mw-joint-v1", "windows": []}
    _mw_report = None

    def _flag(v):
        if type(v) is str and v in ("true", "false"):
            return v == "true"
        return v is True

    use = _flag(use_character)
    try:
        prod = _flag(use_product)
    except NameError:
        prod = False
    if not (use or prod):
        rep["skipped"] = "no_person_or_product_asset"
        _mw_report = json.dumps(rep, ensure_ascii=False)
        return {"positive": [], "report": _mw_report}

    plan = json.loads(plan_json) if type(plan_json) is str else plan_json
    if type(plan) is not dict:
        raise ValueError("VIP_MW_PLAN_NOT_JSON")
    segs = plan.get("segments") or []
    count = int(plan.get("count") or len(segs))
    wc = int(window_count)
    if count != wc or len(segs) != count:
        raise ValueError("VIP_MW_PLAN_COUNT_MISMATCH:%s/%s/%s" % (count, wc, len(segs)))
    if not 1 <= count <= 10:
        raise ValueError("VIP_MW_WINDOW_COUNT_UNSUPPORTED:%d" % count)

    sentinel_digest = None
    try:
        sentinel = empty_image_sentinel
    except NameError:
        sentinel = None
    if sentinel is not None and hasattr(sentinel, "shape"):
        try:
            sentinel_digest, _ = _vip_image_digest(sentinel)
        except Exception:
            sentinel_digest = None

    def _img_empty(img):
        if _vip_is_missing(img) or not hasattr(img, "shape"):
            return True
        if sentinel_digest:
            try:
                d, _ = _vip_image_digest(img)
            except Exception:
                return True
            if d == sentinel_digest:
                return True
        return False

    def _aud_empty(a):
        if _vip_is_missing(a) or type(a) is not dict:
            return True
        w = a.get("waveform")
        return not hasattr(w, "shape")

    def _vid_empty(v):
        return _vip_is_missing(v) or not hasattr(v, "shape")

    def _get(name):
        try:
            return g[name]
        except KeyError:
            return None

    # 用户原槽位（原编号）→ 实际存在的才送进编码；提示词里 <Picture N>/<Audio N>/<Video N> 按原编号重排成连续编号
    imgs = [(i, _get("user_image_%d" % i)) for i in range(1, 10)]
    imgs = [(i, v) for i, v in imgs if not _img_empty(v)]
    auds = [(i, _get("user_audio_%d" % i)) for i in range(1, 4)]
    auds = [(i, v) for i, v in auds if not _aud_empty(v)]
    vids = [(i, _get("user_video_%d" % i)) for i in range(1, 4)]
    vids = [(i, v) for i, v in vids if not _vid_empty(v)]
    scenes = [_get("scene_image_%d" % i) for i in range(1, 5)]
    scenes = [v for v in scenes if not _img_empty(v)]
    n_scene = len(scenes)
    img_map = {orig: k + 1 for k, (orig, _) in enumerate(imgs)}
    aud_map = {orig: k + 1 for k, (orig, _) in enumerate(auds)}
    vid_map = {orig: k + 1 for k, (orig, _) in enumerate(vids)}
    rep.update(user_images=[o for o, _ in imgs], user_audios=[o for o, _ in auds],
               user_videos=[o for o, _ in vids], scene_images=n_scene, person=use, product=prod)

    def _remap(prompt):
        def sub(kind, table):
            def fn(m):
                n = int(m.group(1))
                if n not in table:
                    raise ValueError("VIP_MW_PROMPT_REFERS_TO_EMPTY_%s_SLOT:%d" % (kind.upper(), n))
                return "<%s %d>" % (kind, table[n])
            return fn
        prompt = re.sub(r"<Picture\s+(\d+)>", sub("Picture", img_map), prompt)
        prompt = re.sub(r"<Audio\s+(\d+)>", sub("Audio", aud_map), prompt)
        prompt = re.sub(r"<Video\s+(\d+)>", sub("Video", vid_map), prompt)
        return prompt

    def _inject(prompt, sentence):
        before = re.findall(r"<d>.*?</d>", prompt, flags=re.S)
        tok = "retention_analysis:"
        pos = prompt.find(tok)
        if pos >= 0:
            at = pos + len(tok)
            out = prompt[:at] + "\n" + sentence + "\n" + prompt[at:].lstrip("\n")
        else:
            out = sentence + "\n" + prompt
        if re.findall(r"<d>.*?</d>", out, flags=re.S) != before:
            raise ValueError("VIP_MW_DIALOGUE_CHANGED_BY_CONSTRAINTS")
        return out

    positives = []
    for i, seg in enumerate(segs):
        base = seg.get("prompt") or ""
        if type(base) is not str or not base.strip():
            raise ValueError("VIP_MW_WINDOW_PROMPT_EMPTY:%d" % i)
        frames = int(seg.get("model_frames") or 0)
        if frames < 5:
            raise ValueError("VIP_MW_WINDOW_FRAMES_INVALID:%d:%d" % (i, frames))
        prompt = _remap(base)
        primary = scenes[i % n_scene] if n_scene else None
        secondary = scenes[(i + 1) % n_scene] if n_scene >= 2 else None
        slot_imgs = [v for _, v in imgs]
        second_label = None
        if secondary is not None and len(slot_imgs) < 8:
            slot_imgs.append(secondary)
            second_label = len(slot_imgs)
        primary_label = (len(slot_imgs) + 1) if primary is not None else None
        lines = ["MULTI-WINDOW SYSTEM CONSTRAINTS (never spoken, never narrated, never rendered as on-screen text):"]
        if i > 0:
            lines.append("This window opens on a new camera angle of the same scene, a deliberate cut; it does not continue from any previous frame.")
        if use:
            lines.append("The person is exactly the supplied character reference in every window: same face, hair, body and clothing; the person is never replaced.")
            lines.append("Clothing is only worn; it is never held up, hung on a hanger, laid out or presented as an item.")
            lines.append("The lips are closed on the first frame; they open only while a line in this window's dialogue tags is being spoken, close during every pause, and stay closed after the last line until the window ends.")
        if prod:
            lines.append("The product is exactly the supplied product reference in every window: same shape, color, buttons and printed details.")
        lines.append("Speak only this window's tagged dialogue lines, verbatim, once, in order; do not add, repeat or invent lines.")
        lines.append("No subtitles, captions, lower-thirds, title cards or burned-in text at any time.")
        if primary_label is not None:
            lines.append("The room is only the supplied environment reference; do not invent new furniture, walls, windows or a different room.")
        else:
            lines.append("No environment reference is supplied: keep the environment consistent with the character reference; do not invent a different room or add furniture, walls or windows that are not shown.")
        if second_label is not None:
            lines.append("<Picture %d>: another angle of the same room, environment reference only (background, layout, lighting); no person from <Picture %d> appears." % (second_label, second_label))
        prompt = _inject(prompt, " ".join(lines))
        for k in range(1, 10):
            g["ref_image_%d" % k] = slot_imgs[k - 1] if k <= len(slot_imgs) else None
        for k in range(1, 4):
            g["ref_audio_%d" % k] = auds[k - 1][1] if k <= len(auds) else None
            g["ref_video_%d" % k] = vids[k - 1][1] if k <= len(vids) else None
        g["scene_image"] = primary
        g["generation_prompt"] = prompt
        g["length"] = frames
        b = _vip_entry()
        if type(b) is not dict or "positive" not in b:
            raise ValueError("VIP_MW_WINDOW_ENCODE_NO_BUNDLE:%d" % i)
        pos = b["positive"]
        if type(pos) is str or not isinstance(pos, (list, tuple)) or not pos:
            raise ValueError("VIP_MW_WINDOW_POSITIVE_INVALID:%d:%s" % (i, type(pos).__name__))
        positives.append(pos)
        rep["windows"].append({"index": i, "frames": frames, "prompt_chars": len(prompt),
                               "scene_primary_label": primary_label, "scene_second_label": second_label,
                               "images": len(slot_imgs) + int(primary is not None),
                               "dialogue_tags": len(re.findall(r"<d>.*?</d>", prompt, flags=re.S))})
    rep["success"] = True
    _mw_report = json.dumps(rep, ensure_ascii=False)
    return {"positive": positives, "report": _mw_report}


def _vip_mw_safe():
    import builtins, json, traceback
    g = globals()
    try:
        return _vip_mw_main()
    except BaseException as e:
        _vip_record_private_reference_failure(e, "多窗人物、商品及参考素材处理阶段")
        msg = _vip_public_reference_failure(e, "多窗人物、商品及参考素材处理阶段")
        _mw_report = json.dumps({"success": False, "error": msg}, ensure_ascii=False)
        return {"positive": [], "error": msg, "report": _mw_report}
    finally:
        # 不把逐窗临时变量留在 IDENode 命名空间里（否则会变成额外输出）
        for k in ["scene_image", "generation_prompt", "length"] + ["ref_image_%d" % i for i in range(1, 10)] + ["ref_audio_%d" % i for i in range(1, 4)] + ["ref_video_%d" % i for i in range(1, 4)]:
            g.pop(k, None)

result = _vip_mw_safe()


def _vip_native_failure_bundle(message):
    class VipReferenceFailure(object):
        def __init__(self, public_message):
            self.public_message = public_message
        def _fail(self, *args, **kwargs):
            raise ValueError(self.public_message) from None
        __iter__ = _fail
        __getitem__ = _fail
        def __repr__(self):
            return self.public_message
        __str__ = __repr__
    failure = VipReferenceFailure(message)
    return {"positive": failure, "latent": failure, "report": message, "video_prefix": ""}

def _vip_entry_public_safe():
    try:
        return _vip_entry()
    except Exception as error:
        _vip_record_private_reference_failure(error, "人物、商品及参考素材准备阶段")
        message = _vip_public_reference_failure(error, "人物、商品及参考素材准备阶段")
        return _vip_native_failure_bundle(message)

def _prepare_call(inputs):
    from .host_boundary import coerce_dotted_unique_id
    values = dict(inputs)
    coerce_dotted_unique_id(values.pop("unique_id", None))
    if "idenode_loop_guard" in values:
        coerced = coerce_dotted_unique_id(values["idenode_loop_guard"])
        values["idenode_loop_guard"] = str(coerced) if type(coerced) is int else coerced
    return values


def _types(fields):
    return {
        "required": {name: (typ, {"forceInput": True}) for name, typ in fields},
        "hidden": {"unique_id": "UNIQUE_ID"},
    }


class PPCRefModSingle:
    """One character or a joint person+product encode. Photo mode does not encode."""

    _FIELDS = (
        ("clip", "CLIP"), ("vae", "VAE"), ("audio_vae", "VAE"),
        ("use_character", "BOOLEAN"), ("character_file", "STRING"),
        ("character_transport", "STRING"), ("character_base64", "STRING"),
        ("character_sha256", "STRING"), ("character_bytes", "INT"),
        ("generation_prompt", "STRING"), ("width", "INT"), ("height", "INT"), ("length", "INT"),
        ("scene_image", "IMAGE"),
        ("ref_image_1", "IMAGE"), ("ref_image_2", "IMAGE"), ("ref_image_3", "IMAGE"),
        ("ref_image_4", "IMAGE"), ("ref_image_5", "IMAGE"), ("ref_image_6", "IMAGE"),
        ("ref_image_7", "IMAGE"), ("ref_image_8", "IMAGE"), ("ref_image_9", "IMAGE"),
        ("ref_video_1", "IMAGE"), ("ref_video_2", "IMAGE"), ("ref_video_3", "IMAGE"),
        ("ref_audio_1", "AUDIO"), ("ref_audio_2", "AUDIO"), ("ref_audio_3", "AUDIO"),
        ("empty_image_sentinel", "IMAGE"), ("idenode_loop_guard", "STRING"),
        ("use_product", "BOOLEAN"), ("product_base64", "STRING"),
        ("product_sha256", "STRING"), ("product_bytes", "INT"),
    )

    @classmethod
    def INPUT_TYPES(cls):
        return _types(cls._FIELDS)

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Single or joint RefMod consumer. Photo mode returns blockers and does not encode."

    def run(self, **inputs):
        return (invoke(_vip_entry_public_safe, _prepare_call(inputs)),)


class PPCRefModMultiWindow:
    """One joint preparation pass per window. Person and product share that pass."""

    _FIELDS = (
        ("clip", "CLIP"), ("vae", "VAE"), ("audio_vae", "VAE"),
        ("use_character", "BOOLEAN"), ("character_file", "STRING"),
        ("character_transport", "STRING"), ("character_base64", "STRING"),
        ("character_sha256", "STRING"), ("character_bytes", "INT"),
        ("use_product", "BOOLEAN"), ("product_base64", "STRING"),
        ("product_sha256", "STRING"), ("product_bytes", "INT"),
        ("width", "INT"), ("height", "INT"), ("window_count", "INT"), ("plan_json", "STRING"),
        ("scene_image_1", "IMAGE"), ("scene_image_2", "IMAGE"),
        ("scene_image_3", "IMAGE"), ("scene_image_4", "IMAGE"),
        ("user_image_1", "IMAGE"), ("user_image_2", "IMAGE"), ("user_image_3", "IMAGE"),
        ("user_image_4", "IMAGE"), ("user_image_5", "IMAGE"), ("user_image_6", "IMAGE"),
        ("user_image_7", "IMAGE"), ("user_image_8", "IMAGE"), ("user_image_9", "IMAGE"),
        ("user_video_1", "IMAGE"), ("user_video_2", "IMAGE"), ("user_video_3", "IMAGE"),
        ("user_audio_1", "AUDIO"), ("user_audio_2", "AUDIO"), ("user_audio_3", "AUDIO"),
        ("empty_image_sentinel", "IMAGE"), ("idenode_loop_guard", "STRING"),
    )

    @classmethod
    def INPUT_TYPES(cls):
        return _types(cls._FIELDS)

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Multi-window RefMod consumer. Each window uses one encode call, not a second pass."

    def run(self, **inputs):
        return (invoke(_vip_mw_safe, _prepare_call(inputs)),)
