"""Typed RefMod bundle access. No embedded source and no model execution.

The encode kernels 9482009 and 9482140 stay residual: their conditioning path
is a sha256-pinned third-party pack executed with exec/compile. These functions
only perform the checks and selections that the surrounding scripts state
explicitly. Invalid bundles raise, so a string cannot be mistaken for
conditioning. Window failures stay objects whose iteration raises ValueError,
which is what the original window scripts returned.
"""

from __future__ import annotations

import builtins
import json

from .rejection import host_execution_blocker
from .serialize import pack_error, pack_success

_WINDOWS = "_VIP_CHAR_FILEMODE_WINDOWS"
_REPORT = "_VIP_CHAR_FILEMODE_REPORT"


class WindowFailure:
    def __init__(self, msg):
        self.msg = msg

    def _boom(self, *args, **kwargs):
        raise ValueError(self.msg)

    __iter__ = _boom
    __getitem__ = _boom

    def __repr__(self):
        return "VipMwFailure(%s)" % self.msg[:300]

    def __str__(self):
        return repr(self)


def pick_positive(bundle):
    if type(bundle) is not dict:
        raise ValueError("VIP_REFMOD_BUNDLE_INVALID")
    return bundle["positive"]


def pick_latent(bundle):
    if type(bundle) is not dict:
        raise ValueError("VIP_REFMOD_BUNDLE_INVALID")
    return bundle["latent"]


def pick_window(bundle, index):
    if type(bundle) is str:
        return WindowFailure("VIP_MW_ENCODER_RETURNED_STRING:" + bundle[:3000])
    if type(bundle) is not dict:
        return WindowFailure("VIP_MW_BUNDLE_INVALID:" + type(bundle).__name__)
    if bundle.get("error"):
        return WindowFailure(str(bundle.get("error"))[:3500])
    items = bundle.get("positive")
    if type(items) is not list:
        return WindowFailure("VIP_MW_BUNDLE_NO_POSITIVE_LIST")
    if not 0 <= index < len(items):
        return WindowFailure("VIP_MW_WINDOW_INDEX_OUT_OF_RANGE:%d/%d" % (index, len(items)))
    return items[index]


def pick_latent_index(bundle, index):
    store = getattr(builtins, _WINDOWS, None)
    items = None
    if type(store) is dict and type(store.get("latent")) is list and store.get("latent"):
        items = store["latent"]
    if items is None:
        if type(bundle) is not dict:
            raise ValueError("VIP_REFMOD_BUNDLE_INVALID")
        items = bundle["latent"]
        if type(items) is not list:
            items = [items]
    if index >= len(items):
        return host_execution_blocker()(None)
    return items[index]


def read_refmod_report():
    report = getattr(builtins, _REPORT, None)
    if type(report) is not str or not report.strip():
        raise ValueError("VIP_REFMOD_REPORT_MISSING")
    try:
        info = json.loads(report)
    except Exception:
        raise ValueError("VIP_REFMOD_REPORT_NOT_JSON:" + report[:1500])
    if type(info) is not dict or info.get("success") is not True:
        raise ValueError("VIP_REFMOD_FAILED:" + report[:2500])
    return "ok"


def conditioning_type_gate(value):
    kind = type(value).__name__
    if type(value) is str:
        raise ValueError("VIP_COND_IS_STR:" + value[:2500])
    if kind in ("int", "float", "bool", "NoneType", "dict", "bytes"):
        raise ValueError("VIP_COND_BADTYPE:" + kind)
    if type(value) not in (list, tuple):
        module = getattr(type(value), "__module__", "")
        raise ValueError("VIP_COND_BADTYPE:" + kind + ":" + module)
    if not value:
        raise ValueError("VIP_COND_EMPTY")
    item = value[0]
    if type(item) not in (list, tuple) or not item:
        raise ValueError("VIP_COND_BADITEM:" + type(item).__name__)
    head = item[0]
    head_kind = type(head).__name__
    if head_kind in ("str", "int", "float", "bool", "NoneType"):
        raise ValueError("VIP_COND_NOTENSOR:" + head_kind + ":" + str(head)[:400])
    return "ok:" + kind + ":" + type(item).__name__ + ":" + head_kind


def recover_conditioning(cond, idx):
    try:
        builtins._VIP_CHAR_FILEMODE_INDEX = int(idx)
    except Exception:
        builtins._VIP_CHAR_FILEMODE_INDEX = 0
    if type(cond) is not str:
        return cond
    store = getattr(builtins, _WINDOWS, None)
    index = getattr(builtins, "_VIP_CHAR_FILEMODE_INDEX", 0)
    try:
        index = int(index)
    except Exception:
        index = 0
    items = store.get("positive") if type(store) is dict else None
    if type(items) is list and 0 <= index < len(items) and type(items[index]) is not str:
        return items[index]
    shown = cond[:2500] if type(cond) is str else type(cond).__name__
    raise ValueError("VIP_COND_IS_STR:" + shown)


def _bundle_node(class_name, function):
    def run(self, bundle):
        return (function(bundle),)

    return type(
        class_name,
        (),
        {
            "INPUT_TYPES": classmethod(
                lambda cls: {"required": {"bundle": ("REFMOD_BUNDLE", {"forceInput": True})}}
            ),
            "RETURN_TYPES": ("*",),
            "RETURN_NAMES": ("result",),
            "FUNCTION": "run",
            "CATEGORY": "PPC/Workflow",
            "DESCRIPTION": "Select one typed value from a RefMod bundle.",
            "run": run,
        },
    )


PPCRefModPositive = _bundle_node("PPCRefModPositive", pick_positive)
PPCRefModLatent = _bundle_node("PPCRefModLatent", pick_latent)


def _window_node(index):
    class_name = "PPCRefModWindow%d" % index

    def run(self, bundle, _index=index):
        return (pick_window(bundle, _index),)

    return type(
        class_name,
        (),
        {
            "INPUT_TYPES": classmethod(
                lambda cls: {"required": {"bundle": ("REFMOD_BUNDLE", {"forceInput": True})}}
            ),
            "RETURN_TYPES": ("*",),
            "RETURN_NAMES": ("result",),
            "FUNCTION": "run",
            "CATEGORY": "PPC/Workflow",
            "DESCRIPTION": "Select window %d from bundle['positive'], or a failure object." % index,
            "WINDOW_INDEX": index,
            "run": run,
        },
    )


def _latent_index_node(index):
    class_name = "PPCRefModLatentIndex%d" % index

    def run(self, bundle=None, _index=index):
        return (pick_latent_index(bundle, _index),)

    return type(
        class_name,
        (),
        {
            "INPUT_TYPES": classmethod(
                lambda cls: {
                    "required": {},
                    "optional": {"bundle": ("REFMOD_BUNDLE", {"forceInput": True})},
                }
            ),
            "RETURN_TYPES": ("*",),
            "RETURN_NAMES": ("result",),
            "FUNCTION": "run",
            "CATEGORY": "PPC/Workflow",
            "DESCRIPTION": "Select latent index %d, or ExecutionBlocker when that window is absent." % index,
            "LATENT_INDEX": index,
            "run": run,
        },
    )


WINDOW_NODES = {index: _window_node(index) for index in range(10)}
LATENT_INDEX_NODES = {index: _latent_index_node(index) for index in range(1, 10)}


class PPCRefModReportGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Read the fixed RefMod report name and reject anything other than success JSON."

    def run(self):
        try:
            return pack_success(read_refmod_report())
        except Exception as exc:
            return pack_error(exc)


class PPCConditioningTypeGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"input_text": ("*",)}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Reject stringified conditioning. A nested non-scalar sequence passes."

    def run(self, input_text):
        try:
            return pack_success(conditioning_type_gate(input_text))
        except Exception as exc:
            return pack_error(exc)


class PPCConditioningRecover:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "cond": ("*",),
                "gate": ("STRING", {"forceInput": True}),
                "idx": ("INT", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Pass conditioning through, or recover one non-string window when the value was stringified."

    def run(self, cond=None, gate=None, idx=None):
        return (recover_conditioning(cond, idx),)
