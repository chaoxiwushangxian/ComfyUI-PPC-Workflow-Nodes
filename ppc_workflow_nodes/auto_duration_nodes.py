"""Explicit node classes for the automatic-duration compilers. No code input."""

from __future__ import annotations

from .auto_duration_plan import (
    run_dialogue_interval_split,
    run_frame_grid,
    run_long_estimate_split,
    run_native_windows,
    run_without_voice_plan,
)
from .auto_duration_scope import run_empty_scene_scope, run_shot_opening, run_shot_scope
from .auto_duration_text import run_clip_timing, run_duration_projection, run_projection_apply
from .auto_duration_timing import run_causal_pace, run_duration_estimate, run_timing_hints

_RUNNER = ("STRING", "STRING", "BOOLEAN")
_NAMES = ("result_text", "result_json", "has_error")


def _pair():
    return {
        "required": {
            "input_text": ("STRING", {"forceInput": True}),
            "input_json": ("STRING", {"forceInput": True}),
        }
    }


def _text_only():
    return {"required": {"input_text": ("STRING", {"forceInput": True})}}


class PPCDialogueIntervalSplit:
    """720010. Split a long without-voice line only when the original weight exceeds 95."""

    @classmethod
    def INPUT_TYPES(cls):
        return _text_only()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Split long without-voice dialogue by the original weight rule. Concatenation stays equal."

    def run(self, input_text):
        return run_dialogue_interval_split(input_text)


class PPCLongEstimateSplit:
    """720011."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Split an over-long without-voice estimate. Does not accept code."

    def run(self, input_text, input_json):
        return run_long_estimate_split(input_text, input_json)


class PPCNativeWindowSplit:
    """770008. Per-window 30s cap from the original compiler, not a forced film duration."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Build native windows from an existing estimate. Does not accept code."

    def run(self, input_text, input_json):
        return run_native_windows(input_text, input_json)


class PPCFrameGridFit:
    """720008."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fit pending windows onto the original 60-second frame grid."

    def run(self, input_text, input_json):
        return run_frame_grid(input_text, input_json)


class PPCWithoutVoiceDurationPlan:
    """500020."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Plan without-voice frames from estimated windows or the supplied selected seconds."

    def run(self, input_text, input_json):
        return run_without_voice_plan(input_text, input_json)


class PPCTimingHints:
    """720003."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Read authored clocks. Does not accept code."

    def run(self, input_text, input_json):
        return run_timing_hints(input_text, input_json)


class PPCCausalPace:
    """720007."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Attach pace and pause seconds already written in the prompt."

    def run(self, input_text, input_json):
        return run_causal_pace(input_text, input_json)


class PPCAutoDurationEstimate:
    """720001. Default mode remains 自动时长."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Estimate without-voice duration from prompt hints. Does not force 30s or 120s."

    def run(self, input_text, input_json):
        return run_duration_estimate(input_text, input_json)


class PPCDurationProjection:
    """720002."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Project clocks outside dialogue tags."

    def run(self, input_text, input_json):
        return run_duration_projection(input_text, input_json)


class PPCTimingProjectionApply:
    """720006."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Apply a pending timing projection outside dialogue tags."

    def run(self, input_text, input_json):
        return run_projection_apply(input_text, input_json)


class PPCClipTimingAssembly:
    """720009."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Assemble clip timing. Dialogue tag contents stay byte-for-byte."

    def run(self, input_text, input_json):
        return run_clip_timing(input_text, input_json)


class PPCShotScope:
    """720004."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Scope one without-voice shot. Dialogue tags must match the input."

    def run(self, input_text, input_json):
        return run_shot_scope(input_text, input_json)


class PPCEmptySceneScope:
    """720005."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Narrow picture slots for an explicit empty scene."

    def run(self, input_text, input_json):
        return run_empty_scene_scope(input_text, input_json)


class PPCShotOpening:
    """720013."""

    @classmethod
    def INPUT_TYPES(cls):
        return _pair()

    RETURN_TYPES = _RUNNER
    RETURN_NAMES = _NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Rewrite only an opening cut cue. Dialogue tags must match the input."

    def run(self, input_text, input_json):
        return run_shot_opening(input_text, input_json)
