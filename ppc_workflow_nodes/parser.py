"""Fixed replacement for the storyboard parser (node 500009).

Dialogue inside ``<d>`` tags is copied through. Alias normalization runs only
outside those tags. Nothing in this module rewrites spoken text.
"""

from __future__ import annotations

import json
import re

from .references import validate_references
from .serialize import pack_error, pack_success

_PARSER_ALIAS = re.compile(r"@(?:参考)?(图片|图|音频|音色|视频)\s*(\d+)")
_ALIAS_FAMILY = {
    "图片": "Picture",
    "图": "Picture",
    "音频": "Audio",
    "音色": "Audio",
    "视频": "Video",
}
_SHOT = re.compile(r"(?m)^[ \t]*\[Shot[ \t]+(\d+)\]")
_BACKGROUND = re.compile(
    r"background|music|sound effect|ambience|背景|音乐|音效|环境",
    re.I,
)


def _normalize_alias(match: re.Match) -> str:
    return "<" + _ALIAS_FAMILY[match[1]] + " " + match[2] + ">"


def _blank_dialogue(match: re.Match) -> str:
    return " " * len(match[0])


def build_parser_result(input_text: str):
    parsed = json.loads(input_text)
    source = parsed.get("prompt", "")
    assert source.strip() and len(source) <= 24000, "prompt_invalid"
    inventory = {}
    for name, cap in (("images", 9), ("audios", 3), ("videos", 3)):
        ids = parsed.get(name, [])
        assert len(ids) == len(set(ids)) and set(ids) <= set(range(1, cap + 1)), (
            "invalid_inventory"
        )
        inventory[name] = sorted(ids)
    pieces = re.split(r"(<d>.*?</d>)", source, flags=re.S)
    for index in range(0, len(pieces), 2):
        pieces[index] = _PARSER_ALIAS.sub(_normalize_alias, pieces[index])
    text = "".join(pieces)
    validate_references(text, inventory)
    if "detailed_description:" in text:
        header, body = text.split("detailed_description:", 1)
    else:
        header, body = "", text
    if "overall_soundscape:" in body:
        body, tail = body.split("overall_soundscape:", 1)
    else:
        tail = ""
    subject_defs = {}
    banks = {}
    voices = {}
    background = set()
    for line in header.splitlines():
        subject_ids = set(re.findall(r"<Subject\s+(\d+)>", line))
        pictures = [int(x) for x in re.findall(r"<Picture\s+(\d+)>", line)]
        audios = [int(x) for x in re.findall(r"<Audio\s+(\d+)>", line)]
        if len(subject_ids) == 1:
            sid = list(subject_ids)[0]
            subject_defs.setdefault(sid, []).append(line)
            banks[sid] = list(dict.fromkeys(banks.get(sid, []) + pictures))
            if audios:
                assert len(set(audios)) == 1, "ambiguous_voice_ownership"
                assert voices.get(sid, audios[0]) == audios[0], "ambiguous_voice_ownership"
                voices[sid] = audios[0]
        elif (
            not subject_ids
            and audios
            and _BACKGROUND.search(line)
        ):
            background.update(audios)
    voice_candidates = [x for x in inventory["audios"] if x not in background]
    masked = re.sub(r"<d>.*?</d>", _blank_dialogue, body, flags=re.S)
    marks = list(_SHOT.finditer(masked))
    if marks:
        assert [int(m[1]) for m in marks] == list(range(1, len(marks) + 1)), (
            "shot_order_invalid"
        )
    if marks:
        ranges = [
            (m.start(), marks[i + 1].start() if i + 1 < len(marks) else len(body))
            for i, m in enumerate(marks)
        ]
    else:
        ranges = [(0, len(body))]
    global_action = body[: marks[0].start()] if marks else ""
    shots = []
    rows = []
    for index, (start, end) in enumerate(ranges):
        chunk = body[start:end]
        parts = []
        cursor = 0
        ids = []
        for dialogue in re.finditer(r"<d>\[([^\]]+)\](.*?)</d>", chunk, re.S):
            action = chunk[cursor : dialogue.start()]
            words = dialogue[2]
            assert words.strip(), "empty_dialogue"
            people = re.findall(r"(?:<Subject\s+|\bS)(\d+)>?", action)
            sid = people[-1] if people else (
                list(subject_defs)[0] if len(subject_defs) == 1 else None
            )
            if sid is None and not subject_defs:
                sid = "1"
            local_audio = re.findall(r"<Audio\s+(\d+)>", action)
            voice = voices.get(sid)
            if local_audio:
                assert len(set(local_audio)) == 1, "ambiguous_voice_ownership"
                voice = int(local_audio[-1])
            if voice is None and len(voice_candidates) == 1 and len(subject_defs) <= 1:
                voice = voice_candidates[0]
            if voice_candidates:
                assert sid is not None and voice in voice_candidates, (
                    "ambiguous_voice_ownership"
                )
            row = {
                "source_block": len(rows),
                "shot": index,
                "subject": sid,
                "voice": voice,
                "text": words,
                "language": dialogue[1],
                "action": action,
                "raw_dialogue": dialogue[0],
            }
            rows.append(row)
            ids.append(row["source_block"])
            parts.append(row)
            cursor = dialogue.end()
        assert chunk.count("<d>") == len(parts) and chunk.count("</d>") == len(parts), (
            "dialogue_tag_boundaries"
        )
        shots.append(
            {
                "shot": index,
                "body": chunk,
                "parts": parts,
                "tail": chunk[cursor:],
                "source_blocks": ids,
                "text": "".join(row["text"] for row in parts),
                "global_action": global_action,
                "visual_only": not parts,
            }
        )
    mode = "with_voice" if rows and voice_candidates else "without_voice"
    return {
        "schema": "rh-native-source-v1",
        "source": source,
        "header": header,
        "tail": tail,
        "inventory": inventory,
        "subject_defs": subject_defs,
        "identity_banks": banks,
        "rows": rows,
        "shots": shots,
        "mode": mode,
    }


def run_parser(input_text):
    text = "" if input_text is None else input_text
    try:
        return pack_success(build_parser_result(text))
    except Exception as exc:
        return pack_error(exc)


class PPCStoryboardParser:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"input_text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Parse a prepared storyboard JSON object. Does not accept code."

    def run(self, input_text):
        return run_parser(input_text)
