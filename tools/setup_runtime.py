"""Install local, pinned Windows dependencies without changing system Python."""
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

def wheel(name, version):
    target = ROOT / 'vendor'
    metadata = json.loads(download(f'https://pypi.org/pypi/{name}/{version}/json'))
    tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
    entry = next((x for x in metadata['urls'] if f'{tag}-{tag}-win_amd64.whl' in x['filename']), None)
    if not entry and sys.version_info >= (3, 13):
        entry = next((x for x in metadata['urls'] if 'cp313-abi3-win_amd64.whl' in x['filename']), None)
    if not entry:
        raise RuntimeError(f'{name} does not have a wheel for {tag}; use 64-bit Python 3.12–3.14.')
    blob = download(entry['url'])
    if hashlib.sha256(blob).hexdigest() != entry['digests']['sha256']:
        raise RuntimeError('Download checksum mismatch')
    target.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(blob)).extractall(target)
    print(f'Installed {name} {version}', flush=True)

def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('This package requires Windows x64.')
    wheel('PyAudioWPatch', '0.2.12.9')
    if sys.version_info >= (3, 13):
        wheel('audioop-lts', '0.2.2')
    from setup_streaming import main as setup_streaming
    setup_streaming()
    print('Setup complete.', flush=True)

if __name__ == '__main__':
    main()
