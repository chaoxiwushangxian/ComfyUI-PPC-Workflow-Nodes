"""Node 500024. Read authored silent holds. Speech deadlines are not extra silence."""

from __future__ import annotations

import math
import re

from .serialize import pack_error, pack_success

_HOLD = re.compile(r"\b(?:silent|silence|pause|hold)\b|静默|停顿|无对白|无台词", re.I)
_DEADLINE = re.compile(
    r"(?:finish|speak|say)\s+(?:by|within)\s+[\d.]+\s+seconds?|[\d:]+前[说讲]完",
    re.I,
)
_SPAN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|–|到|至|to|and)\s*(\d+(?:\.\d+)?)\s*(?:seconds?|s\b|秒)",
    re.I,
)
_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(?:seconds?\b|s\b|秒)", re.I)


def _holds(text: str) -> float:
    clean = re.sub(r"<d>.*?</d>", "", text, flags=re.S)
    total = 0.0
    for line in re.split(r"[\n。;；]", clean):
        if not _HOLD.search(line):
            continue
        if " by " in line.lower() or " within " in line.lower() or "前说完" in line or "前讲完" in line:
            line = _DEADLINE.sub("", line)
        spans = _SPAN.findall(line)
        for start, end in spans:
            assert float(end) > float(start), "invalid_silent_hold"
            total += float(end) - float(start)
        if spans:
            line = _SPAN.sub("", line)
        values = _VALUE.findall(line)
        total += sum(float(value) for value in values)
    assert math.isfinite(total) and 0 <= total <= 120, "invalid_silent_hold"
    return total


def build_pause_policy(raw: str):
    plan = json_loads(raw)

    def apply_policy(parsed):
        if parsed["mode"] != "with_voice":
            return parsed
        starts = [shot.get("authored_start") for shot in parsed["shots"]]
        for index, shot in enumerate(parsed["shots"]):
            if shot["visual_only"]:
                start = shot.get("authored_start")
                end = shot.get("authored_end")
                seconds = end - start if start is not None and end is not None else _holds(shot["body"])
                if not seconds and index + 1 < len(starts) and starts[index] is not None and starts[index + 1] is not None:
                    seconds = starts[index + 1] - starts[index]
                assert math.isfinite(seconds) and 0 < seconds <= 120, "silent_hold_without_duration"
                shot["hold_seconds"] = seconds
            else:
                for row in shot["parts"]:
                    row["pause_before"] = _holds(row["action"])
                    row["pause_after"] = 0.0
                    parsed["rows"][row["source_block"]].update(
                        pause_before=row["pause_before"], pause_after=0.0
                    )
                tail = _holds(shot["tail"])
                shot["parts"][-1]["pause_after"] = tail
                parsed["rows"][shot["source_blocks"][-1]]["pause_after"] = tail
        return parsed

    return apply_policy(plan)


def json_loads(raw: str):
    import json

    return json.loads(raw)


def run_pause_policy(input_text, input_json=None):
    del input_json
    text = "" if input_text is None else input_text
    try:
        return pack_success(build_pause_policy(text))
    except Exception as exc:
        return pack_error(exc)


class PPCPausePolicy:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"input_text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Copy authored silent holds onto shot rows. Does not accept code."

    def run(self, input_text):
        return run_pause_policy(input_text)
