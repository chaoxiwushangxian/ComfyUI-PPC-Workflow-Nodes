"""Fragment path check for node 414015.

The delivered form is always ``output/selflift_auto_segment_<name>.mp4``.
An absolute path is accepted only when ``PPC_FRAGMENT_ROOT`` is set and the
path is exactly ``<root>/<32 lowercase hex>/output/<that file>``. ``..`` and
URL-like paths are rejected. No deployment root is built into the package.
"""

from __future__ import annotations

import os
import re

_UNSAFE = re.compile(r"(^|/)\.\.(/|$)|://")
_RELATIVE = re.compile(r"output/(selflift_auto_segment_[A-Za-z0-9_-]+\.mp4)\Z")


def normalize_fragment_path(path):
    path = str(path).replace("\\", "/")
    if _UNSAFE.search(path):
        raise AssertionError("VIP_UNSAFE_FRAGMENT_PATH")
    relative = _RELATIVE.fullmatch(path)
    if relative:
        return path
    root = os.environ.get("PPC_FRAGMENT_ROOT", "").strip().replace("\\", "/").rstrip("/")
    if root and _UNSAFE.search(root) is None and "://" not in root:
        absolute = re.fullmatch(
            re.escape(root) + r"/[a-f0-9]{32}/output/(selflift_auto_segment_[A-Za-z0-9_-]+\.mp4)",
            path,
        )
        if absolute:
            return "output/" + absolute.group(1)
    raise AssertionError("VIP_UNRELATED_FRAGMENT_PATH")
