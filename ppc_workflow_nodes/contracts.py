"""Identity of the first batch. Hashes identify scripts; they are not the scripts."""

from __future__ import annotations

MEDIA_IDS = tuple(range(1300, 1312))
VIDEO_ID = 99050007
ADAPTER_ID = 500000
PARSER_ID = 500009
VOICE_ID = 500012
GUARD_IDS = {
    99050001: "inventory",
    99050002: "parser",
    99050003: "voice_json",
}

MEDIA_CODE_SHA256 = "1a479c57097e2614b83eb8504cee18355b547d2cdc5c94c4a2e65a89e4ff642f"
VIDEO_CODE_SHA256 = "c49f4505037fd8b7859f9081a62ccf3f2fdc535ac7bf531cd7d938936c2fd5ac"
ADAPTER_CODE_SHA256 = "0016bff3ec2a0826be76acd8d906b1fac94707cd8deb34a555010fb5d1b9c12e"
PARSER_CODE_SHA256 = "1232794eadb757e63b578eec847c31b681f49d2108aa257b54bfdebddbd3ef4d"
VOICE_CODE_SHA256 = "7d68cf9b091f2b521a025be6f38b74b11b538cf0966639491977629a0c0b405f"
GUARD_CODE_SHA256 = {
    99050001: "6225b88133a10bb9a4488494c7b3b2f6f685fa0c641a5cf923013f5b2d09ee4c",
    99050002: "57c5c86eeb6bd552e77438670a2aaaec460d4bce1ef3573c235352da0ee7aedb",
    99050003: "687c623883fc0cdc653a1be192fec2b4aa3bbfd57c0ab2100743862d0a7329fa",
}

# 21 public controls named by the graph group title, plus the 14 character,
# product, and scene fields that bring the workflow API surface to 35.
# Node 1700, 1600, and 760010 keep an incoming link and a widget default.
BUSINESS_INPUT_IDS = (
    232,
    150,
    164,
    1003,
    1004,
    1005,
    1006,
    1007,
    1008,
    1009,
    1101,
    1102,
    1103,
    910100,
    910101,
    910102,
    1800,
    1700,
    1600,
    760010,
    132,
    9482000,
    9482001,
    9482002,
    9482003,
    9482004,
    9482005,
    9482016,
    9482090,
    9482091,
    9482092,
    9482093,
    9482130,
    9482131,
    9482132,
)

# Measured storyboard clock. Each script is a pure function of its inputs.
# Duration numbers come from those inputs; none of these nodes invent a TTS length.
TRANCHE2 = (
    {
        "id": 760011,
        "class_type": "PPCStoryboardNormalize",
        "sha256": "215d348295c3f04810c397af9d92d10281dd741727daed07448b4896574dcbeb",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 500024,
        "class_type": "PPCPausePolicy",
        "sha256": "28af18c21adbe30aaedfcb98e6d9c2435fa7f6b68dbcf0fef200e20980d63dff",
        "linked": (("input_text", "STRING"),),
    },
    {
        "id": 500021,
        "class_type": "PPCClockBridge",
        "sha256": "02018aa77d75903b345070df7fbaed197763be48664dd763f8fd848df98fa257",
        "linked": (("input_text", "STRING"),),
    },
    {
        "id": 500030,
        "class_type": "PPCClockToWindows",
        "sha256": "6ef29d9df4d339c96792aeb922e46764f7b4fd0f369d2f12b43a31a9ae26d6ef",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 500031,
        "class_type": "PPCDurationPlan",
        "sha256": "37433cfeeb34c3d54913aa1116550ee2544a8b3f92f74e88a5914d6b4921ae99",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 730003,
        "class_type": "PPCMeasuredDialogueBind",
        "sha256": "bc576e62603658c72ade94aa8732f5e80d162036d32a61e55056be28f730a9f7",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 400275,
        "class_type": "PPCExactLine",
        "sha256": "f26c220595355cd80cead99b9387aede55ab8a062930823041216a12e2a19953",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 760012,
        "class_type": "PPCCustomDuration",
        "sha256": "455af3eeacace08b28d9c7bce926fbf11a6cf09b5a5da507ca4f23355264b38f",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
    {
        "id": 400478,
        "class_type": "PPCSpeechEdgeTrim",
        "sha256": "2ec3480b2e5bff594e87075080f080d083de61cd5b20b13b47777a131a18ac2e",
        "linked": (("input_text", "STRING"), ("input_json", "STRING")),
    },
)
TRANCHE2_IDS = tuple(item["id"] for item in TRANCHE2)
TRANCHE2_BY_ID = {item["id"]: item for item in TRANCHE2}
RUNNER_OUTPUTS = (
    ("result_text", "STRING"),
    ("result_json", "STRING"),
    ("has_error", "BOOLEAN"),
)

SOURCE_NODE_COUNT = 539
SOURCE_LINK_COUNT = 1087
SOURCE_SHA256 = "0268d3f9a7313536434660fc5be5f84da201ad48d775d7c1c0cd2cb2efe5a08c"
EXECUTOR_TYPES = ("VRGDG_PythonCodeRunner", "IDENode")
# Automatic-duration compilers. 720012 is easy cleanGpuUsed and is not in this set.
TRANCHE3 = (
    {"id": 720010, "class_type": "PPCDialogueIntervalSplit", "sha256": "9a115c331a3a55387947a855b55d0ed11ce03c2da33ae99843acce7aa85bc0a5", "linked": (("input_text", "STRING"),)},
    {"id": 720011, "class_type": "PPCLongEstimateSplit", "sha256": "859ca03e361caad5f522c908c03153c44f2837fce5ed28db58b9294d4a3c240a", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 770008, "class_type": "PPCNativeWindowSplit", "sha256": "7de019796aa4907142580414f8b5617b6285bb126a33179e828e3d50e311b905", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720008, "class_type": "PPCFrameGridFit", "sha256": "13ed8419c32092548ec3e3b06caf76227555fa638a13a76ea71b012f5e1b669c", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 500020, "class_type": "PPCWithoutVoiceDurationPlan", "sha256": "58e3c6d28f3401ac98cbf2c9cd00f1ec8c74ac6f39fc972957a6b497758b3d3d", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720003, "class_type": "PPCTimingHints", "sha256": "8aa15873ed2ebe24d735b805d0e5bcfde5a524645cba16edaa2688afa1f00597", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720007, "class_type": "PPCCausalPace", "sha256": "47a829e4db391d7022d9b8b816f158672c9d845cfdd4b52880d6ca3d16e55218", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720001, "class_type": "PPCAutoDurationEstimate", "sha256": "d56af35a379bba5a6da6e08057709eeb44091c6036af9d2729575a1a9c1cf254", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720002, "class_type": "PPCDurationProjection", "sha256": "8ec9f3c50969fd0c0c16e9a7614e05742ef5b11cb169cf4660ec9912db935af2", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720006, "class_type": "PPCTimingProjectionApply", "sha256": "058f61d3cc66844f3e7fef5847292db02b3786922bd60a8bbe660f305e47f8f9", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720009, "class_type": "PPCClipTimingAssembly", "sha256": "84d298a17a7aca1f7ec81e6ad8348e0cea4ff48a7743fb4cc2ab2113c61ef815", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720004, "class_type": "PPCShotScope", "sha256": "10c17303494dc3b319fc5e806806502fe24db46717835449e90364b283da5293", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720005, "class_type": "PPCEmptySceneScope", "sha256": "f3eaa56054aaffd15220a97852d428a93c240fd7821a3d89bf22414b2055ae7e", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
    {"id": 720013, "class_type": "PPCShotOpening", "sha256": "9e8b444cce986a4f5010342fefcf11c61d8c8576048d7274bab148d7f4d2f27e", "linked": (("input_text", "STRING"), ("input_json", "STRING"))},
)
TRANCHE3_IDS = tuple(item["id"] for item in TRANCHE3)
TRANCHE3_BY_ID = {item["id"]: item for item in TRANCHE3}

FIRST_BATCH_COUNT = 19
TRANCHE2_COUNT = 9
TRANCHE3_COUNT = 14
TRANCHE4_COUNT = 145
# 7801602 is replaced in tranche 5. The sandbox NameError is a recorded deviation.
TRANCHE4_EXCLUDED = ()
TRANCHE5_COUNT = 37
REPLACED_COUNT = FIRST_BATCH_COUNT + TRANCHE2_COUNT + TRANCHE3_COUNT + TRANCHE4_COUNT + TRANCHE5_COUNT
REMAINING_EXECUTORS = 0

PARTIAL_STATUS = "PARTIAL"
PARTIAL_REASON = (
    "PRE_RH_VALIDATION / PARTIAL / NOT DEPLOYABLE. Replaced all 224 executor instances. "
    "No VRGDG_PythonCodeRunner or IDENode remains. "
    "Node 720012 is easy cleanGpuUsed and was not replaced. "
    "RefMod file mode calls the static pinned API; real GPU model inference has not been run. "
    "RunningHub has not validated this graph."
)
