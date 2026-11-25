"""Registration for the audited RefMod, identity, export, and audio-route nodes."""

from __future__ import annotations

from .audio_route import PPCFixed7801602
from .host_boundary import PPCExecutorBoundary
from .refmod_consumer import PPCRefModMultiWindow, PPCRefModSingle
from .identity_png import IDENTITY_NODES
from .native_export import PPCNativeExportVideo
from .refmod_bundle import (
    LATENT_INDEX_NODES,
    PPCConditioningRecover,
    PPCConditioningTypeGate,
    PPCRefModLatent,
    PPCRefModPositive,
    PPCRefModReportGate,
    WINDOW_NODES,
)
from .tranche5_data import TRANCHE5

TRANCHE5_CLASS_MAPPINGS = {
    "PPCFixed7801602": PPCFixed7801602,
    "PPCRefModSingle": PPCRefModSingle,
    "PPCRefModMultiWindow": PPCRefModMultiWindow,
    "PPCExecutorBoundary": PPCExecutorBoundary,
    "PPCRefModPositive": PPCRefModPositive,
    "PPCRefModLatent": PPCRefModLatent,
    "PPCRefModReportGate": PPCRefModReportGate,
    "PPCConditioningTypeGate": PPCConditioningTypeGate,
    "PPCConditioningRecover": PPCConditioningRecover,
    "PPCNativeExportVideo": PPCNativeExportVideo,
}
TRANCHE5_CLASS_MAPPINGS.update({f"PPCRefModWindow{index}": node for index, node in WINDOW_NODES.items()})
TRANCHE5_CLASS_MAPPINGS.update(
    {f"PPCRefModLatentIndex{index}": node for index, node in LATENT_INDEX_NODES.items()}
)
TRANCHE5_CLASS_MAPPINGS.update({f"PPCIdentityPng{index}": node for index, node in IDENTITY_NODES.items()})

TRANCHE5_DISPLAY = {name: name for name in TRANCHE5_CLASS_MAPPINGS}
TRANCHE5_BY_ID = {item["id"]: item for item in TRANCHE5}

RESIDUAL_EXECUTORS = ()
