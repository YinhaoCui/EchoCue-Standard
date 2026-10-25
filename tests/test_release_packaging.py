"""Check the portable package layout without bundling a real Python installation."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


spec = importlib.util.spec_from_file_location('package_release', Path(__file__).resolve().parents[1] / 'tools/package_release.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class ReleasePackagingTests(unittest.TestCase):
    def test_echocue_package_includes_both_languages_and_excludes_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'source'
            python = Path(folder) / 'python'
            output = Path(folder) / 'output'
            files = {
                'EchoCue.exe': 'test launcher',
                'app/assets/echocue.png': 'test icon',
                'vendor/dependency.py': '',
                'runtime/asr/model.onnx': 'test model',
                'runtime/Release/whisper-cli.exe': 'batch ASR',
                'runtime/Release/whisper.dll': 'batch runtime',
                'runtime/Release/test-vad.exe': 'unused diagnostic',
                'runtime/ggml-base.bin': 'batch model',
                'tools/login_antigravity.cmd': '',
                'tools/asr_models.json': '{}',
                'README.md': '[中文](README_ZH.md)\n<img src="app/assets/echocue.png" />',
                'README_ZH.md': '[English](README.md)',
                'CHANGELOG.md': '# Changelog',
                'VERSION': '1.0.0',
                'requirements.txt': '',
                'docs/USER_GUIDE.md': '# EchoCue',
                'data/settings.dpapi': 'private settings',
                'work/transcript.txt': 'private transcript',
            }
            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
            for name in ('DLLs', 'Lib'):
                (python / name).mkdir(parents=True)
            (python / 'python.exe').write_bytes(b'test runtime')
            with patch.object(packager, 'ROOT', root), patch.object(packager.sys, 'base_prefix', str(python)), \
                    patch.object(packager.sys, 'argv', ['package_release.py', '--output', str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                packager.main()
            archive = output / 'EchoCue-1.0.0-windows-x64.zip'
            self.assertTrue(archive.with_suffix('.zip.sha256').is_file())
            with zipfile.ZipFile(archive) as bundle:
                prefix = 'EchoCue-1.0.0-windows-x64/'
                names = bundle.namelist()
                for name in ('EchoCue.exe', 'README.md', 'README_ZH.md', '_internal/app/assets/echocue.png'):
                    self.assertIn(prefix + name, names)
                self.assertIn(b'src="_internal/app/assets/echocue.png"', bundle.read(prefix + 'README.md'))
                self.assertEqual(bundle.read(prefix + 'VERSION'), b'1.0.0')
                for name in ('Release/whisper-cli.exe', 'Release/whisper.dll', 'ggml-base.bin'):
                    self.assertIn(prefix + '_internal/runtime/' + name, names)
                self.assertNotIn(prefix + '_internal/runtime/Release/test-vad.exe', names)
                self.assertFalse(any('/data/' in name or '/work/' in name for name in names))
