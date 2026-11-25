"""Shared reference scan used by the input adapter and the storyboard parser."""

from __future__ import annotations

import re

FAMILIES = {"Picture": "images", "Audio": "audios", "Video": "videos"}
LABELS = {"Picture": "普通参考图", "Audio": "参考音频", "Video": "参考视频"}
ALIAS_NAMES = {
    "参考图片": "Picture",
    "参考图": "Picture",
    "图片": "Picture",
    "图": "Picture",
    "image_": "Picture",
    "image": "Picture",
    "参考音频": "Audio",
    "参考音色": "Audio",
    "音频": "Audio",
    "音色": "Audio",
    "参考视频": "Video",
    "视频": "Video",
}
TAG_PATTERN = re.compile(r"<(Picture|Audio|Video)\s+(\d+)>")
ALIAS_PATTERN = re.compile(
    r"@(参考图片|参考图|图片|图|image_|image|参考音频|参考音色|音频|音色|参考视频|视频)\s*(\d+)"
)
MISSING_SUFFIX = (
    "。请上传到对应编号槽位，或将提示词改为已上传的同类素材编号。"
    "独立场景槽 scene_1–4 不计入普通参考图 Picture 编号。"
)


def validate_references(source: str, inventory: dict) -> None:
    outside_dialogue = " ".join(re.split(r"<d>.*?</d>", source, flags=re.S))
    missing = {"Picture": [], "Audio": [], "Video": []}
    for family, slot in TAG_PATTERN.findall(outside_dialogue):
        number = int(slot)
        if number not in inventory[FAMILIES[family]] and number not in missing[family]:
            missing[family].append(number)
    for spelling, slot in ALIAS_PATTERN.findall(outside_dialogue):
        family = ALIAS_NAMES[spelling]
        number = int(slot)
        if number not in inventory[FAMILIES[family]] and number not in missing[family]:
            missing[family].append(number)
    details = []
    for family in ("Picture", "Audio", "Video"):
        if missing[family]:
            codes = "、".join(family + str(i) for i in sorted(missing[family]))
            details.append(LABELS[family] + " " + codes)
    if details:
        raise ValueError(
            "missing_reference: 以下引用没有对应的已上传素材："
            + "；".join(details)
            + MISSING_SUFFIX
        )
