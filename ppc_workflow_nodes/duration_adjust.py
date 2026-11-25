"""Nodes 760012 and 400478.

Custom duration scales numbers already present on the plan. Automatic mode
returns that plan unchanged. Speech-edge trim uses measured silence fields and
refuses the plan when those fields are not finite.
"""

from __future__ import annotations

import json
import math

from .serialize import pack_error, pack_success


def build_custom_duration(plan_text: str, options_text: str):
    plan = json.loads(plan_text)
    options = json.loads(options_text)
    if plan["mode"] == "without_voice" and options.get("duration_mode") == "自定义时长":
        info = options["duration_estimate"]
        entries = info["shots"]
        target = float(options["selected_seconds"])
        assert 4 <= target <= 60, "custom_seconds_outside4_60"
        weights = [max(0.01, entry["estimated_seconds"]) for entry in entries]
        steps = max(
            int(math.ceil((96 - 5 * len(entries)) / 17)),
            0,
            int(math.floor((target * 24 - 5 * len(entries)) / 17)),
        )
        quotas = [steps * weight / sum(weights) for weight in weights]
        allocation = [int(item) for item in quotas]

        def residual(index):
            return quotas[index] - allocation[index]

        for index in sorted(range(len(entries)), key=residual, reverse=True)[: steps - sum(allocation)]:
            allocation[index] += 1
        for entry, count in zip(entries, allocation):
            entry["frames"] = 5 + 17 * count
            available = entry["frames"] / 24
            ratio = available / max(entry["estimated_seconds"], 0.001)
            for field in ("speech_seconds", "silence_seconds", "tail_seconds"):
                entry[field] *= ratio
            for row in entry["rows"]:
                row["speech_seconds"] *= ratio
                row["pause_before"] *= ratio
            entry["estimated_seconds"] = available
        info.update(
            duration_mode="自定义时长",
            decision="custom_duration_applied",
            budget_sufficient=True,
            fallback_reasons=[],
            estimated_required_seconds=sum(entry["estimated_seconds"] for entry in entries),
        )
        options["estimated_frames"] = [entry["frames"] for entry in entries]
    return options


def build_speech_edge(measurement_text: str, row_text: str):
    row = json.loads(row_text)
    measurement = json.loads(measurement_text)["original"]
    try:
        total = float(measurement["duration_seconds"])
        if not math.isfinite(total) or total <= 0:
            raise ValueError("时长无效")
        start = 0.0
        duration = total + 0.001
        head_est = 0.0
        tail_est = 0.0
        if row["auto"]:
            sample_rate = float(measurement["sample_rate"])
            raw_head = float(measurement["leading_silence_seconds"])
            raw_tail = float(measurement["trailing_silence_seconds"])
            active = float(measurement["active_seconds"])
            if (
                not math.isfinite(sample_rate)
                or sample_rate <= 0
                or not 0 <= raw_head < total
                or not 0 <= raw_tail < total
                or not 0 < active <= total
                or raw_head + raw_tail >= total
            ):
                raise ValueError("未取得可靠的人声边界")
            frame = round(sample_rate * 0.03) / sample_rate
            factor = frame / 0.03
            head = raw_head * factor
            tail = max(0.0, total - (total - raw_tail) * factor)
            start = math.floor(max(0.0, head - 0.1) / frame) * frame
            excess = max(0.0, tail - 0.1)
            duration = total + 0.001 - start - excess
            if duration <= 0:
                raise ValueError("保留时长无效")
            head_est = min(duration, head - start + frame / 2)
            tail_est = min(duration, tail - excess + (0.001 if excess else 0.0) + frame / 2)
        row.update(trim_start=start, trim_duration=duration, edge_head=head_est, edge_tail=tail_est)
        return row
    except Exception as exc:
        raise ValueError("配音首尾检查未通过；已保留原始配音，停止画面生成：" + str(exc)) from exc


def run_custom_duration(input_text, input_json):
    text = "" if input_text is None else input_text
    extra = "" if input_json is None else input_json
    try:
        return pack_success(build_custom_duration(text, extra))
    except Exception as exc:
        return pack_error(exc)


def run_speech_edge(input_text, input_json):
    text = "" if input_text is None else input_text
    extra = "" if input_json is None else input_json
    try:
        return pack_success(build_speech_edge(text, extra))
    except Exception as exc:
        return pack_error(exc)


class PPCCustomDuration:
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
    DESCRIPTION = "Scale an existing without-voice estimate only in custom-duration mode."

    def run(self, input_text, input_json):
        return run_custom_duration(input_text, input_json)


class PPCSpeechEdgeTrim:
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
    DESCRIPTION = "Trim silence using measured analyzer fields. Does not accept code."

    def run(self, input_text, input_json):
        return run_speech_edge(input_text, input_json)
