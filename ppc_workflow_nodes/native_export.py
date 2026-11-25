"""Deliver one native audio+video file without prompt or workflow metadata.

SaveVideo's format, codec, and quality arguments are forwarded. metadata is
forced to None. The delivered bytes must match the single native encode:
frame count, frame rate, dimensions, packet payload, and packet timing.
A failed check leaves no delivered file. This is not a metadata-stripping
rename of an unchecked file.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from fractions import Fraction
from pathlib import Path

_MESSAGE = (
    "PPC_OUTPUT_INTEGRITY_FAILED: 本次输出未通过完整音画或附带数据检查，"
    "已停止交付。请保留任务号联系支持，请勿直接重复生成。"
)
_DELEGATED = {
    "get_dimensions",
    "get_frame_count",
    "get_frame_rate",
    "get_components",
    "get_duration",
    "get_stream_source",
    "get_container_format",
    "get_active_trim_window",
}


def safe_tags(tags, stream=False):
    permitted = (
        {"language", "handler_name", "vendor_id", "encoder"}
        if stream
        else {"major_brand", "minor_version", "compatible_brands", "encoder", "creation_time"}
    )
    for key, value in tags.items():
        key = str(key).lower()
        value = str(value)
        assert key in permitted and len(value) <= 128, "PRIVATE_METADATA_PRESENT"
        if key == "encoder":
            assert value.startswith(("Lavf", "Lavc")), "UNEXPECTED_ENCODER_TAG"
        if key == "minor_version":
            assert value.isascii() and value.isdecimal(), "UNEXPECTED_VERSION_TAG"
        if key in ("major_brand", "compatible_brands"):
            assert re.fullmatch(r"[A-Za-z0-9 ]{1,64}", value), "UNEXPECTED_BRAND_TAG"
        if key == "creation_time":
            assert re.fullmatch(r"[0-9TZ:.+\-]{1,40}", value), "UNEXPECTED_TIME_TAG"
        if key == "language":
            assert re.fullmatch(r"[a-z]{3}", value), "UNEXPECTED_LANGUAGE_TAG"
        if key == "handler_name":
            assert value in ("VideoHandler", "SoundHandler", "SubtitleHandler", "Handler"), "UNEXPECTED_HANDLER_TAG"
        if key == "vendor_id":
            assert value in ("[0][0][0][0]", "\x00\x00\x00\x00", "0000", "FFMP"), "UNEXPECTED_VENDOR_TAG"


def clock(value, base):
    return None if value is None else str(Fraction(value) * base)


def fingerprint(path):
    import av

    with av.open(path) as container:
        safe_tags(container.metadata)
        streams = list(container.streams)
        assert len(streams) == 2 and {stream.type for stream in streams} == {"video", "audio"}, "COMPLETE_AV_REQUIRED"
        result = {}
        lookup = {}
        for stream in streams:
            safe_tags(stream.metadata, True)
            codec = stream.codec_context
            item = {
                "codec": codec.name,
                "extra": hashlib.sha256(bytes(codec.extradata or b"")).hexdigest(),
                "start": clock(stream.start_time, stream.time_base),
                "packets": 0,
                "payload": hashlib.sha256(),
                "timing": hashlib.sha256(),
            }
            if stream.type == "video":
                item.update(width=codec.width, height=codec.height, rate=str(stream.average_rate), frames=int(stream.frames))
            else:
                item.update(sample_rate=codec.sample_rate, channels=len(codec.layout.channels))
            result[stream.type] = item
            lookup[stream.index] = stream.type
        for packet in container.demux():
            if not packet.size:
                continue
            item = result[lookup[packet.stream.index]]
            item["packets"] += 1
            item["payload"].update(bytes(packet))
            ticks = (
                clock(packet.pts, packet.time_base),
                clock(packet.dts, packet.time_base),
                clock(packet.duration, packet.time_base),
            )
            item["timing"].update(repr(ticks).encode("ascii"))
        for item in result.values():
            assert item["packets"] > 0, "EMPTY_AV_TRACK"
            item["payload"] = item["payload"].hexdigest()
            item["timing"] = item["timing"].hexdigest()
        return result


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _public_reason(error):
    reason = error.args[0] if error.args else None
    if type(reason) is str and re.fullmatch(r"[A-Z_]{1,64}", reason):
        return reason
    return "INTERNAL_VALIDATION_ERROR"


class NativeExportVideo:
    def __init__(self, video):
        self._video = video
        self.ppc_report = {"ok": False, "state": "not_saved"}

    def __repr__(self):
        return "PPC_NATIVE_EXPORT_VIDEO"

    def __getattr__(self, name):
        if name not in _DELEGATED:
            raise AttributeError(name)
        return getattr(self._video, name)

    def save_to(self, path, *args, **kwargs):
        import folder_paths

        reference = None
        complete = False
        temp_root = os.path.realpath(folder_paths.get_temp_directory())
        try:
            output = os.path.realpath(os.fspath(path))
            root = os.path.realpath(folder_paths.get_output_directory())
            assert os.path.commonpath((output, root)) == root, "OUTPUT_PATH_SCOPE"
            assert not os.path.exists(output), "OUTPUT_ALREADY_EXISTS"
            expected_frames = int(self._video.get_frame_count())
            expected_dimensions = tuple(self._video.get_dimensions())
            assert expected_frames > 0, "EMPTY_SOURCE_VIDEO"
            source_encoded = None
            video_type = type(self._video)
            if video_type.__module__ == "comfy_api.latest._input_impl.video_types" and video_type.__name__ == "VideoFromFile":
                trim = getattr(self._video, "get_active_trim_window", lambda: (0, 0))()
                if not any(trim):
                    source_encoded = fingerprint(self._video.get_stream_source())
            descriptor, reference = tempfile.mkstemp(
                prefix="ppc_export_native_",
                suffix=os.path.splitext(output)[1] or ".mp4",
                dir=temp_root,
            )
            os.close(descriptor)
            native_kwargs = dict(kwargs)
            native_kwargs["metadata"] = None
            self._video.save_to(reference, *args, **native_kwargs)
            before = fingerprint(reference)
            native_sha = file_hash(reference)
            assert before["video"]["frames"] == expected_frames, "SOURCE_FRAME_COUNT_CHANGED"
            # PyAV prints an integer rate as "8/1"; Fraction(8) prints "8".
            # The original string compare rejected an unchanged rate. Compare the rationals.
            assert Fraction(before["video"]["rate"]) == Fraction(self._video.get_frame_rate()), "SOURCE_FRAME_RATE_CHANGED"
            assert (before["video"]["width"], before["video"]["height"]) == expected_dimensions, "SOURCE_DIMENSIONS_CHANGED"
            if source_encoded is not None:
                assert all(
                    source_encoded[key]["payload"] == before[key]["payload"]
                    and source_encoded[key]["packets"] == before[key]["packets"]
                    for key in ("video", "audio")
                ), "SOURCE_MEDIA_PAYLOAD_CHANGED"
            shutil.copyfile(reference, output)
            after = fingerprint(output)
            output_sha = file_hash(output)
            assert native_sha == output_sha and before == after, "AV_PACKET_OR_TIMELINE_CHANGED"
            self.ppc_report = {
                "ok": True,
                "version": "ppc_native_export_copy_v2",
                "nativeEncoderCalls": 1,
                "metadataArgumentOmitted": True,
                "nativeEncodedSha256": native_sha,
                "deliveredNativeSha256": output_sha,
                "byteExactCopy": True,
                "tracks": after,
                "sourceEncodedPayloadChecked": source_encoded is not None,
                "sourceTracks": source_encoded,
                "sourceExpectedFrames": expected_frames,
            }
            complete = True
        except Exception as error:
            reason = _public_reason(error)
            self.ppc_report = {
                "ok": False,
                "version": "ppc_native_export_copy_v2",
                "reason": reason,
                "category": type(error).__name__,
            }
            raise ValueError(_MESSAGE + " [" + reason + "]") from None
        finally:
            if complete and reference:
                assert os.path.dirname(os.path.realpath(reference)) == temp_root
                assert os.path.basename(reference).startswith("ppc_export_native_")
                try:
                    os.unlink(reference)
                except OSError:
                    self.ppc_report["temporaryCleanupDeferred"] = True
        return None


class PPCNativeExportVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"source_video": ("*", {"forceInput": True})}}

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Check a complete audio+video encode and copy those exact bytes. Prompt metadata is omitted."

    def run(self, source_video):
        return (NativeExportVideo(source_video),)
