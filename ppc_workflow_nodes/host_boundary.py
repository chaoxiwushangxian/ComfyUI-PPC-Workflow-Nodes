"""Local unique-id normalization. This does not patch builtins.

Node 9482017 used to replace builtins.int and builtins.__import__, then wrap
IDENode so a dotted Comfy id such as ``1.2.3`` survived ``int()``. Those
executors are gone. The linked guard input only needs a string, so this node
returns a status and leaves the process builtins unchanged. Dotted ids are
normalized only by ``coerce_dotted_unique_id``.
"""

from __future__ import annotations

import builtins
import re

from .serialize import pack_success

_DOTTED = re.compile(r"^\d+(?:\.\d+){2,}$")


def coerce_dotted_unique_id(value):
    if value is None:
        return value
    text = str(value)
    if _DOTTED.fullmatch(text):
        return int(text.split(".")[-1])
    return value


class PPCExecutorBoundary:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Report that no IDENode unique-id patch is installed. Builtins stay unchanged."

    def run(self, unique_id=None):
        if builtins.int is not int or builtins.__import__ is not __import__:
            raise RuntimeError("builtins were already patched")
        # Comfy injects UNIQUE_ID. Loop ids look like "12.0.1"; normalize here.
        self.last_unique_id = coerce_dotted_unique_id(unique_id)
        return pack_success("executor-free")
