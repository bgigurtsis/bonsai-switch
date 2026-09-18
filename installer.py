"""Install the pinned external components; never copy a user's existing setup."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / '.runtime'
APP = Path('/Applications/LM Studio.app/Contents/Resources/app/.webpack')
BONSAI_REV = 'c398c6eeef7533dd9398682cc1297e33670df0cd'
ORCA_REV = '947a80cd1d3b4f9a97417025e6c2c62223571287'
GGUF_REV = '6ed5e12bf84b7a63069882c91dd9e9218647d17b'
MLX_REV = '3f926b415992eaa2ae9dd7b573706494d6bbf787'


def run(args: list[str], cwd: Path = ROOT, env=None) -> None:
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def checkout(name: str, url: str, revision: str) -> Path:
    """Fetch one fixed source revision without resetting an existing checkout.
    Why: repeat installation must preserve local changes and upstream licenses.
    If wrong: an update can overwrite work or silently execute different code.
    """
    target = DATA / name
    if not target.exists():
        run(['git', 'clone', '--no-checkout', url, str(target)])
        run(['git', 'checkout', '--detach', revision], target)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
    if actual != revision:
        raise RuntimeError(f'{target} is at a different revision; use a fresh install directory.')
    return target


def install_npm() -> Path:
    """Fetch a pinned npm CLI and verify its published SHA-512 integrity.
    Why: LM Studio includes Node but users need not have npm on PATH.
    If wrong: unverified executable dependencies would enter the installer.
    """
    folder = DATA / 'npm'
    cli = folder / 'package/bin/npm-cli.js'
    if cli.exists():
        return cli
    with urllib.request.urlopen('https://registry.npmjs.org/npm/10.9.2', timeout=30) as response:
        metadata = json.load(response)['dist']
    archive = DATA / 'npm.tgz'
    urllib.request.urlretrieve(metadata['tarball'], archive)
    expected = metadata['integrity']
    actual = 'sha512-' + base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()
    if actual != expected:
        raise RuntimeError('npm download integrity mismatch')
    folder.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as package:
        package.extractall(folder, filter='data')
    archive.unlink()
    return cli


def download_model(python: Path, repo: str, revision: str, target: Path, patterns=None) -> None:
    code = ('import json,sys; from huggingface_hub import snapshot_download; '
            'snapshot_download(repo_id=sys.argv[1], revision=sys.argv[2], '
            'local_dir=sys.argv[3], allow_patterns=json.loads(sys.argv[4]))')
    run([str(python), '-c', code, repo, revision, str(target), json.dumps(patterns)])


def install() -> None:
    """Assemble both servers, downloaded weights, and the new LM Studio plugin.
    Why: a fresh user should not need any files from the developer's computer.
    If wrong: installation may appear complete with a missing runtime or model.
    """
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('Apple Silicon macOS is required.')
    node, lms = APP / 'bin/node', APP / 'lms'
    if not node.is_file() or not lms.is_file():
        raise RuntimeError('Install and open LM Studio in /Applications first.')
    DATA.mkdir(exist_ok=True)
    if not (DATA / 'mlx/config.json').exists() and shutil.disk_usage(DATA).free < 25 * 1024**3:
        raise RuntimeError('Allow at least 25 GiB of free disk space for the first installation.')
    uv = DATA / 'bin/uv'
    if not uv.is_file():
        raise RuntimeError('Start with Install.command, which installs uv and Python.')
    bonsai = checkout('bonsai', 'https://github.com/PrismML-Eng/Bonsai-demo.git', BONSAI_REV)
    orca = checkout('orca', 'https://github.com/Continuum-AI-Corp/OrcaBonsai-27B-Uncensored.git', ORCA_REV)
    python = DATA / 'python/bin/python'
    if not python.exists():
        run([str(uv), 'venv', '--python', '3.12', str(DATA / 'python')])
    run([str(uv), 'pip', 'install', '--python', str(python), '-r', str(orca / 'requirements.txt'),
         'fastapi==0.141.1', 'uvicorn==0.53.0', 'huggingface-hub==1.32.0'])
    # The tested newer Prism binary release supports the Bonsai 2 format on Apple Silicon.
    downloader = bonsai / 'scripts/download_binaries.sh'
    script = downloader.read_text()
    if 'prism-b10683-d8f26ee' in script:
        script = script.replace('prism-b10683-d8f26ee', 'prism-b10687-5d80cff')
        script = script.replace('#!/bin/sh', '#!/bin/sh\n# Modified by bonsai-switch: pinned tested native release.', 1)
        downloader.write_text(script)
    run(['sh', str(downloader)], bonsai)
    download_model(python, 'prism-ml/Ternary-Bonsai-2-27B-gguf', GGUF_REV, DATA / 'gguf',
                   ['*PQ2_0.gguf', 'LICENSE*', 'NOTICE*', 'README.md'])
    download_model(python, 'prism-ml/Ternary-Bonsai-2-27B-mlx-2bit', MLX_REV, DATA / 'mlx')
    npm = install_npm()
    env = dict(os.environ, PATH=str(node.parent) + os.pathsep + os.environ.get('PATH', ''))
    run([str(node), str(npm), 'ci', '--ignore-scripts'], ROOT / 'plugin', env)
    run([str(node), str(ROOT / 'plugin/node_modules/typescript/bin/tsc'), '--noEmit'], ROOT / 'plugin')
    run([str(lms), 'dev', '--install', '--yes'], ROOT / 'plugin', env)
    run([str(python), str(ROOT / 'launcher.py'), '--check'])
    print('\nInstalled. Open Launch.command, then choose bgigurtsis/bonsai-switch in LM Studio.')
    print('Use its Model dropdown to switch between Bonsai 2 and OrcaBonsai.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='Show fixed sources without downloading or installing')
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({'bonsai': BONSAI_REV, 'orca': ORCA_REV, 'gguf': GGUF_REV, 'mlx': MLX_REV,
                          'directory': str(DATA), 'plugin': 'bgigurtsis/bonsai-switch'}, indent=2))
    else:
        install()
