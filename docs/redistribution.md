# Redistribution and attribution

Reviewed 2026-09-18. This is a review of available licensing evidence, not a legal
opinion or guarantee of title. Fixed source revisions live in `installer.py`.

## Shipped material

| Component | Origin and license | Treatment |
| --- | --- | --- |
| `plugin/src/index.ts` | Newly authored against public SDK interfaces; Apache-2.0 | Does not copy the earlier ankh plugin implementation. |
| `backend/generation.py` | Derived from OrcaBonsai `run.py`, commit `947a80cd1d3b4f9a97417025e6c2c62223571287`; Apache-2.0 declaration | Origin and modification notice in file; full license at repository root. |
| API server, installer, launcher, tests | Local integration code; Apache-2.0 | No upstream model weights or ablation implementation is copied. |
| npm lockfile | Dependency metadata | Installed dependency code is excluded and keeps its own licenses. |

The Orca [upstream LICENSE](https://github.com/Continuum-AI-Corp/OrcaBonsai-27B-Uncensored/blob/main/LICENSE)
declares Apache-2.0 by reference, rather than reproducing its full terms. This
repository supplies the full license. The derived generation helper prominently
identifies its changes: callbacks, cancellation, and no implicit output cap.

## External downloads

- [Bonsai-demo](https://github.com/PrismML-Eng/Bonsai-demo/blob/main/LICENSE): Apache-2.0.
  The installer marks its local downloader change selecting the tested native release.
- [OrcaBonsai](https://github.com/Continuum-AI-Corp/OrcaBonsai-27B-Uncensored): cloned
  separately with original license and direction files intact.
- [Prism ML's model pack](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit):
  model card declares Apache-2.0. Its downloaded NOTICE credits Prism ML, Inc. and
  Alibaba Cloud/Qwen; runtime/LICENSE carries Apple's MIT notice. The entire
  snapshot, including these notices, is downloaded unchanged.
- The GGUF download includes the selected model and upstream README/LICENSE/NOTICE files.
- Native binaries come through Prism's downloader. LM Studio is installed separately;
  this adapter's license does not license redistribution of that application or CLI.
- uv, Python, npm, the SDK, and Python dependencies retain their respective licenses.
  They are installed separately and not bundled into this source release.

Do not upload `.runtime`, weights, `node_modules`, or binary installers without
reviewing the actual bundled artifacts and carrying their required notices.

## Original plugin attribution

[ankh's published metadata](https://lmstudio.ai/ankh/openai-compat-endpoint/files/package.json)
declares ISC, but the local copy lacks a standalone license and named copyright
holder. Its Hub ancestry credits tupik and will-lms. We credit these handles for
the prototype, but do not invent copyright notices or treat credit alone as a
redistribution grant. Their implementation is not included in this package.

## Notice obligations

[Apache-2.0 section 4](https://www.apache.org/licenses/LICENSE-2.0) requires a license
copy, modification notices, retention of relevant notices, and applicable NOTICE
contents. Section 6 does not grant general trademark rights. The root license
cannot relicense external components or imply endorsement.

The Prism notice requests “Created using Bonsai by Prism ML.” Its wording is an
appreciation request, not a separate compulsory advertising clause. Applicable
NOTICE contents must nevertheless be preserved for covered derivatives.
