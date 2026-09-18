"""Supervise the two local servers; closing the launcher stops its own workers."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('ORCABONSAI_DATA', ROOT / '.runtime')).resolve()
NATIVE_PORT = int(os.environ.get('BONSAI_PORT', '18124'))
ORCA_PORT = int(os.environ.get('ORCABONSAI_PORT', '18123'))


def commands():
    upstream = Path(os.environ.get('ORCABONSAI_UPSTREAM', DATA / 'orca')).resolve()
    pack = Path(os.environ.get('ORCABONSAI_PACK', DATA / 'mlx')).resolve()
    model = Path(os.environ.get('BONSAI_MODEL', DATA / 'gguf/Ternary-Bonsai-2-27B-PQ2_0.gguf'))
    native = Path(os.environ.get('BONSAI_NATIVE', DATA / 'bonsai/bin/mac/llama-server'))
    python = Path(os.environ.get('ORCABONSAI_PYTHON', DATA / 'python/bin/python'))
    required = [model, native, python, pack / 'config.json',
                pack / 'runtime/vision_artifact.py', upstream / 'directions/refusal_dir.safetensors']
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError('Installation is incomplete. Run Install.command. Missing: ' + ', '.join(missing))
    return [
        (NATIVE_PORT, 'bonsai-2', [str(native), '-m', str(model), '--host', '127.0.0.1',
         '--port', str(NATIVE_PORT), '--alias', 'bonsai-2', '-ngl', '99', '-fa', 'on',
         '-c', '65536', '--jinja', '--temp', '1.0', '--top-p', '0.95', '--top-k', '20',
         '--parallel', '1', '--sleep-idle-seconds', '300', '--reasoning', 'off']),
        (ORCA_PORT, 'orcabonsai', [str(python), str(ROOT / 'backend/server.py')]),
    ]


def ready(port: int, model: str) -> bool:
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models', timeout=2) as response:
            models = json.load(response)['data']
        return any(item['id'] == model for item in models)
    except (OSError, ValueError, KeyError):
        return False  # A server still starting is not ready yet.


def stop(processes):
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()  # Do not leave an old inference worker consuming the GPU.
            process.wait()


def main(check=False):
    """Start and own both processes without killing unrelated local services.
    Why: previous background workers silently blocked new requests.
    If wrong: closing/relaunching the terminal can leave duplicate GPU workers.
    """
    specs = commands()
    if check:
        print('All required model and runtime paths exist. Model loading is checked on first generation.')
        return
    DATA.mkdir(exist_ok=True)
    env = dict(os.environ, ORCABONSAI_UPSTREAM=os.environ.get('ORCABONSAI_UPSTREAM', str(DATA / 'orca')),
               ORCABONSAI_PACK=os.environ.get('ORCABONSAI_PACK', str(DATA / 'mlx')),
               ORCABONSAI_PORT=str(ORCA_PORT), PYTHONUNBUFFERED='1')
    processes, logs = [], []
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        for port, model, command in specs:
            if ready(port, model):
                print(f'{model} already responding on port {port}; using it without taking ownership.')
                continue
            log = (DATA / f'{model}.log').open('a')
            logs.append(log)
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            processes.append(process)
            deadline = time.monotonic() + 120
            while not ready(port, model):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(f'{model} failed to start; see {DATA / (model + ".log")}')
                time.sleep(0.5)
            print(f'{model} ready on port {port}.', flush=True)
        subprocess.run(['open', '-a', 'LM Studio'], check=True)
        print('Select bgigurtsis/bonsai-switch, then choose a model.\nKeep this terminal open. Ctrl-C stops servers started by this launcher.', flush=True)
        while processes:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError('A server exited. Inspect the .runtime logs before restarting.')
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nStopping local servers...')
    finally:
        stop(processes)
        for log in logs:
            log.close()
        if processes:
            print('Servers stopped. You can close this Terminal window.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    main(parser.parse_args().check)
