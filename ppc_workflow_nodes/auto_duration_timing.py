"""Timing-hint nodes 720003, 720007, and 720001."""

from __future__ import annotations

import json
import math
import re

from .serialize import pack_error, pack_success


def _run(builder):
    def run(input_text, input_json=""):
        text = "" if input_text is None else input_text
        extra = "" if input_json is None else input_json
        try:
            return pack_success(builder(text, extra))
        except Exception as exc:
            return pack_error(exc)

    return run


def build_timing_hints(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":

        def clock(value):
            parts = value.rstrip(".,;:").split(":")
            return float(parts[-1]) + (60 * float(parts[0]) if len(parts) == 2 else 0)

        def interval(text):
            found = []
            for match in re.finditer(
                r"\b(?:from|between) +([0-9:.]+) *(seconds?\b)? +(?:to|and) +([0-9:.]+) *(seconds?\b)?",
                text,
                re.I,
            ):
                if match[2] or match[4] or (
                    ":" in match[1] + match[3]
                    or re.search(r"(?:\[shot \d+\]|\bbeat \d+,?)\s*$", text[: match.start()].lower())
                ) and text[match.end() :].lstrip()[:1] in ",;:.，；!?":
                    found = [clock(match[1]), clock(match[3])]
            return found

        def explicit(text):
            total = 0.0
            for match in re.finditer(r"([0-9.]+)( seconds?\b|-second\b)", text, re.I):
                before = text[: match.start()].lower().rstrip()
                after = text[match.end() :].lower().strip().split()[:3]
                allowed = before.endswith(("for", "lasting", "lasts", "pause", "hold")) or (
                    "-second" in match[2]
                    and any(word.strip(".,;:") in ["pause", "hold", "silence", "outro", "ending"] for word in after)
                )
                if allowed:
                    total += float(match[1])
            return total + (
                sum(float(number) for number in re.findall(r"(?:静默|停顿)\s*([0-9.]+)\s*秒", text))
                if "静默" in text or "停顿" in text
                else 0
            )

        summary = plan["header"].partition("summary:")[2].partition("retention_analysis:")[0]
        total = 0.0
        for match in re.finditer(r"[0-9]+[0-9:.]*", summary):
            before = summary[: match.start()].lower().rstrip()
            after = summary[match.end() :].lower()
            film = after.startswith("-second ") and any(
                word.strip(".,") in ["video", "film", "clip", "take", "showcase", "narrative", "timeline"]
                for word in after.split()[:5]
            )
            if film or before.endswith(("duration is", "duration:", "duration =", "duration")):
                total = clock(match[0].rstrip("."))
        hints = []
        errors = []
        global_end = 0.0
        outside = re.sub(r"<d>.*?</d>", "", plan["source"], flags=re.S)
        if re.search(r"\b(?:from|to) +[0-9.]+s\b", outside, re.I):
            errors.append("short_s_clock_unsupported")
        if re.search(r"\d+:\d+:\d+", outside):
            errors.append("hh_mm_ss_clock_unsupported")
        for index, shot in enumerate(plan["shots"]):
            start_authored = shot.get("authored_start")
            end_authored = shot.get("authored_end")
            local = index > 0 and start_authored == 0
            origin = global_end if local or start_authored is None else start_authored
            start = start_authored or 0
            if end_authored is None:
                later = plan["shots"][index + 1].get("authored_start") if index + 1 < len(plan["shots"]) else total
                end_authored = later if later and later > start else None
            duration = end_authored - start if end_authored is not None else explicit(shot["body"])
            rows = []
            for row in shot["parts"]:
                action = row["action"]
                hold = explicit(action)
                pause = bool(
                    re.search(r"\b(?:pauses?|silent|silence|no dialogue|before speaking)\b|静默|停顿|无对白|空镜", action, re.I)
                )
                rows.append({"window": interval(action), "hold": hold, "pause": pause})
            tail_window = interval(shot["tail"]) if not shot["visual_only"] else []
            tail = (
                max(explicit(shot["tail"]), tail_window[1] - tail_window[0] if tail_window else 0)
                if not shot["visual_only"]
                else 0
            )
            if (
                not shot["visual_only"]
                and index == len(plan["shots"]) - 1
                and re.search(r"outro|conclud|ending|收尾|结束", plan["tail"], re.I)
            ):
                tail = max(tail, explicit(plan["tail"]))
            if rows and rows[-1]["window"] and tail_window:
                rows[-1]["window"][1] = min(rows[-1]["window"][1], tail_window[0])
            clocks = [value for row in rows for value in row["window"]]
            if any(left > right for left, right in zip(clocks, clocks[1:])):
                errors.append("conflicting_authored_boundaries")
            if clocks and min(clocks) < start:
                errors.append("mixed_local_global_clock_unsupported")
            if not local and start_authored is not None and index and start_authored != global_end:
                errors.append("noncontiguous_authored_shots")
            if shot["visual_only"] and duration <= 0:
                errors.append("visual_only_duration_unknown")
            hints.append(
                {
                    "start": start,
                    "end": end_authored,
                    "origin": origin,
                    "local": local,
                    "visual_seconds": duration,
                    "rows": rows,
                    "tail": tail,
                    "tail_window": tail_window,
                }
            )
            global_end = origin + duration
        parallel = max(explicit(part) for part in plan["tail"].split("non_diegetic_music:"))
        options["prompt_timing_hints"] = {
            "shots": hints,
            "errors": errors,
            "summary_seconds": total,
            "authored_total": global_end,
            "parallel_minimum": parallel,
        }
    return options


def build_causal_pace(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":
        words = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
            "fifteen": 15, "twenty": 20, "thirty": 30, "sixty": 60,
        }

        def events(text):
            low = text.lower()
            found = []
            for match in re.finditer(r"\b([\w.]+)[ -]seconds?\b", low):
                lead = low[max(0, match.start() - 24) : match.start()].strip()
                if lead.endswith(("from", "to", "between", "and", "duration is", "duration:")):
                    continue
                if match[1] not in words and not match[1].replace(".", "", 1).isdigit():
                    continue
                value = words[match[1]] if match[1] in words else float(match[1])
                found.append({"start": match.start(), "end": match.end(), "value": value, "language": "en"})
            digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            for match in re.finditer(r"(?:静默|停顿|停留|等待)\s*([0-9.]+|[一二两三四五六七八九十])\s*秒", low):
                value = digits[match[1]] if match[1] in digits else float(match[1])
                duplicate = False
                for event in found:
                    if (
                        event["value"] == value
                        and event["end"] <= match.start()
                        and re.match(r"^[\s(（:：,，]*$", low[event["end"] : match.start()])
                    ):
                        duplicate = True
                if not duplicate:
                    found.append({"start": match.start(), "end": match.end(), "value": value, "language": "zh"})
            return sorted(found, key=lambda event: event["start"])

        def pace(action):
            low = action.lower()
            marks = [
                low.find(verb)
                for verb in (
                    "says", "speaks", "speaking", "delivers", "delivering",
                    "addresses the camera", "speech", "delivery",
                )
                if verb in low
            ]
            if not marks:
                return 5.0
            at = min(marks)
            before = low[max(0, at - 65) : at]
            after = low[at : at + 70]
            spoken_clause = low[at : at + 180].split(".", 1)[0]
            slow = any(word in spoken_clause for word in (" slowly", " slow pace", " measured pace")) or any(
                word in before for word in ("slow pace", "measured pace", "slow, measured pace")
            )
            brisk = any(word in after for word in (" briskly", " quickly", " brisk pace", " rapid pace")) or any(
                word in before for word in ("brisk pace", "rapid pace")
            )
            return 3.5 if slow else (5.8 if brisk else 5.0)

        hints = options["prompt_timing_hints"]
        for shot, hint in zip(plan["shots"], hints["shots"]):
            for row, hint_row in zip(shot["parts"], hint["rows"]):
                action = row["action"]
                low = action.lower()
                pre = 0.0
                parallel = 0.0
                for event in events(action):
                    after = low[event["end"] :]
                    around = low[max(0, event["start"] - 50) : event["end"] + 35]
                    sequence = re.search(r"\b(?:then|before speaking|before saying|after which|after that)\b", after)
                    paused = bool(re.search(r"\b(?:pause|pauses|silent|silently|silence|wait|waits)\b|静默|停顿|停留|等待", around))
                    simultaneous_match = re.search(r"\bwhile\b|\bat the same time\b|同时", after)
                    simultaneous = bool(
                        simultaneous_match and (not sequence or simultaneous_match.start() < sequence.start())
                    )
                    if (sequence or paused) and not simultaneous:
                        pre += event["value"]
                    else:
                        parallel += event["value"]
                hint_row["pre_seconds"] = pre
                hint_row["parallel_seconds"] = parallel
                hint_row["rate_cjk"] = row.get("duration_rate", pace(action))
            if not shot["visual_only"]:
                authored = sum(event["value"] for event in events(shot["tail"]))
                hint["tail"] = max(hint["tail"], authored)
                if not hint["tail"] and any(
                    word in shot["tail"].lower() for word in ("hold", "pause", "fade", "dissolve", "ending", "outro")
                ):
                    hint["tail"] = 0.6
        if "noncontiguous_authored_shots" in hints["errors"]:
            for index in range(1, len(hints["shots"])):
                previous = hints["shots"][index - 1]
                current = hints["shots"][index]
                if not current["local"] and previous["end"] is not None and current["start"] > previous["end"]:
                    previous["tail"] += current["start"] - previous["end"]
            hints["errors"] = [item for item in hints["errors"] if item != "noncontiguous_authored_shots"]
            options["clock_normalization"] = "authored_shot_order_with_explicit_gaps_preserved"
        options["timing_semantics"] = "causal_pace_v1"
    return options


def build_duration_estimate(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice":
        hints = options.pop("prompt_timing_hints")
        entries = []
        unknown = hints["errors"]
        duration_mode = options.get("duration_mode", "自动时长")
        assert duration_mode in ["自动时长", "自定义时长"], "invalid_duration_mode"
        for shot, hint in zip(plan["shots"], hints["shots"]):
            rows = []
            silence = max(0, hint["visual_seconds"]) if shot["visual_only"] else 0.0
            speech = 0.0
            for row, hint_row in zip(shot["parts"], hint["rows"]):
                text = row["text"]
                cjk = sum("\u3400" <= char <= "\u9fff" for char in text)
                latin = len(re.findall(r"[A-Za-z]+", text))
                digits = sum(char in "0123456789" for char in text)
                rate = hint_row.get("rate_cjk", 5.0)
                estimate = max(0.25, (cjk + digits) / rate + latin / (rate / 2))
                before = hint_row.get("pre_seconds", hint_row["hold"] if hint_row["pause"] else 0.0)
                estimate = max(estimate, hint_row.get("parallel_seconds", 0 if hint_row["pause"] else hint_row["hold"]))
                window = hint_row["window"]
                if window and window[0] >= window[1]:
                    unknown.append("conflicting_authored_boundaries")
                rows.append(
                    {
                        "source_block": row["source_block"],
                        "speech_seconds": estimate,
                        "pause_before": before,
                        "source_clock": window,
                    }
                )
                speech += estimate
                silence += before
            tail = hint["tail"]
            if not shot["visual_only"] and not tail and re.search(
                r"\b(?:holds?|pauses?|fades?|dissolves?|ending|outro)\b", shot["tail"], re.I
            ):
                unknown.append("preserve_authored_due_to_unquantified_actions")
            original_required = speech + silence + tail
            seconds = original_required
            authored = hint["visual_seconds"] if shot.get("authored_end") is not None else 0.0
            if duration_mode == "自动时长" and authored > seconds:
                tail += authored - seconds
                seconds = authored
            frames = 5 + 17 * max(0, int(math.ceil((seconds * 24 - 5) / 17)))
            entries.append(
                {
                    "shot": shot["shot"],
                    "speech_seconds": speech,
                    "silence_seconds": silence,
                    "tail_seconds": tail,
                    "estimated_seconds": seconds,
                    "frames": frames,
                    "rows": rows,
                    "source_start": hint["start"],
                    "source_end": hint["end"],
                    "source_tail": hint["tail_window"],
                    "source_global_origin": hint["origin"],
                    "source_local_clock": hint["local"],
                }
            )
            entries[-1]["visual_padding_seconds"] = max(0, seconds - original_required)
        extra = max(0, hints["parallel_minimum"] - sum(entry["estimated_seconds"] for entry in entries))
        if extra:
            entry = entries[-1]
            entry["tail_seconds"] += extra
            entry["estimated_seconds"] += extra
            entry["frames"] = 5 + 17 * max(0, int(math.ceil((entry["estimated_seconds"] * 24 - 5) / 17)))
        entries[0]["frames"] += 17 * max(0, int(math.ceil((96 - sum(item["frames"] for item in entries)) / 17)))
        cap = 60.0
        fits = not unknown and sum(item["frames"] for item in entries) <= int(cap * 24)
        authored = hints["authored_total"]
        fallback = bool(
            not fits
            and unknown
            and 4 <= authored <= cap
            and all(
                item in [
                    "speech_pace_requires_authored_budget",
                    "preserve_authored_due_to_unquantified_actions",
                    "short_s_clock_unsupported",
                ]
                for item in unknown
            )
        )
        if fallback:
            options["selected_seconds"] = authored
        cursor = 0
        for entry in entries:
            entry["output_start"] = cursor
            entry["planned_seconds"] = entry["frames"] / 24
            available = max(0, entry["planned_seconds"] - entry["silence_seconds"] - entry["tail_seconds"])
            scale = available / entry["speech_seconds"] if entry["speech_seconds"] else 1.0
            at = 0.0
            for row in entry["rows"]:
                row["action_start"] = at
                at += row["pause_before"]
                row["start"] = at
                at += row["speech_seconds"] * scale
                row["end"] = at
            entry["tail_start"] = at
            entry["tail_end"] = entry["planned_seconds"]
            cursor += entry["frames"]
        options["duration_estimate"] = {
            "clock_source": "prompt_estimate_causal_v3",
            "nominal_requested_seconds": float(options["selected_seconds"]),
            "native_final_audio_measured": False,
            "decision": "estimate_applied"
            if fits
            else ("preserve_authored_due_to_unquantified_actions" if fallback else "unresolved_original_budget_preserved"),
            "fallback_canvas_requested_seconds": authored if fallback else None,
            "selected_upper_seconds": cap,
            "parallel_audio_minimum_seconds": hints["parallel_minimum"],
            "estimated_required_seconds": sum(entry["estimated_seconds"] for entry in entries),
            "budget_sufficient": fits,
            "fallback_reasons": unknown + ([] if fits else ["estimated_budget_not_satisfied"]),
            "shots": entries,
        }
        options["duration_estimate"]["duration_mode"] = duration_mode
        if fits:
            options["estimated_frames"] = [entry["frames"] for entry in entries]
    return options


run_timing_hints = _run(build_timing_hints)
run_causal_pace = _run(build_causal_pace)
run_duration_estimate = _run(build_duration_estimate)
