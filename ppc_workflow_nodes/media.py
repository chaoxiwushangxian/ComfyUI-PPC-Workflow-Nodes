"""Fixed replacement for IDENode media-absence checks (nodes 1300–1311)."""

from __future__ import annotations


def media_missing(value) -> bool:
    """Return true when an optional upload slot has no media.

    This follows the original predicate exactly, including its numeric check.
    ``False`` is an ``int`` and compares equal to ``0``, so it is treated as
    missing. ``True`` is not. Real image, audio, and tensor values are not
    coerced with ``bool(value)``. An unresolved prompt link is the two-item
    list ``[decimal-node-id-string, 0]``.
    """
    unresolved_link = (
        type(value) is list
        and len(value) == 2
        and type(value[0]) is str
        and value[0].isascii()
        and value[0].isdigit()
        and type(value[1]) is int
        and value[1] == 0
    )
    return (
        value is None
        or (isinstance(value, str) and value == "")
        or (isinstance(value, (int, float)) and value == 0)
        or unresolved_link
    )


class PPCMediaMissing:
    """optional_media -> result. True means the slot was not uploaded."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"optional_media": ("*",)}}

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Detect a missing optional media slot without running user code."

    def run(self, optional_media):
        return (media_missing(optional_media),)
