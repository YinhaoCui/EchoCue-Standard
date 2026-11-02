"""Download the pinned upstream Windows x64 DLX component and its MIT license."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v1.3.1'
ASSETS = {
    'deeplx.exe': (
        f'https://github.com/OwO-Network/DLX/releases/download/{VERSION}/deeplx_windows_amd64.exe',
        'fa1107779606222578568053381989a2e921db270a10dd8128bd9dd2b7857f4b'),
    'LICENSE.txt': (
        f'https://raw.githubusercontent.com/OwO-Network/DLX/{VERSION}/LICENSE',
        '07d8087d9d722927de7a76beea85fae9f23348ce410aea1daf9159bdc7ae76c7'),
}


def main():
    target = ROOT / 'runtime' / 'dlx'
    target.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in ASSETS.items():
        path = target / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            continue
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('DLX download checksum mismatch: ' + name)
        path.write_bytes(data)
    print('DLX ' + VERSION + ' ready (Windows x64).', flush=True)


if __name__ == '__main__':
    main()
