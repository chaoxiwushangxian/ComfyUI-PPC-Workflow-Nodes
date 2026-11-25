"""Node 500021. Build the measurement queue from storyboard rows.

Timing fields written here are queue placeholders. Measured seconds arrive later
on PPCClockToWindows and are not replaced by these placeholders.
"""

from __future__ import annotations

import json

from .serialize import pack_error, pack_success


def build_clock_bridge(raw: str):
    parsed = json.loads(raw)
    assert parsed["mode"] in ("with_voice", "without_voice"), "invalid_clock_mode"
    if parsed["mode"] == "with_voice":
        assert parsed["rows"], "missing_measured_clock"
    rows = []
    source_rows = parsed["rows"] if parsed["mode"] == "with_voice" else []
    for original in source_rows:
        row = dict(original)
        assert row["voice"] in parsed["inventory"]["audios"] and row["voice"] in (1, 2, 3), (
            "ambiguous_voice_ownership"
        )
        row.update(
            person=int(row["subject"]),
            speaker=str(row["subject"]),
            emotion=None,
            emotion_name="natural",
            rate=1.0,
            auto=True,
            fixed_total=120,
            deadline=120,
            start=0,
            end=None,
            last=row["source_block"] == len(parsed["rows"]) - 1,
            sentence_end=True,
            reference_windows={},
        )
        rows.append(row)
    result = {
        "count": len(rows),
        "rows": rows,
        "reference_windows": {},
        "source": parsed,
    }
    if parsed["mode"] == "without_voice":
        result["inactive"] = True
    result["clock_queue"] = json.dumps(
        {"queue": rows, "accepted": [], "timeline": [], "splits": 0, "attempts": 0},
        ensure_ascii=False,
    )
    return result


def run_clock_bridge(input_text, input_json=None):
    del input_json
    text = "" if input_text is None else input_text
    try:
        return pack_success(build_clock_bridge(text))
    except Exception as exc:
        return pack_error(exc)


class PPCClockBridge:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"input_text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Queue storyboard rows for measurement. Does not accept code."

    def run(self, input_text):
        return run_clock_bridge(input_text)
