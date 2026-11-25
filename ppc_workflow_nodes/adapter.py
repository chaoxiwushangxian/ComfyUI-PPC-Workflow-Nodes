"""Fixed replacement for the input adapter (node 500000)."""

from __future__ import annotations

import json
import math
import re

from .references import validate_references
from .serialize import pack_error, pack_success

POLICIES = (
    "detailed_description: The target video is in a realistic smartphone photography style, "
    "with natural skin texture and soft available light. The video frames remain entirely clean, "
    "with NO subtitles, captions, dialogue transcription, translated text, title cards, lower thirds, "
    "speech bubbles, overlay text, or watermarks at any time.",
    "Render visible text only when the user explicitly requests it. Never turn dialogue into captions. "
    "Physical text already in supplied reference scenes may remain.",
)
H3_KEYS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_FLAG_OK = ("true", "false", "0", "1")
_PRESENT = ("false", "0")
_LABEL_RE = re.compile(
    r"^\s*(?:口播文案|口播内容|配音文案|台词|对白|旁白|文案)\s*[:：]",
    re.M,
)
_SAY_RE = re.compile(
    r"^(?:\s*)(?:人物|主角|他|她|图片\d+|图\d+)\s*(?:说|讲|says)\s*[:：]\s*[“「『\"]",
    re.M,
)


def _policy_body(candidate: str) -> str:
    prefix = "detailed_description: "
    if candidate.startswith(prefix):
        return candidate[len(prefix) :]
    return candidate


def build_adapter_result(raw, flags_text):
    flags = flags_text.split("|")
    assert len(flags) == 4, "invalid_inventory"
    inventory = {}
    for name, text, cap in zip(("images", "audios", "videos"), flags[:3], (9, 3, 3)):
        values = text.split(",")
        assert len(values) == cap and all(
            v.strip().lower() in _FLAG_OK for v in values
        ), "invalid_inventory"
        inventory[name] = [
            i + 1 for i, v in enumerate(values) if v.strip().lower() in _PRESENT
        ]
    seconds = float(flags[3])
    assert math.isfinite(seconds), "selected_outside4_30"
    source = raw.strip()
    policy = ""
    for candidate in POLICIES:
        if source.endswith(candidate):
            source = source[: -len(candidate)].rstrip()
            policy = _policy_body(candidate)
            break
    if source.startswith("{"):
        parsed = json.loads(source)
        if all(k in parsed for k in H3_KEYS):
            assert all(str(parsed[k]) == parsed[k] for k in H3_KEYS), "invalid_h3_fields"
            for candidate in POLICIES:
                if candidate in parsed.get("exclusions", []):
                    policy = _policy_body(candidate)
            source = "\n\n".join(k + ":\n" + parsed[k] for k in H3_KEYS)
        elif parsed.get("schema") == "h3-director-json-v1":
            for candidate in POLICIES:
                if candidate in parsed.get("exclusions", []):
                    policy = _policy_body(candidate)
            parsed["exclusions"] = [
                x for x in parsed.get("exclusions", []) if x not in POLICIES
            ]
            source = json.dumps(parsed, ensure_ascii=False)
    assert source.strip() and len(source) <= 24000, "prompt_invalid"
    validate_references(source, inventory)
    structured = "<d>" in source or "detailed_description:" in source
    positive = False
    malformed = False
    if not structured and inventory["audios"]:
        label = _LABEL_RE.search(source)
        say = _SAY_RE.search(source)
        if label:
            positive = bool(source[label.end() :].strip())
            malformed = not positive
        if say:
            positive = True
    assert not malformed, "empty_explicit_dialogue"
    normalize = bool(not structured and (positive or not inventory["audios"]))
    notes = (
        "Declared uploaded references, with their original user roles: "
        + ", ".join("<Picture " + str(i) + ">" for i in inventory["images"])
        + "."
    )
    prepared = source
    if structured:
        if "detailed_description:" in prepared:
            prepared = prepared.replace(
                "detailed_description:", notes + "\ndetailed_description:", 1
            )
        else:
            prepared = (
                "subject_definitions:\nsummary:\n" + notes + "\ndetailed_description:\n" + prepared
            )
    return {
        "raw": raw,
        "source": source,
        "caption_policy": policy,
        "inventory": inventory,
        "selected_seconds": seconds,
        "structured": structured,
        "normalize": normalize,
        "raw_route": not (structured or normalize),
        "legacy_flags": ",".join(flags[:3]) + ",true,true,true",
        "parser_input": json.dumps(
            {"prompt": prepared, **inventory}, ensure_ascii=False
        ),
    }


def run_adapter(input_text, input_json):
    raw = "" if input_text is None else input_text
    flags_text = "" if input_json is None else input_json
    try:
        return pack_success(build_adapter_result(raw, flags_text))
    except Exception as exc:
        return pack_error(exc)


class PPCReferenceInputAdapter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Normalize the prompt and uploaded-slot flags. Does not accept code."

    def run(self, input_text, input_json):
        return run_adapter(input_text, input_json)
