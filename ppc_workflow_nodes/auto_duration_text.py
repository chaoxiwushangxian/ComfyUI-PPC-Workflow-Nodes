"""Prompt projection and shot-scope nodes 720002, 720004, 720005, 720006, 720009, 720013.

Dialogue tags are split out and copied back. Assertions reject a result whose
``<d>`` spans differ from the input.
"""

from __future__ import annotations

import json
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


def _clock(value):
    parts = value.split(":")
    return float(parts[-1]) + (60 * float(parts[0]) if len(parts) == 2 else 0)


def _stamp(value):
    return str(int(value // 60)).zfill(2) + ":" + ("%06.3f" % (value % 60))


def _number(value):
    return str(round(value, 3))


def _mapped(value, points):
    if not points:
        return value
    if value <= points[0][0]:
        return points[0][1]
    for (left, left_out), (right, right_out) in zip(points, points[1:]):
        if left <= value < right:
            return left_out + (right_out - left_out) * (value - left) / (right - left)
    return points[-1][1]


def _project(text, points, local_prose=False):
    points = sorted(points)
    pieces = re.split(r"(<d>.*?</d>)", text, flags=re.S)

    for index in range(0, len(pieces), 2):
        def token(match, piece_index=index):
            lead = " " + pieces[piece_index][: match.start()].lower().rstrip()
            return (
                _stamp(_mapped(_clock(match[0]), points))
                if not re.search(r"\b(?:aspect|ratio|format)\b", lead[-60:])
                and lead.endswith(
                    (" from", " to", " between", " and", " at", " through", " until", " by", " duration is", " duration:")
                )
                else match[0]
            )

        def span(match, piece_index=index):
            framed = re.search(r"(?:\[shot \d+\]|\bbeat \d+,?)\s*$", pieces[piece_index][: match.start()], re.I)
            return (
                match[1]
                + _number(_mapped(float(match[2]), points))
                + match[3]
                + _number(_mapped(float(match[4]), points))
                + (match[5] or "")
                if "second" in match[0].lower()
                or framed
                and re.match(r"\s*(?:[,;，；!?]|[.:](?!\d)|$)", pieces[piece_index][match.end() :])
                else match[0]
            )

        def numeric(match, piece_index=index):
            lead = pieces[piece_index][: match.start()].lower().rstrip()
            allowed = lead.endswith(("begins", "starts", "continues", "ends", "stops", "musical phrase")) and any(
                word in lead[-100:] for word in ("music", "track", "score", "ambience", "soundscape")
            )
            return match[1] + " " + _number(_mapped(float(match[2]), points)) if allowed else match[0]

        if local_prose:
            pieces[index] = pieces[index].replace("global clock", "local clock of this generated clip").replace(
                "global positions in this one video", "local positions within this generated clip"
            )
        pieces[index] = re.sub(r"\b\d{2}:\d{2}(?:\.\d+)?\b", token, pieces[index])
        pieces[index] = re.sub(
            r"(\b(?:from|between)\s+)(\d+(?:\.\d+)?)(\s*(?:seconds?\s+)?(?:to|and)\s+)(\d+(?:\.\d+)?)(\s*seconds?\b)?",
            span,
            pieces[index],
            flags=re.I,
        )
        pieces[index] = re.sub(
            r"\b(at|through|until) +(\d+(?:\.\d+)?)(?= *[,;.\n]|$)",
            numeric,
            pieces[index],
            flags=re.I,
        )
    return "".join(pieces)


def _shot_points(entry):
    local = []
    if entry["source_start"] is not None:
        local.append((entry["source_start"], 0))
    if entry["source_end"] is not None:
        local.append((entry["source_end"], entry["planned_seconds"]))
    for row in entry["rows"]:
        if row["source_clock"]:
            local.extend(zip(row["source_clock"], [row["action_start"], row["end"]]))
    if entry["source_tail"]:
        local.extend(zip(entry["source_tail"], [entry["tail_start"], entry["tail_end"]]))
    return local


def build_duration_projection(segment_text: str, plan_text: str):
    segment = json.loads(segment_text)
    plan = json.loads(plan_text)
    info = plan.get("duration_estimate", {})
    if plan["mode"] == "without_voice" and info.get("budget_sufficient"):
        global_points = [
            (left + (entry["source_global_origin"] if entry["source_local_clock"] else 0), right + entry["output_start"] / 24)
            for entry in info.get("windows", info["shots"])
            for left, right in _shot_points(entry)
        ]
        entry = info["windows"][segment["segment_index"]] if info.get("windows") else info["shots"][segment["shot"]]
        prompt = segment["prompt"]
        local = _shot_points(entry)
        head, separator, body = prompt.partition("detailed_description:\n")
        detail, separator_2, tail = body.partition("overall_soundscape:\n")
        assert separator and separator_2, "duration_projection_sections"
        old_detail = detail
        detail = _project(detail, local, True)
        segment["duration_projection"] = {"original_detail": old_detail, "projected_detail": detail}
        segment["timing_projection_pending"] = {
            "head": head,
            "tail": tail,
            "detail": detail,
            "global_points": global_points,
            "planned_seconds": entry["planned_seconds"],
        }
    return segment


def build_projection_apply(segment_text: str, plan_text: str):
    segment = json.loads(segment_text)
    json.loads(plan_text)
    if "timing_projection_pending" in segment:
        data = segment.pop("timing_projection_pending")
        head = data["head"]
        tail = data["tail"]
        detail = data["detail"]
        global_points = data["global_points"]
        data["head"] = _project(head, global_points, True)
        data["tail"] = _project(tail, global_points)
        segment["timing_projection_pending"] = data
    return segment


def build_clip_timing(segment_text: str, plan_text: str):
    segment = json.loads(segment_text)
    plan = json.loads(plan_text)
    before = None
    if "timing_projection_pending" in segment:
        data = segment.pop("timing_projection_pending")
        head = data["head"]
        tail = data["tail"]
        detail = data["detail"]
        planned = data["planned_seconds"]
        before = re.findall(r"<d>.*?</d>", segment["prompt"], flags=re.S)

        def total_duration(match):
            return match[1] + _number(plan["actual_seconds"]) + match[2]

        def film_duration(match):
            return _number(plan["actual_seconds"]) + "-second"

        if "-second" in head.lower():
            head = re.sub(
                r"\b[0-9.]+-second\b(?=\s+(?:(?:continuous|high-end|commercial|fashion|authored)\s+){0,3}(?:video|film|clip|take|showcase|timeline)\b)",
                film_duration,
                head,
                flags=re.I,
            )
        if "duration" in head.lower():
            head = re.sub(
                r"((?:total|overall|film|video)\s+duration\s*(?:is|:|=)?\s*)\d+(?:\.\d+)?(\s*(?:seconds?|s\b))",
                total_duration,
                head,
                flags=re.I,
            )
        vocal = (
            "Do not add speech. "
            if segment["visual_only"]
            else "Speak only the assigned words at the authored natural pace; after the last word, "
        )
        timing = (
            "This clip uses local action times from 00:00.000 to "
            + _stamp(planned)
            + ". Summary and soundtrack clocks describe the complete film timeline. "
            + vocal
            + "Complete the authored silent ending actions and music without adding speech.\n"
        )
        out = head + "detailed_description:\n" + timing + detail + "overall_soundscape:\n" + tail
        assert re.findall(r"<d>.*?</d>", out, flags=re.S) == before, "duration_projection_dialogue"
        segment["prompt"] = out
    info = plan.get("duration_estimate", {})
    if plan["mode"] == "without_voice" and info.get("budget_sufficient") and not segment.get("visual_only"):
        entry = info["windows"][segment["segment_index"]] if info.get("windows") else info["shots"][segment["shot"]]
        rows = [row for row in entry["rows"] if row["source_block"] in segment["source_blocks"]]

        def role(text):
            text = re.sub(r"[\s_-]+", " ", text.lower()).replace("offscreen", "off screen").replace(
                "voiceover", "voice over"
            ).replace("oncamera", "on camera")
            found = None
            latest = -1
            positives = [
                "voice over", "narrator", "narration", "旁白", "画外音", "解说",
                "speaks off screen", "says off screen", "off screen voice", "off screen speaker",
            ]
            negatives = [
                "speaks on camera", "says on camera", "speaks on screen", "on camera speech",
                "on camera presenter", "on screen presenter", "对镜头说", "对着镜头说", "出镜口播", "现场口播",
            ]
            for word in positives + negatives:
                at = text.rfind(word)
                if at > latest and not any(
                    text[:at].rstrip().endswith(prefix)
                    for prefix in ("no", "not", "without", "not a", "not an", "无", "没有", "不是", "不要", "禁止")
                ):
                    latest = at
                    found = word in positives
            return found

        origins = {item["source_block"]: item["original_action"] for item in segment.get("action_provenance", [])}
        units = {item["source_block"]: item for item in segment.get("speaker_units", [])}
        definitions = segment.get("source_metadata", {}).get("header", "").split("summary:", 1)[0]

        def is_voice(row):
            action = origins.get(row["source_block"], "")
            value = role(action)
            if value is not None:
                return value
            unit = units.get(row["source_block"], {})
            subject = unit.get("subject")
            matches = re.findall(r"\(S(\d+)\)", action)
            speaker = matches[-1] if matches else None
            blocks = re.split(r"(?m)(?=^\s*<Subject\s+\d+>)", definitions)
            for block in blocks:
                subject_match = re.match(r"\s*<Subject\s+(\d+)>", block)
                if (subject_match and subject and subject_match[1] == subject) or (
                    speaker and re.search(r"\(S" + speaker + r"\)", block)
                ):
                    value = role(block.split("<Picture ", 1)[0])
                    if value is not None:
                        return value
            return False

        if len(rows) == len(before):
            def voice_event(match):
                index = cursor.pop()
                cursor.append(index + 1)
                row = rows[index]
                if not is_voice(row):
                    return match[0]
                onset = max(0, row["start"])
                limit = rows[index + 1]["action_start"] if index + 1 < len(rows) else entry["planned_seconds"]
                cue = "At " + _stamp(onset) + ", the off-screen narrator begins the following complete line as one fluent, connected utterance. "
                cue += "Use natural phrase breaks only at its written punctuation; keep words connected through the visual action and reference changes. "
                cue += "Finish the line naturally within this shot, then leave the remaining action to the requested music and ambience. "
                events.append(
                    {
                        "source_block": row["source_block"],
                        "onset": onset,
                        "deadline": limit,
                        "pause_before": row["pause_before"],
                    }
                )
                return cue + match[0]

            head, separator, body = segment["prompt"].partition("detailed_description:\n")
            detail, separator_2, tail = body.partition("overall_soundscape:\n")
            events = []
            cursor = [0]
            detail = re.sub(r"<d>.*?</d>", voice_event, detail, flags=re.S)
            if events:
                detail += (
                    "\nThe scheduled voice entry takes priority over a musical introduction. "
                    "Music and effects accompany the narrator underneath; they do not delay or restart the spoken line.\n"
                )
                segment["prompt"] = head + separator + detail + separator_2 + tail
                assert re.findall(r"<d>.*?</d>", segment["prompt"], flags=re.S) == before, "voice_entry_dialogue_changed"
                segment["native_voice_entry"] = {
                    "version": "no_ref_voiceover_entry_v2",
                    "events": events,
                    "frame_budget_unchanged": True,
                }
    return segment


run_duration_projection = _run(build_duration_projection)
run_projection_apply = _run(build_projection_apply)
run_clip_timing = _run(build_clip_timing)
