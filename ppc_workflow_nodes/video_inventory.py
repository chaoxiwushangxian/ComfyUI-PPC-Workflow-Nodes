"""Fixed replacement for the three-slot video frame inventory (node 99050007)."""

from __future__ import annotations


def no_video(frame_count) -> bool:
    """True unless frame_count is a real int greater than zero.

    ``bool`` is not an ``int`` under ``type(x) is int``, so ``True`` and
    ``False`` are both treated as no video. Floats are not accepted.
    """
    return type(frame_count) is not int or frame_count <= 0


def inventory_text(video_1_frames, video_2_frames, video_3_frames) -> str:
    return ",".join(
        (
            str(no_video(video_1_frames)).lower(),
            str(no_video(video_2_frames)).lower(),
            str(no_video(video_3_frames)).lower(),
        )
    )


class PPCVideoInventory:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_1_frames": ("*",),
                "video_2_frames": ("*",),
                "video_3_frames": ("*",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Report which of the three reference-video slots have no positive integer frame count."

    def run(self, video_1_frames, video_2_frames, video_3_frames):
        return (inventory_text(video_1_frames, video_2_frames, video_3_frames),)
