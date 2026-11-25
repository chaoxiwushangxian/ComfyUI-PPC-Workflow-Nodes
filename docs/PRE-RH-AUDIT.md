# Pre-RH audit, package 0.7.0

**PRE_RH_VALIDATION / PARTIAL / NOT DEPLOYABLE.** 211 classes replace 224 executor instances in the private 539-node workflow. No GPU inference has been run. RunningHub has not accepted this package.

This is a review package for the 224 executor replacements. It is not a RunningHub acceptance and not a GPU render. The 539-node count below is an audit count. This distribution does not include that workflow.

## Counts

- Unit tests on system Python 3.12.3, no torch: 74 ran, 73 passed, 1 skipped (PyAV missing).
- The skipped PyAV test passed on the unpatched CPU venv: 8 frames, 16x16, rate 24, no audio stream.
- Replaced instances: 224. Registered classes: 211. Remaining IDENode or PythonCodeRunner: 0.
- Business inputs still equal to the source: 35. Candidate nodes: 539. Links: 1087.
- Host: ComfyUI `0d0e105153c02261519a6a552c52ec1cd5d9855e`, torch `2.15.0+cpu`, torchvision `0.29.2+cpu`, CUDA false. The earlier patched torchvision venv was not used.
- The package loaded through `nodes.load_custom_node`. Five checked classes were present in the host registry.
- H3 names present and not called: `_empty_av_latent`, `_resize`, `adapt_canvas`, module `_encode_ref_audio`, `MiniMaxH3ReferenceToVideo`. The class has no `_encode_ref_audio` method. The pinned code uses the module function first.
- Mixed chain actually executed: `PPCResultGuard` parser output into `PPCFixed760016`, then that text into `PPCFixed760017`. Dialogue `你好，世界` is still in both results and both `has_error` flags are false.

## What the host does not register

Listed in `docs/RH-INSTALL.md`. Schemas for those types were not invented. `nodes_glsl` failed to import because `comfy_angle` is absent; that extra is not used by this graph.

## Gaps that block functional acceptance

- No model weights, no GPU, no MiniMax H3 encode was run.
- Third-party nodes listed in the install note are absent from this checkout.
- Dotted ids inside `SelfLiftH3Sampler` and the other original patch targets are not normalized by this package.
- `PPC_FRAGMENT_ROOT` must be set on the platform if absolute fragment paths are still passed to node `414015`.
