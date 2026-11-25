"""Fixed replacement for the voice-route node (node 500012)."""

from __future__ import annotations

import json

from .serialize import pack_error, pack_success


def build_voice_result(input_text: str):
    parsed = json.loads(input_text)
    return {"with_voice": parsed["mode"] == "with_voice"}


def run_voice(input_text):
    text = "" if input_text is None else input_text
    try:
        return pack_success(build_voice_result(text))
    except Exception as exc:
        return pack_error(exc)


class PPCVoiceRoute:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"input_text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Read mode and emit with_voice only when it is exactly with_voice."

    def run(self, input_text):
        return run_voice(input_text)
