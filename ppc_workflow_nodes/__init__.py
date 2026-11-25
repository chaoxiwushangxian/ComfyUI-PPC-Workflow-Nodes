"""Fixed-function nodes. Import does not run a workflow or open a network connection."""

from .auto_duration_nodes import (
    PPCAutoDurationEstimate,
    PPCCausalPace,
    PPCClipTimingAssembly,
    PPCDialogueIntervalSplit,
    PPCDurationProjection,
    PPCEmptySceneScope,
    PPCFrameGridFit,
    PPCLongEstimateSplit,
    PPCNativeWindowSplit,
    PPCShotOpening,
    PPCShotScope,
    PPCTimingHints,
    PPCTimingProjectionApply,
    PPCWithoutVoiceDurationPlan,
)
from .adapter import PPCReferenceInputAdapter
from .clock_bridge import PPCClockBridge
from .duration_adjust import PPCCustomDuration, PPCSpeechEdgeTrim
from .guard import PPCResultGuard
from .measured_clock import (
    PPCClockToWindows,
    PPCDurationPlan,
    PPCExactLine,
    PPCMeasuredDialogueBind,
)
from .media import PPCMediaMissing
from .parser import PPCStoryboardParser
from .pause_policy import PPCPausePolicy
from .storyboard_normalize import PPCStoryboardNormalize
from .video_inventory import PPCVideoInventory
from .voice import PPCVoiceRoute
from .fixed_text_nodes import FIXED_TEXT_CLASS_MAPPINGS, FIXED_TEXT_DISPLAY
from .tranche5 import TRANCHE5_CLASS_MAPPINGS, TRANCHE5_DISPLAY

NODE_CLASS_MAPPINGS = {
    "PPCMediaMissing": PPCMediaMissing,
    "PPCVideoInventory": PPCVideoInventory,
    "PPCReferenceInputAdapter": PPCReferenceInputAdapter,
    "PPCStoryboardParser": PPCStoryboardParser,
    "PPCVoiceRoute": PPCVoiceRoute,
    "PPCResultGuard": PPCResultGuard,
    "PPCStoryboardNormalize": PPCStoryboardNormalize,
    "PPCPausePolicy": PPCPausePolicy,
    "PPCClockBridge": PPCClockBridge,
    "PPCClockToWindows": PPCClockToWindows,
    "PPCDurationPlan": PPCDurationPlan,
    "PPCMeasuredDialogueBind": PPCMeasuredDialogueBind,
    "PPCExactLine": PPCExactLine,
    "PPCCustomDuration": PPCCustomDuration,
    "PPCSpeechEdgeTrim": PPCSpeechEdgeTrim,
    "PPCDialogueIntervalSplit": PPCDialogueIntervalSplit,
    "PPCLongEstimateSplit": PPCLongEstimateSplit,
    "PPCNativeWindowSplit": PPCNativeWindowSplit,
    "PPCFrameGridFit": PPCFrameGridFit,
    "PPCWithoutVoiceDurationPlan": PPCWithoutVoiceDurationPlan,
    "PPCTimingHints": PPCTimingHints,
    "PPCCausalPace": PPCCausalPace,
    "PPCAutoDurationEstimate": PPCAutoDurationEstimate,
    "PPCDurationProjection": PPCDurationProjection,
    "PPCTimingProjectionApply": PPCTimingProjectionApply,
    "PPCClipTimingAssembly": PPCClipTimingAssembly,
    "PPCShotScope": PPCShotScope,
    "PPCEmptySceneScope": PPCEmptySceneScope,
    "PPCShotOpening": PPCShotOpening,
    **FIXED_TEXT_CLASS_MAPPINGS,
    **TRANCHE5_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PPCMediaMissing": "PPC Media Missing",
    "PPCVideoInventory": "PPC Video Inventory",
    "PPCReferenceInputAdapter": "PPC Reference Input Adapter",
    "PPCStoryboardParser": "PPC Storyboard Parser",
    "PPCVoiceRoute": "PPC Voice Route",
    "PPCResultGuard": "PPC Result Guard",
    "PPCStoryboardNormalize": "PPC Storyboard Normalize",
    "PPCPausePolicy": "PPC Pause Policy",
    "PPCClockBridge": "PPC Clock Bridge",
    "PPCClockToWindows": "PPC Clock To Windows",
    "PPCDurationPlan": "PPC Duration Plan",
    "PPCMeasuredDialogueBind": "PPC Measured Dialogue Bind",
    "PPCExactLine": "PPC Exact Line",
    "PPCCustomDuration": "PPC Custom Duration",
    "PPCSpeechEdgeTrim": "PPC Speech Edge Trim",
    "PPCDialogueIntervalSplit": "PPC Dialogue Interval Split",
    "PPCLongEstimateSplit": "PPC Long Estimate Split",
    "PPCNativeWindowSplit": "PPC Native Window Split",
    "PPCFrameGridFit": "PPC Frame Grid Fit",
    "PPCWithoutVoiceDurationPlan": "PPC Without Voice Duration Plan",
    "PPCTimingHints": "PPC Timing Hints",
    "PPCCausalPace": "PPC Causal Pace",
    "PPCAutoDurationEstimate": "PPC Auto Duration Estimate",
    "PPCDurationProjection": "PPC Duration Projection",
    "PPCTimingProjectionApply": "PPC Timing Projection Apply",
    "PPCClipTimingAssembly": "PPC Clip Timing Assembly",
    "PPCShotScope": "PPC Shot Scope",
    "PPCEmptySceneScope": "PPC Empty Scene Scope",
    "PPCShotOpening": "PPC Shot Opening",
    **FIXED_TEXT_DISPLAY,
    **TRANCHE5_DISPLAY,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
