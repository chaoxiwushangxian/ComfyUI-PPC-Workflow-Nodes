# PPC Workflow Nodes

**PRE_RH_VALIDATION / PARTIAL / NOT DEPLOYABLE.** 211 classes replace 224 executor instances in the private 539-node workflow. No GPU inference has been run. RunningHub has not accepted this package. Importing these nodes is not a finished film render and is not RunningHub usability.

Fixed-function ComfyUI nodes for that workflow. The nodes do not accept Python or JavaScript, and they do not call `exec`, `eval`, `compile`, or a subprocess.

All 224 `VRGDG_PythonCodeRunner` and `IDENode` instances have fixed functions. Node 720012 stays `easy cleanGpuUsed` and is not one of these 211 classes. RefMod file mode calls a static pinned API. A real GPU inference run has not been done. See `docs/RH-INSTALL.md` for host symbols and third-party node types this package does not provide, `docs/PRE-RH-AUDIT.md` for the 0.7.0 gaps, and `docs/FEATURE-PRESERVATION.md` for behavior the replacements still have to keep.

Nothing here uploads a repository, sends a task, or edits a live workflow.

## Install

The repository root is one ComfyUI custom-node folder. Copy this directory into `ComfyUI/custom_nodes/` and restart ComfyUI. No extra pip packages are required. `pyproject.toml` lists an empty dependency set on purpose. Do not pin or upgrade torch, CUDA, or ComfyUI to install this package. Python 3.10 or newer is assumed because the original scripts use that language level. The host ComfyUI build must provide `comfy_execution.graph_utils.ExecutionBlocker`.

`PPC_FRAGMENT_ROOT`, the MiniMax H3 names this revision actually calls, the third-party node types missing from the audited host, and dotted `UNIQUE_ID` handling remain testing requirements. They are listed in `docs/RH-INSTALL.md`. Satisfying one of them is not RunningHub acceptance.

## Nodes

| Class | Replaces | Inputs | Outputs |
| --- | --- | --- | --- |
| `PPCMediaMissing` | 1300–1311 | `optional_media` | `result` BOOLEAN |
| `PPCVideoInventory` | 99050007 | `video_1_frames`, `video_2_frames`, `video_3_frames` | `result` STRING |
| `PPCReferenceInputAdapter` | 500000 | `input_text`, `input_json` | `result_text`, `result_json`, `has_error` |
| `PPCStoryboardParser` | 500009 | `input_text` | same three runner outputs |
| `PPCVoiceRoute` | 500012 | `input_text` | same three runner outputs |
| `PPCResultGuard` | 99050001 inventory, 99050002 parser, 99050003 voice_json | `runner_text`, `runner_has_error`, closed `stage`, optional storyboard and caption pairs | `result`, `rejection` VIDEO, `invalid` |
| `PPCStoryboardNormalize` | 760011 | `input_text`, `input_json` | runner triple |
| `PPCPausePolicy` | 500024 | `input_text` | runner triple |
| `PPCClockBridge` | 500021 | `input_text` | runner triple |
| `PPCClockToWindows` | 500030 | `input_text`, `input_json` | runner triple |
| `PPCDurationPlan` | 500031 | `input_text`, `input_json` | runner triple |
| `PPCMeasuredDialogueBind` | 730003 | `input_text`, `input_json` | runner triple |
| `PPCExactLine` | 400275 | `input_text`, `input_json` | runner triple |
| `PPCCustomDuration` | 760012 | `input_text`, `input_json` | runner triple |
| `PPCSpeechEdgeTrim` | 400478 | `input_text`, `input_json` | runner triple |

`PPCResultGuard` returns the host `ExecutionBlocker(None)` on the text output when it rejects. The rejection object raises `ValueError` with the public reason from `get_dimensions()` and `save_to()`, which is the order `SaveVideo.execute` uses. Success leaves `rejection` as `None` and `invalid` as `False`.

## Fixed functions

The 145 `PPCFixed<id>` classes are ordinary Python functions. Each one is the reviewed script body, with the runner's success and error packing. They do not read a code string from the graph. A top-level read of a name before it is assigned is reported as `NameError`, which is what the runner's flat namespace raises. Node 7801602 is also a fixed function, and ordinary `isinstance` is intentional there: the sandbox `NameError` was not the route. The package does not pin or upgrade torch, CUDA, or ComfyUI.

A check that the system interpreter has no torch is not scheduler proof. It is not a GPU inference run, and it is not RunningHub acceptance.

## What this package does not do

It does not change the 35 business-input nodes, and it does not run the measurement while-loop, TTS, a sampler, or a GPU model. This distribution does not include the native graph, a candidate graph, private tests, fixtures, `migration-boundary.json`, or user assets. Leaving those out does not close the gaps in `docs/PRE-RH-AUDIT.md`.

## License

`LicenseRef-Proprietary`, as declared in `pyproject.toml`. This publication does not add a different license. The pinned files under `ppc_workflow_nodes/refmod_pinned/` keep their existing MIT notice: Copyright (c) 2026 Luisa (luisacaotica).
