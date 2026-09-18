# OrcaBonsai LM Studio Adapter

Run **Bonsai 2** and **OrcaBonsai** locally and switch between them with a dropdown
in LM Studio. The installer downloads both model formats, Python dependencies,
native runtime, and installs the included LM Studio plugin.

**Experimental first release. Apple Silicon macOS only.** This is an independent
community integration, not an official release from Prism ML, Continuum AI, or LM Studio.

## Quick install

Install and open [LM Studio](https://lmstudio.ai/download) in `/Applications` first.
Apple Command Line Tools must be present for Git; if missing, follow Apple's
`xcode-select --install` prompt and rerun. These are the only manual prerequisites.
No separate Python, Node, npm, or API key is required.

```sh
git clone https://github.com/bgigurtsis/orcabonsai-lmstudio-adapter.git
cd orcabonsai-lmstudio-adapter
./Install.command
./Launch.command
```

Alternatively download this repository as a ZIP, unzip into a permanent folder,
and open `Install.command`, followed by `Launch.command`. Git/Command Line Tools
are still needed to fetch the upstream source repositories.

In LM Studio:

1. Select **bgigurtsis/orcabonsai-lmstudio-adapter** from the top model selector.
2. In Configuration, choose **Bonsai 2 (native)** or **OrcaBonsai (MLX)**.
3. Send a message. Reasoning defaults to Off.

Keep the launcher's terminal open. **Ctrl-C stops the servers it started** without
leaving background GPU workers. Open `Launch.command` next time. Keep the repository
folder in place: its ignored `.runtime/` directory holds the downloaded components.

## What gets installed

- A pinned Astral uv release and private Python 3.12 environment.
- Fixed upstream revisions of Bonsai-demo and OrcaBonsai.
- A tested Prism llama.cpp binary release and official GGUF and MLX model snapshots.
- Orca's Python dependencies plus the local API server dependencies.
- This repository's newly written LM Studio plugin, under its own name.

Allow **at least 25 GiB free disk space** before installation; more is preferable
for caches and updates. Both are 27B model formats, so the download is substantial
and duration depends on your connection. A Mac with 32 GB or more unified memory
is recommended, with more room useful for long context and other apps. No minimum
memory or throughput benchmark is claimed.

The installer checks required files. The MLX model loads on its first generation;
a listening server alone does not establish that model loading has completed.
Repeated installation will not reset modified upstream checkouts. If a later release
changes the pinned commits, use a fresh directory. For a read-only source plan,
run `python3 installer.py --plan` with Python 3.12 or newer.

## Behavior

| Selection | Backend | Default endpoint |
| --- | --- | --- |
| Bonsai 2 | Native Prism llama.cpp, original GGUF | `http://127.0.0.1:18124/v1` |
| OrcaBonsai | Python/MLX using upstream Orca | `http://127.0.0.1:18123/v1` |

- Text chat only in this release. Images, attachments, and tool integrations are
  unsupported; disable integrations and use a fresh text-only conversation.
- Ordinary Orca replies stream. Reasoning-enabled replies are currently buffered
  until completion; use Off for immediate visible text.
- No default or hard output-token cap is imposed by the Orca API or plugin.
  Generation ends naturally or when you press Stop. Explicit budgets from other
  API clients are honored. Underlying context and memory limits still apply.
- One Orca generation runs at a time. Concurrent requests receive a clear busy
  error instead of silently waiting. Stop the other chat or wait, then retry.
- Chat traffic stays on loopback. Downloads contact upstream providers, but chat
  messages are not sent to them. The plugin accepts only loopback HTTP endpoints.
- Existing plugins and Bonsai installations are not overwritten.

## Troubleshooting

- **Connection refused:** open `Launch.command` and leave it running.
- **Orca busy:** stop the response in the other chat or wait for it to finish.
- **Slow first response:** MLX loads on its first request. Orca and native Bonsai
  use different runtimes and are not expected to have equal speed.
- **Startup failure:** inspect `.runtime/bonsai-2.log` and `.runtime/orcabonsai.log`.
- **Occupied ports:** use `BONSAI_PORT` and `ORCABONSAI_PORT` when launching and
  match the plugin's endpoint settings; do not kill unrelated services.
- **Strange model output:** verify the complete pinned MLX snapshot, including
  `runtime/` and tokenizer files. The specialized upstream loader is required.

## Attribution and licensing

Created using Bonsai by Prism ML.

Thanks to [PrismML-Eng/Bonsai-demo](https://github.com/PrismML-Eng/Bonsai-demo),
[Continuum-AI-Corp/OrcaBonsai](https://github.com/Continuum-AI-Corp/OrcaBonsai-27B-Uncensored),
Prism ML, Alibaba Cloud/Qwen, Apple MLX, and LM Studio.
The prototype used [ankh/openai-compat-endpoint](https://lmstudio.ai/ankh/openai-compat-endpoint),
whose published ancestry credits tupik and will-lms. Their plugin implementation
is not copied here: the shipped plugin is newly authored against the public SDK.

This repository uses [Apache-2.0](LICENSE). [NOTICE](NOTICE) and the
[redistribution review](docs/redistribution.md) identify derived code and external
components. We do not upload model weights, direction artifacts, native binaries,
LM Studio, credentials, or installed environments. The installer downloads external
components separately with their upstream licenses and notices intact.

## Development

After installation:

```sh
.runtime/python/bin/python -m unittest discover -s tests -v
```

Regression tests cover streaming before completion, Unicode, cancellation, busy
rejection, uncapped output, missing files, paths with spaces, and refusing to reset
a different upstream revision. The plugin is TypeScript-checked and its installation
into LM Studio is tested. This first release has not had a complete clean-machine
multi-gigabyte install; tests used an existing dependency environment and model files.
