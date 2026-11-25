# RunningHub installation requirements

**PRE_RH_VALIDATION / PARTIAL / NOT DEPLOYABLE.** 211 classes replace 224 executor instances in the private 539-node workflow. No GPU inference has been run. RunningHub has not accepted this package.

This package is a pre-RH review build. It is not an acceptance result. Do not treat a successful import as a finished film render.

## This package

- Python 3.10 or newer.
- Copy the directory into `ComfyUI/custom_nodes/` and restart.
- Dependencies in `pyproject.toml` are empty. Do not pin or upgrade the host torch or CUDA for this package.
- The host must provide `comfy_execution.graph_utils.ExecutionBlocker`.
- Optional: `PPC_FRAGMENT_ROOT` set to the platform account directory so an absolute fragment path of the form `<root>/<32 hex>/output/selflift_auto_segment_<name>.mp4` is accepted. Relative `output/selflift_auto_segment_<name>.mp4` is accepted without that variable. `..` is rejected either way. No account directory is built into the package.

## Host symbols this revision's RefMod code calls

Checked present on ComfyUI `0d0e105153c02261519a6a552c52ec1cd5d9855e` as names only, not by running a model:

- `comfy_extras.nodes_minimax_h3._empty_av_latent`
- `comfy_extras.nodes_minimax_h3._resize`
- `comfy_extras.nodes_minimax_h3.adapt_canvas`
- `comfy_extras.nodes_minimax_h3._encode_ref_audio` (module function; the class has no `_encode_ref_audio` method)
- `comfy_extras.nodes_minimax_h3.MiniMaxH3ReferenceToVideo`
- `comfy.ldm.minimax.vae.MiniMaxH3VideoVAE` (imported when an encode runs)

Author commit recorded in the pinned bridge: `517e8c419a8584fbf69fceb487bc39d83e6a6ec8`. The comment in the reference module names ComfyUI `fd734e9` as the ordinary-node baseline. This host is newer. The names above exist. Their numeric behavior was not executed.

## Node types in the candidate that this ComfyUI checkout does not register

These are third-party or host-pack nodes. This package does not invent their schemas.

- ComfyUI-Easy-Use: `easy ifElse`, `easy isNone`, `easy blocker`, `easy cleanGpuUsed`, `easy convertAnything`, `easy anythingIndexSwitch`, `easy forLoopStart`, `easy forLoopEnd`, `easy whileLoopStart`, `easy whileLoopEnd`, `easy mergeVideosFromPaths`
- Video Helper Suite: `VHS_LoadVideo`, `VHS_SelectFilename`, `VHS_VideoCombine`
- ChatterBox: `ChatterBoxAudioAnalyzer`, `ChatterBoxAudioAnalyzerOptions`
- IndexTTS: `T8_IndexTTS25_ReferenceQuality`, `IndexTTS2BaseNode`
- LayerMask / YOLO: `LayerMask: ObjectDetectorYOLO8`, `LayerMask: DrawBBoxMaskV2`
- Other packs seen in the graph: `SelfLiftH3Sampler`, `H3SigmaRefiner`, `MiniMaxH3AudioGuideFeather`, `Base64ImageInput`, `InpaintCropImproved`, `ModelPreviewOverrideKJ`, `SoundFlow_GetLength`, `AudioFade`, `AudioInfoNode`, `AudioPad`, `GetBoolFromJson`, `GetFloatFromJson`, `GetIntFromJson`, `GetTextFromJson`, `LoadJsonFromText`, `StringToNumber`
- A graph node type named `ExecutionBlocker` is not the same object as `comfy_execution.graph_utils.ExecutionBlocker`. It was not in this host's node registry.

## Still required on the platform

- GPU inference with the real MiniMax H3 CLIP, video VAE, and audio VAE.
- A file-mode character pack that passes the v4 latent checks, then one joint person+product encode.
- The third-party nodes listed above.
- Dotted loop ids inside those third-party nodes. This package normalizes `UNIQUE_ID` only on its own entries. It does not patch `builtins.int`.
