# OrcaBonsai LM Studio Adapter

Run **Bonsai 2** and **OrcaBonsai** locally and switch between them with a dropdown
in LM Studio. The installer downloads the model files and the software needed to run them,
then adds a plugin to LM Studio.

**Experimental first release. Apple Silicon macOS only.** This is an independent
community integration, not an official release from Prism ML, Continuum AI, or LM Studio.

## Quick install

Install and open [LM Studio](https://lmstudio.ai/download) in `/Applications` first.
You also need Apple Command Line Tools, which include Git. If you do not have
them, run `xcode-select --install` in Terminal and follow the prompts.
These are the only things you need to install yourself.
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

Keep the launcher's terminal open. **Ctrl-C stops the servers it started** when you finish. Open `Launch.command` next time. Keep the repository
folder in place: the downloads are stored inside it in a folder called `.runtime/`.

## Why download two model formats?

One copy of the MLX model can run both versions. The upstream Orca software has
an `alpha` setting:

- `alpha=0` turns off Orca's changes and runs the original Bonsai model.
- `alpha=1` turns on Orca's changes and runs OrcaBonsai.

That approach worked, but both choices still used MLX, the software that runs
that model format. In our local setup, original Bonsai appeared faster using
Prism's native runner instead. We have not done a controlled speed comparison,
so this is an observation, not a promise about performance on your Mac.

This package therefore downloads the same base model in two formats:

- **GGUF** for original Bonsai, using Prism's native runner.
- **MLX** for OrcaBonsai, using the Orca software with `alpha=1`.

This takes more disk space than sharing one MLX copy. It keeps the two ways of
running the models that we used locally. The LM Studio dropdown chooses between
these two runners; it does not change `alpha` on a shared model. You do not need
to edit `alpha` yourself. A smaller, single-model install is not included here.

## What gets installed

The installer downloads both model formats, the software that runs them, a
private copy of Python 3.12, and the Python packages they need. It also installs
this project's LM Studio plugin. It uses specific versions of the main components
so people get the same setup. It does not overwrite your existing Bonsai setup.

Allow **at least 25 GiB of free disk space**; leave more room for temporary
files and future updates. The downloads are large and may take a while.
We suggest a Mac with **32 GB of memory or more**, but have not tested the minimum
memory requirement. Long conversations and other open apps need extra memory.

Orca loads its model into memory when you send the first message, so that reply
can take longer. The installer checks that the required files exist; this does
not prove the model will load successfully on every Mac.

If a future release changes the downloaded software versions, install it in a
new folder. Rerunning the installer does not reset changes you made to downloaded
source code. Developers can see the selected versions without downloading them
by running `python3 installer.py --plan` with Python 3.12 or newer.

## Using the models

| Model | Software used to run it | Local address |
| --- | --- | --- |
| Bonsai 2 | Native Prism llama.cpp, original GGUF | `http://127.0.0.1:18124/v1` |
| OrcaBonsai | Python/MLX using upstream Orca | `http://127.0.0.1:18123/v1` |

- Text chat only in this release. Images, attachments, and tool integrations are
  unsupported; disable integrations and use a fresh text-only conversation.
- With Reasoning set to Off, Orca shows its reply as it writes. With Reasoning
  enabled, the reply appears only after it finishes.
- The plugin and Orca server do not set a maximum reply length by default.
  A reply ends when the model finishes or you press Stop. Other apps calling the
  server can request a length limit. The model still has memory and conversation
  length limits.
- Orca answers one message at a time. If another chat is using it, you will
  see a busy message. Stop the other reply or wait for it to finish, then retry.
- The plugin sends your messages to servers on your own Mac. Installation
  needs internet access to download files; your chats are not sent to those
  download providers.
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
which credits earlier work by tupik and will-lms. This package includes a newly
written plugin using LM Studio's public development tools, rather than a copy
of their plugin.

This repository uses [Apache-2.0](LICENSE). [NOTICE](NOTICE) and the
[redistribution review](docs/redistribution.md) explain which code was adapted and which
components come from other projects. We do not upload model weights, direction artifacts, native binaries,
LM Studio, credentials, or installed environments. The installer downloads external
components separately with their upstream licenses and notices intact.

## Development

After installation:

```sh
.runtime/python/bin/python -m unittest discover -s tests -v
```

Regression tests cover streaming before completion, Unicode, cancellation, busy
rejection, uncapped output, missing files, paths with spaces, and refusing to reset
a different upstream revision. The plugin passes its TypeScript checks and was installed
successfully into LM Studio. **We have not yet tested the whole installation on
a clean Mac.** Tests used software and model files already on the development Mac.
