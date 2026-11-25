"""Pinned, in-process RefMod-v4 bridge; no node registration, network, or installer.

The caller is trusted workflow/server code. Scope and expected digests MUST come
from its authenticated asset binding, not customer-editable owner/path fields.
IDENode supplies real IMAGE/VAE objects and returns ordinary STRING reports and
an annotated output-file locator. RH execution/artifact collection is unproven.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import struct
import sys
import types
from dataclasses import dataclass
from pathlib import Path

COMMIT = "517e8c419a8584fbf69fceb487bc39d83e6a6ec8"
CORE_SHA256 = "e9a2a03e6402e93d95c94c4b15dd244847582c3f614ec43dd7465f5176f690d6"
COMMON_SHA256 = "893c5e8cce1c5d0bb0fc0fa7cd2bdb88707224267c40279a3c0dd96d531bdda4"
MAX_ASSET_BYTES = 16 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024
MAX_ASSET_TOKENS = 32768
MAX_IMAGE_BYTES = 128 * 1024 * 1024
MAX_ALL_IMAGE_BYTES = 512 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _integer(value, label, lo=1, hi=None):
    if type(value) is not int or value < lo or (hi is not None and value > hi):
        raise ValueError("invalid " + label)
    return value


def _digest(value):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValueError("expected lowercase SHA256")
    return value


def _json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def load_pinned_author(core_source: bytes):
    """Return the static core module after checking the pinned source hash.

    The bytes are provenance only. They are not compiled or executed.
    """
    if type(core_source) is not bytes or _sha(core_source) != CORE_SHA256:
        raise ValueError("pinned author source mismatch: core")
    from . import core as author
    return author


def _no_link(path: Path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("symlink/reparse point rejected")
    return info


def _relative(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or any(c in value for c in "\\:\x00"):
        raise ValueError("unsafe relative locator")
    parts = value.split("/")
    if any(not p or p in (".", "..") for p in parts):
        raise ValueError("unsafe relative locator")
    return tuple(parts)


def _contained(root: Path, relative: str, *, exists=True):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("trusted root is not a directory")
    p = root
    for part in _relative(relative):
        p = p / part
        if p.exists() or p.is_symlink():
            _no_link(p)
        elif exists:
            raise FileNotFoundError("exact authorized file is not materialized")
    resolved = p.resolve(strict=exists)
    if os.path.commonpath((str(root), str(resolved))) != str(root):
        raise ValueError("locator escaped trusted root")
    return p


@dataclass(frozen=True)
class JobScope:
    output_root: Path
    owner_tag: str
    job_id: str
    directory: Path

    @classmethod
    def create(cls, actual_output_root, server_owner_tag: str, server_job_id: str):
        """Trusted caller only. This is path isolation, NOT authentication."""
        if not HEX32.fullmatch(server_owner_tag) or not HEX32.fullmatch(server_job_id):
            raise ValueError("server scope must use opaque 32-hex identifiers")
        root = Path(actual_output_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("output root unavailable")
        p = root
        for part in ("maxapi_refmod_assets", server_owner_tag):
            p = p / part
            if not p.exists():
                p.mkdir(mode=0o700)
            if not stat.S_ISDIR(_no_link(p).st_mode):
                raise ValueError("scope ancestor is not a directory")
        p = p / server_job_id
        p.mkdir(mode=0o700, exist_ok=False)
        _no_link(p)
        return cls(root, server_owner_tag, server_job_id, p)

    def checked(self):
        expected = f"maxapi_refmod_assets/{self.owner_tag}/{self.job_id}"
        p = _contained(self.output_root, expected)
        if p != self.directory or not p.is_dir():
            raise ValueError("scope binding changed")
        return p

    def asset_path(self, sha256):
        return _contained(self.checked(), "asset_" + _digest(sha256) + ".safetensors", exists=False)


def inspect_asset_bytes(raw: bytes, *, max_tokens=MAX_ASSET_TOKENS):
    """Strict selected product subset: v4 FullReference eight-still stack."""
    if type(raw) is not bytes or not 9 <= len(raw) <= MAX_ASSET_BYTES:
        raise ValueError("asset size outside contract")
    _integer(max_tokens, "max_tokens", 1, MAX_ASSET_TOKENS)
    header_len = struct.unpack("<Q", raw[:8])[0]
    if not 2 <= header_len <= MAX_HEADER_BYTES or 8 + header_len >= len(raw):
        raise ValueError("invalid safetensors header size")
    header = _json(raw[8:8 + header_len])
    if type(header) is not dict or set(header) != {"__metadata__", "latent"}:
        raise ValueError("expected one native v4 latent tensor")
    tensor = header["latent"]
    if type(tensor) is not dict or set(tensor) != {"dtype", "shape", "data_offsets"}:
        raise ValueError("invalid tensor descriptor")
    shape = tensor["shape"]
    if tensor["dtype"] != "F16" or type(shape) is not list or len(shape) != 5:
        raise ValueError("expected F16 [1,24,8,H,W]")
    for dim in shape:
        _integer(dim, "tensor dimension", 1, 131072)
    if shape[:3] != [1, 24, 8] or shape[3] % 2 or shape[4] % 2:
        raise ValueError("expected eight-frame visual H3 latent")
    tokens = 8 * (shape[3] // 2) * (shape[4] // 2)
    if tokens > max_tokens:
        raise ValueError("asset exceeds visual token budget")
    tensor_bytes = 1 * 24 * 8 * shape[3] * shape[4] * 2
    offsets = tensor["data_offsets"]
    if type(offsets) is not list or len(offsets) != 2 or any(type(x) is not int for x in offsets):
        raise ValueError("invalid tensor offsets")
    if offsets != [0, tensor_bytes] or len(raw) != 8 + header_len + tensor_bytes:
        raise ValueError("tensor payload size or trailing bytes mismatch")
    embedded = header["__metadata__"]
    if type(embedded) is not dict or set(embedded) != {"refmod_meta"} or type(embedded["refmod_meta"]) is not str:
        raise ValueError("expected native refmod_meta")
    meta = _json(embedded["refmod_meta"])
    if type(meta) is not dict:
        raise ValueError("invalid RefMod metadata")
    for key, expected in {"_format_version": 4, "latent_t": 8, "latent_h": shape[3], "latent_w": shape[4], "optimize_steps": 0}.items():
        if type(meta.get(key)) is not int or meta[key] != expected:
            raise ValueError("metadata dimension/version mismatch: " + key)
    for key, expected in {"kind": "video", "mode": "encode", "source": "stack", "concept_type": "identity"}.items():
        if meta.get(key) != expected:
            raise ValueError("unsupported asset profile: " + key)
    if meta.get("refmod_config"):
        raise ValueError("foreign per-mod configuration unsupported in this profile")
    return {"sha256": _sha(raw), "bytes": len(raw), "shape": shape, "tokens": tokens,
            "metadata": meta, "format": "MiniMaxH3RefMod-v4", "kind": "video", "source_photos_attested": False}


def _read_exact(path: Path, expected_sha256: str, expected_bytes: int):
    _digest(expected_sha256)
    _integer(expected_bytes, "expected_bytes", 9, MAX_ASSET_BYTES)
    info = _no_link(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size != expected_bytes:
        raise ValueError("expected exact regular file size")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as f:
        opened = os.fstat(f.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size != expected_bytes:
            raise ValueError("opened file differs from binding")
        raw = f.read(expected_bytes + 1)
    if len(raw) != expected_bytes or _sha(raw) != expected_sha256:
        raise ValueError("asset digest/size mismatch")
    return raw


def _put_asset(scope: JobScope, raw: bytes, expected_sha256: str, expected_bytes: int):
    if len(raw) != expected_bytes or _sha(raw) != _digest(expected_sha256):
        raise ValueError("asset transfer binding mismatch")
    report = inspect_asset_bytes(raw)
    dest = scope.asset_path(expected_sha256)
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    _read_exact(dest, expected_sha256, expected_bytes)
    return report


def import_input_file(scope, trusted_input_root, server_relative_filename, expected_sha256, expected_bytes):
    """No search, implicit download, fallback prefix or model registration."""
    path = _contained(Path(trusted_input_root), server_relative_filename)
    raw = _read_exact(path, expected_sha256, expected_bytes)
    return _put_asset(scope, raw, expected_sha256, expected_bytes)


def import_base64(scope, encoded, expected_sha256, expected_bytes):
    """Alternative normal STRING-data transport; never interpreted as code."""
    _integer(expected_bytes, "expected_bytes", 9, MAX_ASSET_BYTES)
    if type(encoded) is not str or len(encoded) != 4 * ((expected_bytes + 2) // 3):
        raise ValueError("base64 length outside exact byte binding")
    raw = base64.b64decode(encoded, validate=True)
    return _put_asset(scope, raw, expected_sha256, expected_bytes)


def load_job_asset(scope, expected_sha256, expected_bytes, core_source, *, max_tokens=MAX_ASSET_TOKENS):
    """Returns the actual pinned author's H3RefMod, not a fake typed object."""
    path = scope.asset_path(expected_sha256)
    raw = _read_exact(path, expected_sha256, expected_bytes)
    info = inspect_asset_bytes(raw, max_tokens=max_tokens)
    author = load_pinned_author(core_source)
    mod = author.H3RefMod.load(str(path.with_suffix("")), device="cpu")
    import torch
    if list(mod.latent.shape) != info["shape"] or mod.latent.dtype != torch.float16 or not torch.isfinite(mod.latent).all().item():
        raise ValueError("native loaded tensor is invalid/nonfinite")
    if mod.token_count != info["tokens"]:
        raise ValueError("native token calculation mismatch")
    # Filesystem race exclusion depends on the job directory being OS-private.
    _read_exact(path, expected_sha256, expected_bytes)
    return mod


def _encode_eight(images, encode, resize, *, ref_resolution=1024, max_tokens=10240):
    """Small pure orchestration seam; injected callables are only for CPU tests."""
    import torch
    if not isinstance(images, (list, tuple)) or len(images) != 8:
        raise ValueError("exactly eight ordered IMAGE tensors required")
    _integer(ref_resolution, "ref_resolution", 256, 2048)
    _integer(max_tokens, "max_tokens", 1, MAX_ASSET_TOKENS)
    bindings, total_bytes = [], 0
    for index, image in enumerate(images, 1):
        if not isinstance(image, torch.Tensor) or image.dtype != torch.float32 or image.ndim != 4 or image.shape[0] != 1 or image.shape[3] != 3:
            raise ValueError("each IMAGE must be float32 [1,H,W,3]")
        if min(image.shape[1:3]) < 1 or image.numel() * image.element_size() > MAX_IMAGE_BYTES:
            raise ValueError("input image allocation outside budget")
        total_bytes += image.numel() * image.element_size()
        if total_bytes > MAX_ALL_IMAGE_BYTES or not torch.isfinite(image).all().item() or image.min().item() < 0 or image.max().item() > 1:
            raise ValueError("invalid/unbounded IMAGE input")
        pixel_sha = _sha(image.detach().cpu().contiguous().numpy().tobytes())
        bindings.append({"slot": index, "shape": list(image.shape), "dtype": "float32", "pixel_sha256": pixel_sha})
    if len({b["pixel_sha256"] for b in bindings}) != 8:
        raise ValueError("duplicate source pixels are not eight distinct sources")
    h, w = images[0].shape[1:3]
    scale = min(1.0, ref_resolution / min(h, w))
    canvas = (max(32, round(w * scale / 32) * 32), max(32, round(h * scale / 32) * 32))
    expected_h, expected_w = canvas[1] // 16, canvas[0] // 16
    tokens = 8 * (expected_h // 2) * (expected_w // 2)
    if tokens > max_tokens or canvas[0] * canvas[1] * 3 * 4 > MAX_IMAGE_BYTES:
        raise ValueError("eight-source canvas/token budget exceeded before VAE; no truncation")
    frames, source_shapes = [], []
    with torch.inference_mode():
        for image in images:
            pixels = resize(image, ref_resolution, canvas=canvas)
            z = encode(pixels)
            if not isinstance(z, torch.Tensor) or list(z.shape) != [1, 24, 1, expected_h, expected_w] or not torch.isfinite(z).all().item():
                raise ValueError("H3 VAE must emit one finite [1,24,1,H,W] latent per photo")
            z = z.detach().to(device="cpu", dtype=torch.float16)
            if not torch.isfinite(z).all().item():
                raise ValueError("fp16 conversion became nonfinite")
            frames.append(z)
            source_shapes.append(f"1x{expected_h}x{expected_w}")
        latent = torch.cat(frames, dim=2)
    return latent, bindings, source_shapes, tokens


def create_eight(scope, images, vae, core_source, common_source, *, ref_resolution=1024, max_tokens=10240):
    """Production entry: real H3 VAE; fixed FullReference/identity/stack/zero steps."""
    from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE
    if not isinstance(getattr(vae, "first_stage_model", None), MiniMaxH3VideoVAE):
        raise ValueError("real native H3 video VAE required")
    scope.checked()
    author = load_pinned_author(core_source)
    common = _pinned_module(common_source, COMMON_SHA256, "common")
    latent, bindings, shapes, tokens = _encode_eight(images, vae.encode, common.resize_ref,
                                                    ref_resolution=ref_resolution, max_tokens=max_tokens)
    mod = author.H3RefMod(name="character_" + scope.job_id, kind="video", latent=latent,
        latent_h=latent.shape[3], latent_w=latent.shape[4], latent_t=8, mode="encode", source="stack",
        source_shape=" +".join(shapes), pool=f"full-res {latent.shape[4]*16}x{latent.shape[3]*16}px (short-edge cap {ref_resolution}px)",
        optimize_steps=0, tags=["8 img, 0 vid"], description="Eight-photo identity reference cache", concept_type="identity")
    stage = _contained(scope.checked(), "new_asset.safetensors", exists=False)
    if stage.exists():
        raise FileExistsError("fresh job staging name already exists")
    mod.save(str(stage.with_suffix("")))
    raw = stage.read_bytes()
    info = inspect_asset_bytes(raw, max_tokens=max_tokens)
    dest = scope.asset_path(info["sha256"])
    if dest.exists():
        raise FileExistsError("content-addressed asset already exists")
    # Both resolved paths were checked inside this newly created private job.
    os.rename(stage, dest)
    _read_exact(dest, info["sha256"], info["bytes"])
    mod.path = str(dest.with_suffix(""))
    info.update({"source_bindings": bindings, "source_count": 8, "source_photos_attested": True,
                 "producer": "FullReference VAE cache; not LoRA", "author_commit": COMMIT,
                 "ordinary_reference_tokens_included": False, "truncation_allowed": False})
    return mod, info, annotated_output(scope, info["sha256"], info["bytes"])


def annotated_output(scope, expected_sha256, expected_bytes):
    p = scope.asset_path(expected_sha256)
    raw = _read_exact(p, expected_sha256, expected_bytes)
    inspect_asset_bytes(raw)
    return p.relative_to(scope.output_root).as_posix() + " [output]"
