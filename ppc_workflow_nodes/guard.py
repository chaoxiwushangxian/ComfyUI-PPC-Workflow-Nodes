"""Staged rejection guards for nodes 99050001, 99050002, and 99050003.

``stage`` is a closed enum. There is no code, expression, or function-name input.
"""

from __future__ import annotations

import json
import re

from .rejection import PublicRejectionVideo, host_execution_blocker

STAGES = ("inventory", "parser", "voice_json")

_MISSING_DETAIL = re.compile(
    r"missing_reference: 以下引用没有对应的已上传素材："
    r"(?:普通参考图 Picture[0-9]+(?:、Picture[0-9]+)*|参考音频 Audio[0-9]+(?:、Audio[0-9]+)*|参考视频 Video[0-9]+(?:、Video[0-9]+)*)"
    r"(?:；(?:普通参考图 Picture[0-9]+(?:、Picture[0-9]+)*|参考音频 Audio[0-9]+(?:、Audio[0-9]+)*|参考视频 Video[0-9]+(?:、Video[0-9]+)*))*"
    r"。请上传到对应编号槽位，或将提示词改为已上传的同类素材编号。独立场景槽 scene_1–4 不计入普通参考图 Picture 编号。"
)

_PARSER_REASONS = {
    "ambiguous_voice_ownership": "请在提示词中明确每个人物绑定的参考音频编号。",
    "dialogue_tag_boundaries": "请检查每段台词是否有配对的 <d> 和 </d>。",
    "empty_dialogue": "请补全台词或移除空台词段。",
    "shot_order_invalid": "请从镜头 1 开始按顺序连续编号。",
    "prompt_invalid": "请填写提示词并检查长度与格式。",
    "invalid_inventory": "请核对已上传素材槽位。",
    "invalid_voice_mode": "请保留任务号以便核查配音路由。",
}

_INVENTORY_REASONS = {
    "storyboard_clock_order": "请按顺序填写每个镜头的起止时间，结束时间须晚于开始时间。",
    "caption_mode_invalid": "请将字幕控制改成允许的选项，或恢复默认值。",
    "prompt_empty_or_over_24000_characters": "请填写提示词，并将全文控制在 24000 字符以内。",
    "reference_alias_conflict": "请删除冲突的素材别名，或让同一个别名指向同一编号槽位。",
    "bad_json": "请检查结构化提示词是否为有效 JSON 对象。",
    "selected_outside4_30": "请核对时长输入，使用有效的 4 到 30 秒数值。",
    "invalid_h3_fields": "请检查结构化提示词，规定的文本字段须使用字符串。",
    "empty_explicit_dialogue": "请补全台词或移除空台词段。",
    **_PARSER_REASONS,
}

_GENERIC = "PPC_RUNNER_FAILED: 提示词处理未完成。请核对分镜与素材；仍无法通过时请提供任务号。"
_VOICE_JSON = "PPC_INVALID_VOICE_JSON: 配音路由输出无效，with_voice 必须是 JSON 布尔值。请保留任务号以便核查。"


def _reasons_for(kind: str) -> dict:
    if kind == "inventory":
        return _INVENTORY_REASONS
    return _PARSER_REASONS


def public_reason(text, kind: str) -> str:
    if isinstance(text, str):
        _name, separator, detail = text.partition(": ")
    else:
        separator, detail = "", ""
    if separator and _MISSING_DETAIL.fullmatch(detail):
        return detail
    known = _reasons_for(kind)
    if separator and detail in known:
        return detail + ": " + known[detail]
    return _GENERIC


def _rejected(reason: str):
    blocker = host_execution_blocker()(None)
    return (blocker, PublicRejectionVideo(reason), True)


def _strict_voice_object(text):
    def strict_object(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("duplicate key")
            data[key] = value
        return data

    def reject_constant(_value):
        raise ValueError("non-JSON constant")

    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty")
    data = json.loads(
        text,
        object_pairs_hook=strict_object,
        parse_constant=reject_constant,
    )
    if type(data) is not dict or type(data.get("with_voice")) is not bool:
        raise ValueError("with_voice type")
    return data


def guard_runner(text, has_error, kind: str):
    if has_error is not False:
        return _rejected(public_reason(text, kind))
    if kind != "voice_json":
        return (text, None, False)
    try:
        _strict_voice_object(text)
    except (ValueError, RecursionError):
        return _rejected(_VOICE_JSON)
    return (text, None, False)


def run_guard(
    stage,
    runner_text,
    runner_has_error,
    storyboard_text=None,
    storyboard_has_error=None,
    caption_text=None,
    caption_has_error=None,
):
    if stage == "inventory":
        upstream = (
            (storyboard_text, storyboard_has_error),
            (caption_text, caption_has_error),
            (runner_text, runner_has_error),
        )
        if any(flag is None and text is None for text, flag in upstream[:2]):
            return guard_runner("", True, "inventory")
        for text, flag in upstream:
            if flag is not False:
                return guard_runner(text, flag, "inventory")
        return (runner_text, None, False)
    if stage == "parser":
        return guard_runner(runner_text, runner_has_error, "parser")
    if stage == "voice_json":
        return guard_runner(runner_text, runner_has_error, "voice_json")
    return guard_runner("", True, "parser")


class PPCResultGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "runner_text": ("STRING", {"forceInput": True}),
                "runner_has_error": ("BOOLEAN", {"forceInput": True}),
                "stage": (list(STAGES),),
            },
            "optional": {
                "storyboard_text": ("STRING", {"forceInput": True}),
                "storyboard_has_error": ("BOOLEAN", {"forceInput": True}),
                "caption_text": ("STRING", {"forceInput": True}),
                "caption_has_error": ("BOOLEAN", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "VIDEO", "BOOLEAN")
    RETURN_NAMES = ("result", "rejection", "invalid")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = (
        "Pass text through or block with ExecutionBlocker and a public VIDEO rejection. "
        "stage is inventory, parser, or voice_json."
    )

    def run(
        self,
        runner_text,
        runner_has_error,
        stage,
        storyboard_text=None,
        storyboard_has_error=None,
        caption_text=None,
        caption_has_error=None,
    ):
        return run_guard(
            stage,
            runner_text,
            runner_has_error,
            storyboard_text,
            storyboard_has_error,
            caption_text,
            caption_has_error,
        )
