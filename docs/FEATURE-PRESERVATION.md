# Feature-preservation ledger

**PRE_RH_VALIDATION / PARTIAL / NOT DEPLOYABLE.** 211 classes replace 224 executor instances in the private 539-node workflow. No GPU inference has been run. RunningHub has not accepted this package.

Cumulative. A node not listed here is still an original executor or an untouched business input.

Replaced ids are unique. 224 instances total. No code-runner executor remains. Real GPU inference has not been run. These notes do not close the gaps in `docs/PRE-RH-AUDIT.md`.

## First batch (19)

| IDs | Class | Preserved |
| --- | --- | --- |
| 1300–1311 | `PPCMediaMissing` | Missing is `None`, `""`, numeric `0` (so `False` counts), or `["digits", 0]`. No truthiness coercion. |
| 99050007 | `PPCVideoInventory` | `type(x) is int` and `x > 0`. Bool and float are empty slots. |
| 500000 | `PPCReferenceInputAdapter` | Flag envelope, present slots are `false`/`0`, reference errors, dialogue exclusion. |
| 500009 | `PPCStoryboardParser` | `rh-native-source-v1`, shot order, voice ownership, spoken text copied. |
| 500012 | `PPCVoiceRoute` | `with_voice` is true only when `mode == "with_voice"`. |
| 99050001, 99050002, 99050003 | `PPCResultGuard` | Stage order and public reason whitelist. Success does not build a rejection video. |

## Measured storyboard clock (9)

| ID | Class | Preserved |
| --- | --- | --- |
| 760011 | `PPCStoryboardNormalize` | Spoken words are copied into `<d>`. Audio flags `false`/`0` mean the slot is present, so a Chinese shot list is not rewritten. Overlapping authored clocks still raise `storyboard_clock_order`. Non-sequential shot numbers stay raw text. |
| 500024 | `PPCPausePolicy` | Silent-hold spans. Speech deadlines are removed before the hold sum. Dialogue tags are not holds. |
| 500021 | `PPCClockBridge` | Row `text` is copied. `fixed_total` and `deadline` stay 120 because the original queue uses those placeholders. Measured seconds are applied later by `PPCClockToWindows`, not by this node. |
| 500030 | `PPCClockToWindows` | Window length is the sum of supplied timeline `seconds`. A text mismatch raises `dialogue_changed`. |
| 500031 | `PPCDurationPlan` | With voice, frame count is quantized from the measured window seconds. Without voice, weights come from authored clocks or existing text length. Joined segment text must equal joined row text. |
| 730003 | `PPCMeasuredDialogueBind` | Refuses a finished queue whose joined text differs from the storyboard. Split rows copy measured text fields that the queue already contains. |
| 400275 | `PPCExactLine` | The queued `text` is not edited. `emotion is 0` stays `has_emotion` true and `emotion_index` 0, because `0 or 1` is the original index expression. `None` is not an emotion. |
| 760012 | `PPCCustomDuration` | Automatic mode returns the options object unchanged. Custom mode only scales numbers already on the estimate. |
| 400478 | `PPCSpeechEdgeTrim` | Trim uses measured `duration_seconds`, sample rate, and silence fields. A non-finite or non-positive duration is rejected. The public error prefixes the original reason and does not add a traceback. |

## Automatic-duration compilers (14)

720012 is `easy cleanGpuUsed`. It is a GPU-cache node, not a compiler, and it is not replaced.

| IDs | Class | Preserved |
| --- | --- | --- |
| 720010 | `PPCDialogueIntervalSplit` | A without-voice line is split only when its original weight exceeds 95. The chunks concatenate to the original text. |
| 720011 | `PPCLongEstimateSplit` | Estimates whose frames exceed 719 are split. Dialogue text is not rewritten. |
| 770008 | `PPCNativeWindowSplit` | The original per-window 30-second split rule. It does not set the film duration to 30 seconds. |
| 720008 | `PPCFrameGridFit` | Pending windows are fitted to the original 1440-frame ceiling. Missing `_native_windows_pending` is an error. |
| 500020 | `PPCWithoutVoiceDurationPlan` | `selected_seconds` must be finite and inside 4..60. `clock_end <= 120` is the original validation bound, not an output of 120. Joined segment text equals joined row text. |
| 720003 | `PPCTimingHints` | Authored clocks, including rejection of `1.5s` shorthand and `hh:mm:ss`. |
| 720007 | `PPCCausalPace` | Pause and pace numbers already written in the action text. |
| 720001 | `PPCAutoDurationEstimate` | Default mode stays `自动时长`. The 60-second value is the original fit ceiling, not a forced duration. |
| 720002, 720006, 720009 | projection and clip assembly | Clocks outside `<d>` may move. The `<d>` spans stay byte-for-byte. |
| 720004, 720005, 720013 | shot scope and opening | Empty-audio shots can be scoped. Dialogue tags are asserted equal before the prompt is replaced. |

These nodes are tested one at a time. They still sit beside the measurement while-loop and the H3 sampler, so this is not an integrated timeline run.

## Pure text and JSON planning (145)

Each id is its own `PPCFixed<id>` class. The body is the original script, compiled as a normal function. Nothing in this tranche reads `python_code` at runtime. Differential tests compare every id with the original script on empty input, broken JSON, `with_voice`, `without_voice`, non-finite `selected_seconds`, and the dialogue bytes `你好，世界`.

One scope difference is explicit. In the runner, the script runs in a flat namespace, so a name read before assignment is `NameError: name 'p' is not defined`. Inside a function, that same read is `UnboundLocalError`. The wrapper reports that outer-function case as the runner's `NameError`. An `UnboundLocalError` raised inside a nested function is left as `UnboundLocalError`. Node 400510 hits the outer case when JSON fails before `p` is bound. Success paths are unchanged.

Clarity `1701` still maps `720P` to `0.9`. Aspect `1601` still maps `竖屏` to `9:16 (Portrait Widescreen)`. Last-frame `730023` still returns `decoded_count - 1` and still raises when the count is 0. Pause attachment `400475` still stores `参考音频停顿检测未返回有效结果。` on bad JSON and does not set `has_error`. Delivery bridge `762018` still copies `native_audio_seconds` onto `current.seconds`. Inventory slice `500104` still keeps images and caption policy and drops the prompt.

The offline candidates `7801101`–`7801685`, except `7801602`, are the pure JSON glue around the measurement loop: scope stages, continuation, coaxial crop metadata, and opening text. Porting them does not run the while-loop host or a TTS node.

`7801602` is `PPCFixed7801602`. Ordinary `isinstance` runs the route. That is a deliberate bug-fix: the VRGDG sandbox raised `NameError` before the route, and that failure is not preserved. Dialogue inside `<d>` is not rewritten. A positive dense two-voice fixture applies the route; a one-voice fixture and an `<Audio>` tag inside `<d>` do not.

## RefMod selection, identity PNG, and native export (34)

| IDs | Class | Preserved |
| --- | --- | --- |
| 9482010, 9482011 | positive and latent pick | The object in `bundle['positive']` or `bundle['latent']` is returned. A non-dict raises `VIP_REFMOD_BUNDLE_INVALID` instead of becoming a string result. |
| 9482141, 9482020, 9482022, 9482024, 9482026, 9482028, 9482030, 9482032, 9482034, 9482036 | window 0–9 | `bundle['positive'][k]`. A bad window is a failure object whose iteration raises `ValueError`. |
| 9482021–9482037 odd ids | latent index 1–9 | The fixed name `_VIP_CHAR_FILEMODE_WINDOWS` wins over the bundle. A short list returns `ExecutionBlocker(None)`. |
| 9482038 | report gate | The fixed name `_VIP_CHAR_FILEMODE_REPORT` must be JSON with `success: true`. |
| 9482042 | conditioning type gate | A string raises `VIP_COND_IS_STR`. A nested non-scalar sequence passes. The socket type is `*` because the runner could only declare STRING. No link pointed at it. |
| 9482045 | conditioning recover | A non-string passes through. A string is replaced only by a non-string entry in the fixed window store. |
| 9482110–9482117 | identity PNG 0–7 | One window returns the original tiny PNG and opens nothing. A character pack is length-prefixed JSON plus float16 bytes, not pickle. SHA-256 and size are checked before torch is imported. A bad digest's `.encode()` raises. |
| 97020001 | native export | `metadata` is forced to `None`. Both an audio stream and a video stream are required. Packet payload, timing, frame count, dimensions, and the rational frame rate must match. Failure writes no delivered file. |

Frame-rate comparison is a deliberate bug-fix. The original compared `str(Fraction(8))` (`"8"`) with PyAV's `"8/1"` and rejected an unchanged rate. The check now compares the rational values.

## RefMod file mode and the unique-id boundary

`9482009` is `PPCRefModSingle`. `9482140` is `PPCRefModMultiWindow`. Both call the static modules under `refmod_pinned/`. Those modules are the decoded pack, imported normally. `load_pinned_author` checks core sha256 `e9a2a03e6402e93d95c94c4b15dd244847582c3f614ec43dd7465f5176f690d6` and does not compile the bytes. Single conditioning uses `runtime_single.generate_conditioning`. Person plus product uses one `runtime_joint.generate_dual_conditioning` call. Reference video bytes are written with PyAV, not an ffmpeg subprocess. Photo mode returns `ExecutionBlocker(None)` and does not encode.

The schema assumed by the asset bridge, taken from the pinned `inspect_asset_bytes` checks: one F16 latent named `latent`, shape `[1, 24, 8, H, W]`, H and W even, metadata `refmod_meta` with format version 4, kind `video`, mode `encode`, source `stack`, concept type `identity`, and zero optimize steps. A corrupt or extra-key header is rejected. This is not pickle.

`9482017` is `PPCExecutorBoundary`. It returns `executor-free` and does not replace `builtins.int` or `builtins.__import__`. `coerce_dotted_unique_id("9.8.7")` is 7, and the builtin `int` still rejects that string. The old patch existed so IDENode could tolerate dotted Comfy ids and stringified conditioning. No IDENode remains, and the conditioning pickers return the original objects.

GPU inference through MiniMax H3 CLIP/VAE is still untested. A missing or non-H3 VAE raises from the static runtime; the node does not invent a conditioning tensor.

## Explicitly not replaced

- Node 720012, `easy cleanGpuUsed`.
- The measurement while-loop host, TTS synthesis, audio analyzers, and samplers. Those were never these executor scripts.

`ExecutionBlocker(None)` on a guard output stops a downstream node in the real PromptExecutor. `PublicRejectionVideo` raises `ValueError` from `get_dimensions()` before `SaveVideo` writes a file. A unit test that only constructs the blocker is not that proof. The unpatched host run is recorded in `TRANCHE5-TEST-REPORT.md`, which is not part of this distribution.

## Pre-RH audit, 0.7.0

Node `414015` no longer contains a deployment account prefix. A relative `output/selflift_auto_segment_<name>.mp4` still passes. An absolute path passes only when `PPC_FRAGMENT_ROOT` is set to that directory and the next segment is 32 lowercase hex characters. `..` still fails. `PPCExecutorBoundary` and both RefMod entries normalize a dotted `UNIQUE_ID` or `idenode_loop_guard` at the call. They do not patch builtins, and they do not wrap `SelfLiftH3Sampler`. An unreadable or hash-mismatched pinned core raises `ValueError` and is not executed. A synthetic 8-frame 16x16 encode through PyAV is 8 frames at 24 fps with no audio stream. Byte equality with ffmpeg is not required.
