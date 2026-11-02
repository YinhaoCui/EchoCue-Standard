import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_dlx', Path(__file__).resolve().parents[1] / 'tools/setup_dlx.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupDlxTests(unittest.TestCase):
    def test_verified_download_is_cached_and_mismatch_is_never_written(self):
        data = b'pinned component'
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'ROOT', Path(folder)), \
                patch.object(setup, 'ASSETS', {'deeplx.exe': ('https://example.test/dlx', hashlib.sha256(data).hexdigest())}), \
                patch('urllib.request.urlopen', return_value=io.BytesIO(data)) as download:
            setup.main(); setup.main()
            download.assert_called_once()
            self.assertEqual((Path(folder) / 'runtime/dlx/deeplx.exe').read_bytes(), data)
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'bad')), \
                    patch.object(setup, 'ASSETS', {'LICENSE.txt': ('https://example.test/license', '0' * 64)}):
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    setup.main()
            self.assertFalse((Path(folder) / 'runtime/dlx/LICENSE.txt').exists())
