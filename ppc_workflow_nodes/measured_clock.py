"""Measured-clock nodes 500030, 500031, 730003, and 400275.

Window lengths come from the supplied timeline seconds. Dialogue text is compared,
not rewritten, except where a measured split already carries replacement text.
"""

from __future__ import annotations

import json
import math
import re

from .serialize import pack_error, pack_success

_AT_CLOCK = re.compile(r"\bAt\s+(\d+):(\d+(?:\.\d+)?)", re.I)


def _frames(seconds: float) -> int:
    count = max(5, int(math.ceil(seconds * 24)))
    return count + (5 - count % 17) % 17


def build_clock_windows(timeline_text: str, plan_text: str):
    timeline = json.loads(timeline_text)
    plan = json.loads(plan_text)
    if plan["mode"] != "with_voice":
        return {"measured_windows": [], "inactive": True}
    assert len(timeline) == len(plan["rows"]) and timeline, "missing_measured_clock"
    for index, (item, row) in enumerate(zip(timeline, plan["rows"])):
        assert item["source_block"] == index and all(
            item[key] == row[key] for key in ("shot", "subject", "voice", "text")
        ), "dialogue_changed"
    windows = []
    for shot in plan["shots"]:
        if shot["visual_only"]:
            remaining = float(shot["hold_seconds"])
            for _part in range(int(math.ceil(remaining / (719 / 24)))):
                seconds = min(remaining, 719 / 24)
                windows.append({"shot": shot["shot"], "source_blocks": [], "seconds": seconds})
                remaining -= seconds
            continue
        for index in shot["source_blocks"]:
            item = timeline[index]
            seconds = float(item["seconds"])
            assert math.isfinite(seconds) and seconds > 0 and _frames(seconds) <= 720, (
                "single_dialogue_block_over30"
            )
            previous = windows[-1] if windows else None
            merge = bool(previous and previous["shot"] == shot["shot"] and previous["source_blocks"])
            limit = 720
            if merge:
                left = plan["rows"][previous["source_blocks"][-1]]
                right = plan["rows"][index]
                if left.get("measured_sentence_window") or right.get("measured_sentence_window"):
                    merge = bool(
                        left.get("measured_sentence_window")
                        and right.get("measured_sentence_window")
                        and left["original_source_block"] == right["original_source_block"]
                    )
                    merge = merge and len(previous["source_blocks"]) < 2
                    limit = 362
            if merge:
                owner = timeline[previous["source_blocks"][-1]]
                merge = (
                    owner["voice"] == item["voice"]
                    and owner["subject"] == item["subject"]
                    and _frames(previous["seconds"] + seconds) <= limit
                )
            if merge:
                previous["source_blocks"].append(index)
                previous["seconds"] += seconds
            else:
                windows.append({"shot": shot["shot"], "source_blocks": [index], "seconds": seconds})
    assert sum(_frames(window["seconds"]) for window in windows) <= 2880, "total_over120"
    return {"measured_windows": windows}


def _segment(plan, segments, shot, blocks, count, seconds, cursor):
    words = "".join(plan["rows"][index]["text"] for index in blocks)
    return {
        "segment_index": len(segments),
        "shot": shot,
        "source_blocks": blocks,
        "text": words,
        "prompt": "",
        "original_slots": [],
        "bindings": [],
        "native_audio": True,
        "model_frames": count,
        "keep_count": count,
        "keep_start": 0,
        "output_start": cursor,
        "measured_seconds": seconds,
        "visual_only": not blocks,
        "continuation": False,
        "guide_enabled": False,
    }


def build_duration_plan(source_text: str, options_text: str):
    plan = json.loads(source_text)
    options = json.loads(options_text)
    assert plan["schema"] == "rh-native-source-v1" and plan["shots"], "invalid_source_schema"
    mode = plan["mode"]
    segments = []
    cursor = 0
    if mode == "without_voice":
        total = float(options.get("selected_seconds", 15))
        assert math.isfinite(total) and 4 <= total <= 30, "selected_outside4_30"
        count = len(plan["shots"])
        target = int(total * 24)
        assert 5 * count <= target, "too_many_shots_for_duration"
        starts = []
        for shot in plan["shots"]:
            masked = re.sub(r"<d>.*?</d>", "", shot["body"], flags=re.S)
            clocks = _AT_CLOCK.findall(masked)
            starts.append(float(clocks[0][0]) * 60 + float(clocks[0][1]) if clocks else None)
        if count == 1:
            weights = [1.0]
        elif all(item is not None for item in starts):
            assert (
                starts[0] == 0
                and all(left < right for left, right in zip(starts, starts[1:]))
                and starts[-1] < total
            ), "invalid_authored_clock"
            weights = [right - left for left, right in zip(starts, starts[1:] + [total])]
        else:
            assert all(item is None for item in starts) or (
                starts[0] == 0 and all(item is None for item in starts[1:])
            ), "partial_authored_clock"
            weights = [max(1, len(shot["text"])) for shot in plan["shots"]]
        steps = max(int(math.ceil((96 - 5 * count) / 17)), (target - 5 * count) // 17, 0)
        weight = sum(weights)
        quotas = [steps * item / weight for item in weights]
        allocation = [int(item) for item in quotas]
        remainders = [quotas[index] - allocation[index] for index in range(count)]

        def residual(index):
            return remainders[index]

        order = sorted(range(count), key=residual, reverse=True)
        for index in order[: steps - sum(allocation)]:
            allocation[index] += 1
        for shot, extra in zip(plan["shots"], allocation):
            frames = 5 + 17 * extra
            segments.append(_segment(plan, segments, shot["shot"], shot["source_blocks"], frames, frames / 24, cursor))
            cursor += frames
        assert 96 <= cursor <= 720 and abs(target - cursor) < 17, "fixed_frame_budget"
        cap = 30
    else:
        assert mode == "with_voice", "mode_invalid"
        windows = options.get("measured_windows", [])
        covered = []
        previous = -1
        assert windows, "missing_measured_clock"
        for window in windows:
            shot = int(window["shot"])
            blocks = window["source_blocks"]
            seconds = float(window["seconds"])
            assert 0 <= shot < len(plan["shots"]) and shot >= previous, "shot_order_invalid"
            assert math.isfinite(seconds) and 0 < seconds <= 30, "window_over30"
            assert blocks == list(blocks) and all(
                index == int(index) and 0 <= index < len(plan["rows"]) and plan["rows"][index]["shot"] == shot
                for index in blocks
            ), "invalid_source_blocks"
            if not blocks:
                assert plan["shots"][shot]["visual_only"], "missing_spoken_block"
            covered += blocks
            previous = shot
            frames = max(5, int(math.ceil(seconds * 24)))
            frames += (5 - frames % 17) % 17
            assert frames / 24 <= 30, "window_over30"
            item = _segment(plan, segments, shot, blocks, frames, seconds, cursor)
            if blocks and all(plan["rows"][index].get("measured_sentence_window") for index in blocks):
                item["internal_split_origin"] = [shot, plan["rows"][blocks[0]]["original_source_block"]]
            segments.append(item)
            cursor += frames
        assert covered == list(range(len(plan["rows"]))), "dialogue_changed"
        assert {item["shot"] for item in segments} == set(range(len(plan["shots"]))), (
            "silent_hold_without_duration"
        )
        assert 0 < cursor <= 120 * 24, "total_over120"
        total = cursor / 24
        cap = 120
    assert "".join(item["text"] for item in segments) == "".join(row["text"] for row in plan["rows"]), (
        "dialogue_changed"
    )
    return {
        "schema": "rh-native-plan-v1",
        "mode": mode,
        "count": len(segments),
        "requested_seconds": total,
        "actual_seconds": cursor / 24,
        "output_frames": cursor,
        "max_seconds": cap,
        "segments": segments,
    }


def build_measured_bind(queue_text: str, plan_text: str):
    queue = json.loads(queue_text)
    plan = json.loads(plan_text)
    assert not queue["queue"] and len(queue["accepted"]) == len(queue["timeline"]), "unfinished_clock_queue"
    assert "".join(item["text"] for item in queue["accepted"]) == "".join(
        row["text"] for row in plan["rows"]
    ), "dialogue_changed"
    if queue["splits"]:
        rows = []
        for shot in plan["shots"]:
            parts = []
            for accepted in queue["accepted"]:
                if accepted["shot"] != shot["shot"]:
                    continue
                origin = accepted.get("original_source_block", accepted["source_block"])
                row = dict(plan["rows"][origin])
                for key in (
                    "text",
                    "raw_dialogue",
                    "action",
                    "pause_before",
                    "pause_after",
                    "source_action",
                    "original_source_block",
                    "original_full_text",
                    "measured_sentence_window",
                ):
                    if key in accepted:
                        row[key] = accepted[key]
                row["source_block"] = len(rows)
                parts.append(row)
                rows.append(row)
            shot["parts"] = parts
            shot["source_blocks"] = [row["source_block"] for row in parts]
            shot["text"] = "".join(row["text"] for row in parts)
        plan["rows"] = rows
        plan["internal_measured_dialogue_split"] = True
    for item, row in zip(queue["timeline"], plan["rows"]):
        assert all(
            item[key] == row[key] for key in ("source_block", "shot", "subject", "voice", "text")
        ), "clock_source_mismatch"
    return {
        "source": json.dumps(plan, ensure_ascii=False),
        "timeline": json.dumps(queue["timeline"], ensure_ascii=False),
        "measurement_attempts": queue["attempts"],
        "split_count": queue["splits"],
    }


def build_exact_line(queue_text: str, windows_text: str):
    queue = json.loads(queue_text)
    windows = json.loads(windows_text)
    row = queue["queue"][0].copy()
    index = len(queue["timeline"])
    row.update(
        index=index,
        voice_index=row["voice"] - 1,
        emotion_index=(row["emotion"] or 1) - 1,
        has_emotion=row["emotion"] is not None,
        has_previous=index > 0,
        tempo_changed=abs(row["rate"] - 1) > 0.00001,
    )
    row["reference_windows"] = windows.get("reference_windows", {})
    return row


def _run_pair(builder):
    def run(input_text, input_json):
        text = "" if input_text is None else input_text
        extra = "" if input_json is None else input_json
        try:
            return pack_success(builder(text, extra))
        except Exception as exc:
            return pack_error(exc)

    return run


run_clock_windows = _run_pair(build_clock_windows)
run_duration_plan = _run_pair(build_duration_plan)
run_measured_bind = _run_pair(build_measured_bind)
run_exact_line = _run_pair(build_exact_line)


class _RunnerNode:
    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True}),
            }
        }


class PPCClockToWindows(_RunnerNode):
    DESCRIPTION = "Group measured per-line seconds into shot windows. Does not accept code."

    def run(self, input_text, input_json):
        return run_clock_windows(input_text, input_json)


class PPCDurationPlan(_RunnerNode):
    DESCRIPTION = "Turn measured windows or authored clocks into a frame plan. Does not accept code."

    def run(self, input_text, input_json):
        return run_duration_plan(input_text, input_json)


class PPCMeasuredDialogueBind(_RunnerNode):
    DESCRIPTION = "Bind a finished measurement queue back onto the storyboard. Does not accept code."

    def run(self, input_text, input_json):
        return run_measured_bind(input_text, input_json)


class PPCExactLine(_RunnerNode):
    DESCRIPTION = "Read the next queued line without changing its text. Does not accept code."

    def run(self, input_text, input_json):
        return run_exact_line(input_text, input_json)
