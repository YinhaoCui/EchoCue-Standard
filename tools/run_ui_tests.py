"""Run the browser tests for the web UI (needs requirements-dev.txt and Edge).

    python tools/run_ui_tests.py            # skips when Playwright is missing
    python tools/run_ui_tests.py --require  # fails instead (used by CI)
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT / 'tests_ui'))
import app_paths  # noqa: E402,F401  (puts the bundled vendor packages on sys.path)
if __name__ == '__main__':
    if '--require' in sys.argv:
        import playwright  # noqa: F401  (raise ImportError instead of skipping)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests_ui'), pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful() or ('--require' in sys.argv and bool(result.skipped)))
