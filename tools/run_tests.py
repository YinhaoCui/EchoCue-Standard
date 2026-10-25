"""Run application tests from any working directory."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'app'))
sys.path.insert(0,str(ROOT/'tests'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test*.py')
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(not result.wasSuccessful())
