"""Installed data survives app replacement; portable data stays alongside the app."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app_paths import data_path, storage_root


class AppPathsTests(unittest.TestCase):
    def test_portable_and_installed_storage_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'app'
            root.mkdir()
            self.assertEqual(data_path(root, 'settings.dpapi'), root / 'data/settings.dpapi')
            (root / 'installed.flag').touch()
            with patch.dict('os.environ', LOCALAPPDATA=str(Path(folder) / 'user')):
                self.assertEqual(storage_root(root), Path(folder) / 'user/EchoCue')
                self.assertEqual(data_path(root, 'sessions.sqlite3'), Path(folder) / 'user/EchoCue/data/sessions.sqlite3')
                (root / 'EDITION').write_text('standard')
                self.assertEqual(storage_root(root), Path(folder) / 'user/EchoCue Standard')
