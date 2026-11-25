"""Shot-scope nodes 720004, 720005, and 720013. Dialogue spans are compared, not rewritten."""

from __future__ import annotations

import json
import re

from .serialize import pack_error, pack_success

_KEYS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)


def _run(builder):
    def run(input_text, input_json=""):
        text = "" if input_text is None else input_text
        extra = "" if input_json is None else input_json
        try:
            return pack_success(builder(text, extra))
        except Exception as exc:
            return pack_error(exc)

    return run


def _blank(match):
    return " " * len(match[0])


def _fields(prompt):
    masked = re.sub(r"<d>.*?</d>", _blank, prompt, flags=re.S)
    marks = [("\n" + masked).find("\n" + key + ":\n") for key in _KEYS]
    return marks, {
        key: prompt[marks[index] + len(key) + 2 : marks[index + 1] if index < 5 else len(prompt)].strip()
        for index, key in enumerate(_KEYS)
    }


def _person(line):
    words = set(re.findall(r"[a-z]+", line.lower()))
    return bool(words.intersection(["person", "woman", "man", "girl", "boy", "face", "facial", "hair", "speaker", "actor", "model"])) or any(
        word in line for word in ("人物", "女性", "男性", "人脸")
    )


def build_shot_scope(segment_text: str, env_text: str):
    segment = json.loads(segment_text)
    env = json.loads(env_text)
    if not env["inventory"]["audios"] and not segment.get("raw_passthrough") and env["structured"]:
        prompt = segment["prompt"]
        before = re.findall(r"<d>.*?</d>", prompt, flags=re.S)
        marks, fields = _fields(prompt)
        assert marks == sorted(marks) and min(marks) >= 0, "shot_scope_sections"
        source = env["source"]
        head = source.split("summary:", 1)[0].removeprefix("subject_definitions:").strip()
        mapping = dict(zip(segment["original_slots"], range(1, 10)))

        def picture(match):
            return "<Picture " + str(mapping[int(match[1])]) + ">"

        def refs(text):
            return re.sub(r"<Picture\s+(\d+)>", picture, text)

        detail = fields["detailed_description"]
        start = re.search(r"(?m)^\s*\[Shot\s+\d+\]", detail)
        current = detail[start.start() :] if start else detail
        empty = bool(
            segment["visual_only"]
            and any(
                word in current.lower()
                for word in (
                    "people-free", "people free", "unpopulated", "unoccupied",
                    "no people are visible", "no people in the frame", "all people are out of frame",
                    "无人空镜", "无人画面",
                )
            )
        )
        definitions = []
        for line in head.splitlines():
            if not line.strip():
                continue
            if empty and _person(line):
                continue
            definitions.append(refs(line))
        fields["subject_definitions"] = "\n".join(definitions) or (
            "Use only the explicitly requested scene and object attributes of the supplied references."
        )
        opening = re.split(r"\n\s*\n|<d>", current.strip(), maxsplit=1)[0]
        opening = re.sub(r"^\s*\[Shot\s+\d+\]\s*", "", opening)
        fields["summary"] = "[reference generation] Render the current authored shot as a newly generated scene. " + opening
        retain = source.partition("retention_analysis:")[2].partition("detailed_description:")[0]
        rows = []
        for line in retain.splitlines():
            shot_ids = {int(number) for number in re.findall(r"\bShot\s+(\d+)\b", line, re.I)}
            if shot_ids and segment["shot"] + 1 not in shot_ids:
                continue
            if empty and _person(line):
                continue
            line = re.sub(r"\[Shot\s+\d+\]", "[Shot 1]", line)
            line = re.sub(r"(\[Shot 1\])(?:,\s*\[Shot 1\])+", r"\1", line)
            if line.strip():
                rows.append(refs(line))
        rows.append(
            "Reference images supply only their declared attributes; do not display a reference still, face card, "
            "collage, or additional scene. Render the current shot as a full-frame scene."
        )
        if empty:
            fields["detailed_description"] = current
            rows.append(
                "This shot is explicitly unpopulated. Person and clothing references are inactive here. "
                "Keep all people outside the image."
            )
            segment["crop_source"] = 0
            segment["identity_subjects"] = []
            fields["summary"] = (
                "[reference generation] An unpopulated scene; render only the objects and setting described in this shot. "
                + re.split(r"\n\s*\n|<d>", current.strip(), maxsplit=1)[0]
            )
            fields["overall_soundscape"] = (
                "No human vocal sound occurs in this shot. Produce only the room tone, physical object sounds, "
                "or ambience explicitly requested in detailed_description. Do not import any sound or spoken line from another shot."
            )
            music = []
            for clause in re.split(r"(?<=[.!?])\s+", fields["non_diegetic_music"]):
                if any(word in clause.lower() for word in ("spoken", "dialogue", "narration", "speaking")):
                    continue
                music.append(clause)
            fields["non_diegetic_music"] = " ".join(music)
        if "NO subtitles" in env.get("caption_policy", ""):
            rows.append(
                "Reference screenshots are partially_preserved: preserve only the declared people, objects, garments, "
                "actions and physical environment. Exclude source-image subtitles, screen captions, title cards, "
                "playback controls, search boxes and player interfaces. Physical product labels and scene signage "
                "requested by the user remain part of the scene."
            )
        fields["retention_analysis"] = "\n".join(rows)
        if start:
            fields["detailed_description"] = fields["detailed_description"].replace(
                ", cut back to ", ", From the first frame, show ", 1
            ).replace(", cut to ", ", From the first frame, show ", 1)
        out = "\n".join(key + ":\n" + fields[key] for key in _KEYS)
        assert re.findall(r"<d>.*?</d>", out, flags=re.S) == before, "shot_scope_dialogue_changed"
        segment["prompt"] = out
        segment["shot_scope"] = {
            "version": "no_voice_current_shot_v1",
            "explicit_empty": empty,
            "source_shot": segment["shot"],
            "duration_unchanged": True,
            "reference_slots_unchanged": True,
        }
    return segment


def build_empty_scene_scope(segment_text: str, env_text: str):
    segment = json.loads(segment_text)
    env = json.loads(env_text)
    if not env["inventory"]["audios"] and segment.get("shot_scope", {}).get("explicit_empty"):
        prompt = segment["prompt"]
        slots = segment["original_slots"]
        used = sorted({int(number) for number in re.findall(r"<Picture\s+(\d+)>", prompt)})
        header = prompt.split("summary:", 1)[0]
        proven = set()
        for line in header.splitlines():
            refs = [int(number) for number in re.findall(r"<Picture\s+(\d+)>", line)]
            scene = any(
                word in line.lower()
                for word in ("scene", "environment", "interior", "landscape", "location", "场景", "环境", "背景")
            )
            if scene:
                proven.update(refs)
        if used and set(used) <= proven and len(used) < len(slots):
            selected = [slots[number - 1] for number in used]
            assert all(number in env["inventory"]["images"] for number in selected), "invalid_scoped_reference"
            mapping = dict(zip(used, range(1, len(used) + 1)))

            def label(match):
                return "<Picture " + str(mapping[int(match[1])]) + ">"

            segment["prompt"] = re.sub(r"<Picture\s+(\d+)>", label, prompt)
            segment["reference_scope"] = {
                "reason": "explicit_empty_scene",
                "available_slots": slots,
                "selected_slots": selected,
                "excluded_slots": [number for number in slots if number not in selected],
                "label_mapping": {str(key): value for key, value in mapping.items()},
            }
            segment["original_slots"] = selected
            segment["slot_indices"] = selected + [0] * (9 - len(selected))
            for index, value in enumerate(segment["slot_indices"], 1):
                segment["slot_" + str(index)] = value
            segment["bindings"] = [
                {
                    "original_slot": number,
                    "local_picture": index,
                    "subject_ids": [],
                    "subject_roles": ["scene"],
                    "roles": ["scene"],
                    "role": "scene",
                }
                for index, number in enumerate(selected, 1)
            ]
            segment["crop_source"] = 0
            segment["identity_subjects"] = []
            assert re.findall(r"<d>.*?</d>", prompt, flags=re.S) == re.findall(
                r"<d>.*?</d>", segment["prompt"], flags=re.S
            ), "scoped_dialogue_changed"
    return segment


def build_shot_opening(segment_text: str, env_text: str):
    segment = json.loads(segment_text)
    env = json.loads(env_text)
    if not env["inventory"]["audios"] and not segment.get("raw_passthrough") and (env["structured"] or env["normalize"]):
        prompt = segment["prompt"]
        before = re.findall(r"<d>.*?</d>", prompt, flags=re.S)
        marks, fields = _fields(prompt)
        assert marks == sorted(marks) and min(marks) >= 0, "shot_start_sections"

        def opening_boundary(text):
            stripped = text.lstrip()
            if not stripped.lower().startswith("[shot "):
                return text
            label, separator, body = stripped.partition("]")
            if not separator:
                return text
            body = body.lstrip()
            clock = ""
            for mark in [",", ";", "，", "："]:
                head, split, rest = body.partition(mark)
                if split:
                    words = head.lower().split()
                    allowed = "to and s sec secs second seconds - – —".split()
                    valid = (
                        len(words) > 1
                        and words[0] in ["at", "from", "between"]
                        and all(word in allowed or word.replace(":", "").replace(".", "").isdigit() for word in words[1:])
                    )
                    if valid and (words[0] != "at" or ":" in head or words[-1] in allowed):
                        clock = body[: len(head) + 1] + " "
                        body = rest.lstrip()
                        break
            if body.startswith("During the corresponding action"):
                body = body[len("During the corresponding action") :].lstrip(" ,;:，：")
            intro = re.match(
                r"(?i)^matching\s+<picture\s+\d+>(?:(?:,?\s*(?:and(?: transitioning into)?\s+)?<picture\s+\d+>)*\.\s+|,\s+)",
                body,
            )
            if intro:
                clock += intro[0]
                body = body[intro.end() :].lstrip()
            words = body.split(None, 12)
            lower = [word.lower() for word in words]
            used = 0
            for word in lower:
                if word not in "the camera scene shot video we smooth smoothly hard direct directly".split():
                    break
                used += 1
            if len(lower) <= used or lower[used] not in ["cut", "cuts", "cutting", "transition", "transitions", "transitioning"]:
                return text
            used += 1
            if len(lower) > used and lower[used] == "back":
                used += 1
            if len(lower) <= used + 1 or lower[used] not in ["to", "into"]:
                return text
            used += 1
            target = body.split(None, used)[used]
            first = target.split(".", 1)[0].split(";", 1)[0].lower()
            if any(
                word in " " + first + " "
                for word in (
                    " after ", " before ", " once ", " when ", " until ", " then ",
                    " later ", " over ", " during ", " at ", " if ", " unless ",
                )
            ):
                return text
            return label + "] " + clock + "From the first frame, show " + target

        def project(match):
            visible, tag, dialogue = match[0].partition("<d>")
            fixed = opening_boundary(visible)
            if fixed != visible:
                fields["summary"] = fields["summary"].replace(
                    visible.partition("]")[2].lstrip(), fixed.partition("]")[2].lstrip(), 1
                )
            return fixed + tag + dialogue

        fields["detailed_description"] = re.sub(
            r"(?m)^\s*\[Shot \d+\][^\n]*", project, fields["detailed_description"], count=1
        )
        identity = {}
        anchors = set()
        for line in env["source"].splitlines():
            if re.search(r"first frame|last frame|keyframe|composition anchor|starts? from|ends? on", line, re.I):
                anchors.update(int(number) for number in re.findall(r"<Picture (\d+)>", line))
        for binding in segment.get("bindings", []):
            if binding["roles"] != ["speaker_identity"] or len(binding["subject_ids"]) != 1:
                continue
            if binding["original_slot"] not in anchors:
                identity[binding["local_picture"]] = binding["subject_ids"][0]
        for key in ("subject_definitions", "retention_analysis"):
            rows = []
            for line in fields[key].splitlines():
                match = re.match(r"\s*<Picture (\d+)>:\s*", line)
                if match and int(match[1]) in identity:
                    content = re.sub(r"^fully_preserved", "partially_preserved", line[match.end() :])
                    line = "<Subject " + identity[int(match[1])] + ">" + " attributes from <Picture " + match[1] + ">: " + content
                rows.append(line)
            fields[key] = "\n".join(rows)
        segment["prompt"] = "\n".join(key + ":\n" + fields[key] for key in _KEYS)
        assert re.findall(r"<d>.*?</d>", segment["prompt"], flags=re.S) == before, "shot_start_dialogue_changed"
    return segment


run_shot_scope = _run(build_shot_scope)
run_empty_scene_scope = _run(build_empty_scene_scope)
run_shot_opening = _run(build_shot_opening)
