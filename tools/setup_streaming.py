"""Install pinned streaming ASR wheels and checksum-verified local models."""
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def download(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def main(models_only=False):
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Windows x64 is required.')
    tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
    for name, version in ([] if models_only else [('numpy', '2.5.3'), ('sherpa-onnx-core', '1.13.8'), ('sherpa-onnx', '1.13.8'), ('webrtcvad-wheels', '2.0.14.post1')]):
        metadata = json.loads(download(f'https://pypi.org/pypi/{name}/{version}/json'))
        entry = next((x for x in metadata['urls'] if x['filename'].endswith(f'-{tag}-{tag}-win_amd64.whl')
                      or x['filename'].endswith('-py3-none-win_amd64.whl')), None)
        if entry is None:
            raise RuntimeError(f'No compatible {name} wheel for {tag}. Use Python 3.12-3.14 x64.')
        blob = download(entry['url'])
        if hashlib.sha256(blob).hexdigest() != entry['digests']['sha256']:
            raise RuntimeError('Wheel checksum mismatch: ' + name)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            archive.extractall(ROOT / 'vendor')
        print('Installed', name, version, flush=True)
    manifest = json.loads((ROOT / 'tools/asr_models.json').read_text(encoding='utf-8'))
    for relative, info in manifest.items():
        target = ROOT / relative
        if not target.resolve().is_relative_to((ROOT / 'runtime/asr').resolve()):
            raise ValueError('Invalid model path')
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == info['sha256']:
            continue
        print('Downloading', relative, flush=True)
        blob = download(info['url'])
        if hashlib.sha256(blob).hexdigest() != info['sha256']:
            raise RuntimeError('Model checksum mismatch: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.part')
        temporary.write_bytes(blob)
        temporary.replace(target)
    print('Streaming ASR setup complete.', flush=True)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--models-only',action='store_true')
    main(models_only=parser.parse_args().models_only)
