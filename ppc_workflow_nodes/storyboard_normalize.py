"""Node 760011. Structure-only adaptation of an explicit Chinese shot list.

Spoken words are copied into ``<d>`` tags. This module does not paraphrase them.
"""

from __future__ import annotations

import re

from .serialize import pack_error, pack_success

_SHOT = re.compile(
    r"(?m)^\s*(?:#{1,4}\s*)?(?:镜头|分镜)\s*(\d+)\s*[|｜:：、.）)]*\s*"
    r"(?:时长\s*[:：]\s*)?(\d+(?:\.\d+)?)\s*(?:秒|s)?\s*[-–—~～至到]\s*"
    r"(\d+(?:\.\d+)?)\s*(?:秒|s)\s*$"
)
_SPOKEN_KEYS = {
    "画外音": "旁白",
    "解说词": "旁白",
    "解说": "旁白",
    "voiceover": "旁白",
    "voice over": "旁白",
    "voice-over": "旁白",
    "narration": "旁白",
}
_SILENT = {
    "无",
    "无口播",
    "无台词",
    "无对白",
    "无旁白",
    "无配音",
    "无声",
    "不说话",
    "静默",
    "n/a",
    "none",
}
_HARD_CUT = {"硬切", "平滑硬切", "快速切镜", "微调焦点快速切镜"}
_OPEN_QUOTES = {"“", "「", "『", '"'}
_CLOSE_QUOTES = {"”", "」", "』", '"'}


def build_storyboard(raw: str, flags_text: str) -> str:
    source = raw
    flags = flags_text.split("|")
    no_voice = len(flags) >= 2 and all(
        item.strip().lower() in ("true", "1") for item in flags[1].split(",")
    )
    if no_voice and "detailed_description:" not in source and "<d>" not in source:
        marks = list(_SHOT.finditer(source))
        if marks and [int(mark[1]) for mark in marks] == list(range(1, len(marks) + 1)):
            head = source[: marks[0].start()].strip()
            shots = []
            duration = 0.0
            for index, mark in enumerate(marks):
                start = float(mark[2])
                end = float(mark[3])
                assert end > start and start >= duration, "storyboard_clock_order"
                duration = end
                body_end = marks[index + 1].start() if index + 1 < len(marks) else len(source)
                body = source[mark.end() : body_end].strip()
                lines = []
                for line in body.splitlines():
                    key, sep, words = line.replace("：", ":", 1).partition(":")
                    key = key.strip()
                    words = words.strip()
                    key = _SPOKEN_KEYS.get(key.lower(), key)
                    if sep and key in ("台词旁白", "台词", "口播", "口播文案", "旁白"):
                        if words.rstrip("。.!！ ").lower() in _SILENT:
                            line = "No spoken dialogue. Preserve requested music and physical sounds."
                        else:
                            if words[:1] in _OPEN_QUOTES and words[-1:] in _CLOSE_QUOTES:
                                words = words[1:-1]
                            offscreen = " says in an off-screen voiceover" if "旁白" in key else " says naturally"
                            line = "<Subject 1> (S1)" + offscreen + ": <d>[Chinese]" + words + "</d>"
                    if sep and key == "转场" and words.rstrip("。.!！ ") in _HARD_CUT:
                        line = (
                            "The edit to the next shot occurs only after this clip ends. "
                            "Render only the current shot continuously inside this clip."
                        )
                    lines.append(line)
                body = "\n".join(lines)
                shots.append(
                    "[Shot " + str(index + 1) + "] From " + str(start) + " to " + str(end) + " seconds,\n" + body
                )
            bgm = [
                line.strip()
                for line in head.splitlines()
                if line.strip().startswith(("背景音乐：", "BGM：", "BGM:"))
            ]
            music = (
                " ".join(bgm)
                if bgm
                else "Use only music explicitly requested alongside the current shot. No added vocal lyrics."
            )
            return (
                "subject_definitions:\n"
                + head
                + "\nsummary:\nTotal duration is "
                + str(duration)
                + " seconds. Follow the authored shots and actions in order.\n"
                "retention_analysis:\nPreserve the supplied references only in their user-declared roles.\n"
                "detailed_description:\n"
                + "\n\n".join(shots)
                + "\noverall_soundscape:\nGenerate only the physical sounds and music requested in the current shot. "
                "No unscripted speech.\nnon_diegetic_music:\n"
                + music
            )
    return source


def run_storyboard(input_text, input_json):
    raw = "" if input_text is None else input_text
    flags = "" if input_json is None else input_json
    try:
        return pack_success(build_storyboard(raw, flags))
    except Exception as exc:
        return pack_error(exc)


class PPCStoryboardNormalize:
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
    DESCRIPTION = "Adapt an explicit Chinese shot list without paraphrasing spoken words."

    def run(self, input_text, input_json):
        return run_storyboard(input_text, input_json)
