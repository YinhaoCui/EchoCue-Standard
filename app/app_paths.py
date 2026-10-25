"""Application paths. Importing this puts the bundled vendor packages on sys.path."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'vendor') not in sys.path:
    sys.path.insert(0, str(ROOT / 'vendor'))
def storage_root(root):
    """Installed builds keep user files outside the replaceable application folder."""
    root = Path(root)
    if (root / 'installed.flag').is_file():
        edition = root / 'EDITION'
        name = 'EchoCue Standard' if edition.is_file() and edition.read_text().strip() == 'standard' else 'EchoCue'
        return Path(os.environ['LOCALAPPDATA']) / name
    return root


def data_path(root, name):
    return storage_root(root) / 'data' / name


WORK = storage_root(ROOT) / 'work'
WORK.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = data_path(ROOT, 'settings.dpapi')
