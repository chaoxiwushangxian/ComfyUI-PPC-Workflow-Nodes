"""One identity frame as a PNG base64 string. The character pack is not pickle.

The on-disk layout is the one the original script reads: an 8-byte little-endian
header length, a JSON header, then a float16 payload addressed by data_offsets.
A path is accepted only inside the host input directory. The short-circuit for
a single window returns the original tiny PNG and does not open a file.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import struct
from pathlib import Path

TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGNsaGhgwAaYsIoOWgkAMBcBkGHHl6YAAAAASUVORK5CYII="
)


class IdentityFailure(str):
    def encode(self, *args, **kwargs):
        raise ValueError(str.__str__(self))


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _read_owned_pack(character_transport, character_base64, character_file, character_bytes, character_sha256):
    transport = character_transport.strip().lower() if isinstance(character_transport, str) else ""
    encoded = character_base64.strip() if isinstance(character_base64, str) else ""
    path = character_file.strip() if isinstance(character_file, str) else ""
    raw = None
    if transport == "base64" or encoded:
        raw = base64.b64decode(encoded)
    elif path:
        import folder_paths
        import os

        root = os.path.realpath(folder_paths.get_input_directory())
        candidate = os.path.realpath(os.path.join(root, path))
        if not candidate.startswith(root + os.sep):
            raise ValueError("VIP_CHAR_PATH_ESCAPE")
        raw = Path(candidate).read_bytes()
    if not raw:
        raise ValueError("VIP_CHAR_PACK_MISSING")
    expected = int(character_bytes or 0)
    if expected and len(raw) != expected:
        raise ValueError("VIP_CHAR_PACK_SIZE:%d!=%d" % (len(raw), expected))
    want = character_sha256.strip().lower() if isinstance(character_sha256, str) else ""
    if want and hashlib.sha256(raw).hexdigest() != want:
        raise ValueError("VIP_CHAR_PACK_SHA256")
    return raw


def identity_png(index, use_character, window_count, character_transport="", character_base64="",
                 character_file="", character_bytes=0, character_sha256="", vae=None):
    try:
        use = _as_bool(use_character)
        try:
            windows = int(window_count)
        except Exception:
            windows = 0
        if (not use) or windows <= 1:
            return TINY_PNG
        # Integrity is checked before importing torch so a bad digest cannot
        # depend on the host tensor library. The payload itself is still float16.
        raw = _read_owned_pack(
            character_transport, character_base64, character_file, character_bytes, character_sha256
        )
        header_length = struct.unpack_from("<Q", raw, 0)[0]
        if header_length > len(raw) - 8:
            raise ValueError("VIP_CHAR_PACK_TENSORS")
        header = json.loads(raw[8:8 + header_length])
        tensors = {key: value for key, value in header.items() if key != "__metadata__"}
        if len(tensors) != 1:
            raise ValueError("VIP_CHAR_PACK_TENSORS")
        desc = next(iter(tensors.values()))
        shape = list(desc.get("shape") or [])
        if desc.get("dtype") != "F16" or len(shape) != 5 or shape[0] != 1 or shape[1] != 24 or shape[2] < 1:
            raise ValueError("VIP_CHAR_PACK_SHAPE:" + str(shape))
        start, end = desc["data_offsets"]
        payload = raw[8 + header_length + start:8 + header_length + end]
        import numpy as np
        import torch
        from PIL import Image

        latent = torch.frombuffer(bytearray(payload), dtype=torch.float16).reshape(shape)
        frame_count = int(shape[2])
        frame = index if index < frame_count else frame_count - 1
        decoded = vae.decode(latent[:, :, frame:frame + 1].contiguous().float())
        if isinstance(decoded, dict) and "samples" in decoded:
            decoded = decoded["samples"]
        if hasattr(decoded, "sample") and not torch.is_tensor(decoded):
            decoded = decoded.sample
        if not torch.is_tensor(decoded):
            raise ValueError("VIP_CHAR_DECODE_TYPE:" + type(decoded).__name__)
        if decoded.ndim == 5:
            if decoded.shape[-1] in (3, 4):
                decoded = decoded.reshape(-1, decoded.shape[-3], decoded.shape[-2], decoded.shape[-1])
            elif decoded.shape[1] in (3, 4):
                decoded = decoded.permute(0, 2, 3, 4, 1).reshape(-1, decoded.shape[-2], decoded.shape[-1], decoded.shape[1])
            else:
                raise ValueError("VIP_CHAR_DECODE_RANK5:" + str(tuple(decoded.shape)))
        elif decoded.ndim == 4:
            if decoded.shape[-1] not in (3, 4) and decoded.shape[1] in (3, 4):
                decoded = decoded.permute(0, 2, 3, 1)
        elif decoded.ndim == 3:
            decoded = decoded.unsqueeze(0)
        else:
            raise ValueError("VIP_CHAR_DECODE_RANK:" + str(tuple(decoded.shape)))
        image = decoded[0, :, :, :3].detach().float().cpu()
        if float(image.max()) > 1.5:
            image = image / 255.0
        array = (image.clamp(0, 1).numpy() * 255.0 + 0.5).astype(np.uint8)
        if array.shape[0] < 16 or array.shape[1] < 16:
            raise ValueError("VIP_CHAR_DECODE_TINY:" + str(array.shape))
        buffer = io.BytesIO()
        Image.fromarray(array, "RGB").save(buffer, format="PNG", compress_level=1)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception as exc:
        return IdentityFailure("VIP_CHAR_IDENTITY_%d_FAILED:%s:%s" % (index, type(exc).__name__, str(exc)[:900]))


def _identity_node(index):
    class_name = "PPCIdentityPng%d" % index

    def run(self, use_character, character_file, character_transport, character_base64,
            character_sha256, character_bytes, vae, window_count, _index=index):
        return (identity_png(
            _index, use_character, window_count, character_transport, character_base64,
            character_file, character_bytes, character_sha256, vae,
        ),)

    return type(
        class_name,
        (),
        {
            "INPUT_TYPES": classmethod(lambda cls: {"required": {
                "use_character": ("BOOLEAN", {"forceInput": True}),
                "character_file": ("STRING", {"forceInput": True}),
                "character_transport": ("STRING", {"forceInput": True}),
                "character_base64": ("STRING", {"forceInput": True}),
                "character_sha256": ("STRING", {"forceInput": True}),
                "character_bytes": ("INT", {"forceInput": True}),
                "vae": ("VAE", {"forceInput": True}),
                "window_count": ("INT", {"forceInput": True}),
            }}),
            "RETURN_TYPES": ("*",),
            "RETURN_NAMES": ("result",),
            "FUNCTION": "run",
            "CATEGORY": "PPC/Workflow",
            "DESCRIPTION": "Identity frame %d as PNG base64. A single window returns the original tiny PNG." % index,
            "FRAME_INDEX": index,
            "run": run,
        },
    )


IDENTITY_NODES = {index: _identity_node(index) for index in range(8)}
