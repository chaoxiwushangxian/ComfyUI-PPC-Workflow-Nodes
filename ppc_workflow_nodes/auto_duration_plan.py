"""Automatic-duration estimate nodes.

720010, 720011, 770008, 720008, 720003, 720007, 720001, and 500020.
Durations come from the supplied plan. Automatic mode is the original
``自动时长`` branch, not a forced 30s or 120s output.
"""

from __future__ import annotations

import json
import math
import re

from .serialize import pack_error, pack_success


def _text(value):
    return "" if value is None else value


def _run(builder, needs_json=True):
    def run(input_text, input_json=""):
        try:
            if needs_json:
                return pack_success(builder(_text(input_text), _text(input_json)))
            return pack_success(builder(_text(input_text)))
        except Exception as exc:
            return pack_error(exc)

    return run


def build_dialogue_interval_split(raw: str):
    plan = json.loads(raw)
    if plan["mode"] == "without_voice":
        before = "".join(row["text"] for row in plan["rows"])
        rows = []
        changed = False
        for shot in plan["shots"]:
            parts = []
            for original in shot["parts"]:
                text = original["text"]
                tokens = re.findall(r"[A-Za-z]+|\s+|[\s\S]", text)
                total = sum(2 if token.isascii() and token.isalpha() else (1 if token.isalnum() else 0) for token in tokens)
                chunks = []
                current = ""
                weight = 0
                if total > 95:
                    for token in tokens:
                        token_weight = 2 if token.isascii() and token.isalpha() else (1 if token.isalnum() else 0)
                        if weight + token_weight > 70 and current:
                            chunks.append(current)
                            current = ""
                            weight = 0
                        current += token
                        weight += token_weight
                        if weight >= 50 and token in "。！？；.!?;":
                            chunks.append(current)
                            current = ""
                            weight = 0
                    if current:
                        chunks.append(current)
                else:
                    chunks = [text]
                changed = changed or len(chunks) > 1
                for index, chunk in enumerate(chunks):
                    row = dict(original)
                    row["source_block"] = len(rows)
                    row["text"] = chunk
                    row["raw_dialogue"] = "<d>[" + row["language"] + "]" + chunk + "</d>"
                    if len(chunks) > 1:
                        row["original_source_block"] = original["source_block"]
                        row["original_full_text"] = text
                        low = original["action"].lower()
                        row["duration_rate"] = 3.5 if "slow" in low or "measured" in low else 5.0
                    if index:
                        row["source_action"] = original["action"]
                        row["action"] = (
                            "Continue the same scene and ongoing physical action from the preceding interval "
                            "without repeating the introduction. The same <Subject "
                            + row["subject"]
                            + "> (S"
                            + row["subject"]
                            + ") continues speaking at the same pace: "
                        )
                    rows.append(row)
                    parts.append(row)
            shot["parts"] = parts
            shot["source_blocks"] = [row["source_block"] for row in parts]
            shot["text"] = "".join(row["text"] for row in parts)
        assert before == "".join(row["text"] for row in rows), "dialogue_split_changed_words"
        plan["rows"] = rows
        if changed:
            plan["internal_dialogue_split"] = True
    return plan


def build_long_estimate_split(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":
        entries = []
        for entry in options["duration_estimate"]["shots"]:
            if entry["frames"] <= 719 or not entry["rows"]:
                entries.append(entry)
                continue

            def make(rows, silence, tail, action, source=entry):
                window = dict(source)
                window["rows"] = [dict(row) for row in rows]
                window["source_blocks"] = [row["source_block"] for row in rows]
                window["speech_seconds"] = sum(row["speech_seconds"] for row in rows)
                window["silence_seconds"] = silence + sum(row["pause_before"] for row in rows)
                window["tail_seconds"] = tail
                window["estimated_seconds"] = window["speech_seconds"] + window["silence_seconds"] + tail
                window["frames"] = 5 + 17 * max(0, int(math.ceil((window["estimated_seconds"] * 24 - 5) / 17)))
                if action:
                    window["duration_action_override"] = action
                return window

            pending = []
            for old in entry["rows"]:
                row = dict(old)
                if row["pause_before"] + row["speech_seconds"] > 30 and row["pause_before"] > 0:
                    if pending:
                        entries.append(make(pending, 0, 0, ""))
                        pending = []
                    action = plan["rows"][row["source_block"]]["action"]
                    low = action.lower()
                    points = [low.find(token) for token in ("then", "before speaking", "before saying") if token in low]
                    if points:
                        action = action[: min(points)]
                    action += " Complete only this requested preparatory action in silence; no dialogue in this interval."
                    entries.append(make([], row["pause_before"], 0, action))
                    row["pause_before"] = 0.0
                pending.append(row)
            if pending:
                entries.append(make(pending, 0, 0, ""))
            if entry["tail_seconds"] > 0:
                action = plan["shots"][entry["shot"]]["tail"] or (
                    "Remain in the final requested scene and continue the specified closing action "
                    "with only the requested music or ambience. No dialogue."
                )
                entries.append(make([], entry["tail_seconds"], 0, action))
        options["duration_estimate"]["shots"] = entries
    return options


def build_native_windows(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":
        info = options["duration_estimate"]
        windows = []
        for entry in info["shots"]:
            original = plan["shots"][entry["shot"]]
            if entry["frames"] <= 719:
                window = dict(entry)
                window["source_blocks"] = entry.get("source_blocks", original["source_blocks"])
                windows.append(window)
            elif not entry["rows"]:
                count = int(math.ceil(entry["estimated_seconds"] / 30.0))
                for _index in range(count):
                    window = dict(entry)
                    window["source_blocks"] = []
                    window["silence_seconds"] = entry["estimated_seconds"] / count
                    window["estimated_seconds"] = window["silence_seconds"]
                    window["rows"] = []
                    window["frames"] = min(
                        719,
                        5 + 17 * max(0, int(math.ceil((window["estimated_seconds"] * 24 - 5) / 17))),
                    )
                    if window.get("duration_action_override"):
                        window["duration_action_override"] = re.sub(
                            r"\bfor [0-9.]+ seconds?\b",
                            "for " + str(round(window["estimated_seconds"], 3)) + " seconds",
                            window["duration_action_override"],
                            flags=re.I,
                        )
                    windows.append(window)
            else:
                group = []
                seconds = 0.0
                groups = []
                for row in entry["rows"]:
                    length = row["speech_seconds"] + row["pause_before"]
                    assert length <= 30.0, "spoken_unit_needs_split"
                    if group and seconds + length > 30.0:
                        groups.append(group)
                        group = []
                        seconds = 0.0
                    group.append(row)
                    seconds += length
                if group:
                    groups.append(group)
                for index, group in enumerate(groups):
                    window = dict(entry)
                    window["rows"] = [dict(row) for row in group]
                    window["source_blocks"] = [row["source_block"] for row in group]
                    window["speech_seconds"] = sum(row["speech_seconds"] for row in group)
                    window["silence_seconds"] = sum(row["pause_before"] for row in group)
                    window["tail_seconds"] = entry["tail_seconds"] if index == len(groups) - 1 else 0.0
                    window["estimated_seconds"] = (
                        window["speech_seconds"] + window["silence_seconds"] + window["tail_seconds"]
                    )
                    window["frames"] = (
                        min(719, 5 + 17 * max(0, int(math.ceil((window["estimated_seconds"] * 24 - 5) / 17))))
                        if window["estimated_seconds"] <= 30
                        else 736
                    )
                    assert window["frames"] <= 719, "action_and_speech_window_over30"
                    windows.append(window)
        info["_native_windows_pending"] = windows
    return options


def build_frame_grid(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":
        info = options["duration_estimate"]
        windows = info.pop("_native_windows_pending")
        required = sum(window["estimated_seconds"] for window in windows)
        assert required <= 60, "content_requires_over60_seconds"
        total = sum(window["frames"] for window in windows)
        for _unused in range(len(windows) * 2):
            if total <= 1440:
                break
            candidates = [
                index
                for index, window in enumerate(windows)
                if (window["speech_seconds"] > 0 or not window["rows"])
                and window["frames"] > 22
                and (window["frames"] - 17) / 24
                >= window["estimated_seconds"]
                - (
                    17 / 24
                    if not window["rows"] and window["speech_seconds"] == 0
                    else max(min(0.30, window["speech_seconds"] * 0.075), min(17 / 24, window.get("visual_padding_seconds", 0)))
                )
            ]
            if not candidates:
                break

            def excess(index, current=windows):
                return current[index]["frames"] / 24 - current[index]["estimated_seconds"]

            chosen = max(candidates, key=excess)
            windows[chosen]["frames"] -= 17
            total -= 17
            window = windows[chosen]
            trim = max(0, window["estimated_seconds"] - window["frames"] / 24)
            if not window["rows"] and window["speech_seconds"] == 0:
                window["silence_seconds"] = max(0, window["silence_seconds"] - trim)
            if window.get("visual_padding_seconds", 0) >= trim:
                window["visual_padding_seconds"] -= trim
                window["tail_seconds"] -= trim
                window["estimated_seconds"] -= trim
        assert total <= 1440, "frame_grid_requires_over60_seconds"
        cursor = 0
        for window in windows:
            window["output_start"] = cursor
            window["planned_seconds"] = window["frames"] / 24
            at = 0.0
            available = max(0, window["planned_seconds"] - window["silence_seconds"] - window["tail_seconds"])
            scale = available / window["speech_seconds"] if window["speech_seconds"] else 1.0
            for row in window["rows"]:
                row["action_start"] = at
                at += row["pause_before"]
                row["start"] = at
                at += row["speech_seconds"] * scale
                row["end"] = at
            window["tail_start"] = at
            window["tail_end"] = window["planned_seconds"]
            cursor += window["frames"]
        errors = [reason for reason in info["fallback_reasons"] if reason != "estimated_budget_not_satisfied"]
        fits = not errors
        info["windows"] = windows
        info["budget_sufficient"] = fits
        info["decision"] = "estimate_applied" if fits else info["decision"]
        info["fallback_reasons"] = errors
        info["estimated_required_seconds"] = required
        info["frame_grid_tolerance_seconds"] = max(
            [max(0, window["estimated_seconds"] - window["planned_seconds"]) for window in windows] + [0]
        )
        if fits:
            options["estimated_windows"] = windows
            options["estimated_frames"] = [window["frames"] for window in windows]
    return options


def build_without_voice_plan(source_text: str, options_text: str):
    plan = json.loads(source_text)
    options = json.loads(options_text)
    assert plan["schema"] == "rh-native-source-v1" and plan["shots"], "invalid_source_schema"
    mode = plan["mode"]
    segments = []
    cursor = 0
    assert mode == "without_voice", "wrong_duration_branch"

    def segment(shot, blocks, count, seconds):
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

    total = float(options.get("selected_seconds", 15))
    assert math.isfinite(total) and 4 <= total <= 60, "selected_outside4_30"
    count = len(plan["shots"])
    target = int(total * 24)
    assert 5 * count <= target, "too_many_shots_for_duration"
    starts = [shot.get("authored_start") for shot in plan["shots"]]
    if options.get("estimated_frames") or count == 1:
        weights = [1.0] * count
    elif count > 1 and all(item == 0 for item in starts):
        weights = [max(1, float(shot.get("authored_end") or total / count)) for shot in plan["shots"]]
    elif all(item is not None for item in starts):
        assert starts[0] == 0 and all(left < right for left, right in zip(starts, starts[1:])), "invalid_authored_clock"
        authored_end = plan["shots"][-1].get("authored_end")
        clock_end = total if authored_end is None else float(authored_end)
        assert math.isfinite(clock_end) and starts[-1] < clock_end <= 120, "invalid_authored_clock"
        weights = [right - left for left, right in zip(starts, starts[1:] + [clock_end])]
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
    if options.get("estimated_windows"):
        for window in options["estimated_windows"]:
            frames = window["frames"]
            segments.append(segment(window["shot"], window["source_blocks"], frames, frames / 24))
            cursor += frames
            if window.get("duration_action_override"):
                segments[-1]["duration_action_override"] = window["duration_action_override"]
    else:
        for index, (shot, extra) in enumerate(zip(plan["shots"], allocation)):
            frames = options["estimated_frames"][index] if options.get("estimated_frames") else 5 + 17 * extra
            segments.append(segment(shot["shot"], shot["source_blocks"], frames, frames / 24))
            cursor += frames
    assert 96 <= cursor <= 1440 and (options.get("estimated_frames") or abs(target - cursor) < 17), "fixed_frame_budget"
    cap = 60
    assert "".join(item["text"] for item in segments) == "".join(row["text"] for row in plan["rows"]), "dialogue_changed"
    result = {
        "schema": "rh-native-plan-v1",
        "mode": mode,
        "count": len(segments),
        "requested_seconds": total,
        "actual_seconds": cursor / 24,
        "output_frames": cursor,
        "max_seconds": cap,
        "segments": segments,
    }
    if "duration_estimate" in options:
        result["duration_estimate"] = options["duration_estimate"]
    return result


run_dialogue_interval_split = _run(build_dialogue_interval_split, needs_json=False)
run_long_estimate_split = _run(build_long_estimate_split)
run_native_windows = _run(build_native_windows)
run_frame_grid = _run(build_frame_grid)
run_without_voice_plan = _run(build_without_voice_plan)
