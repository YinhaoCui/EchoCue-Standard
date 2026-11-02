"""Build a clean portable Windows folder; never ship personal settings or sessions."""
from pathlib import Path
import shutil
import argparse
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
def release_version(value):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9]+)*',value):
        raise ValueError('Invalid release version')
    return value

def ignore(folder,names):
    return [n for n in names if n in ('__pycache__','tests','test','.pytest_cache','.git') or n.endswith(('.pyc','.pyo','.pdb'))]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default=(ROOT/'VERSION').read_text().strip(),type=release_version)
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    parser.add_argument('--dependencies',type=Path,default=ROOT,help='Source of vendor and runtime directories')
    args=parser.parse_args()
    version=release_version(args.version)
    standard = (ROOT / 'EDITION').is_file() and (ROOT / 'EDITION').read_text().strip() == 'standard'
    name = 'EchoCue-Standard' if standard else 'EchoCue'
    dependencies = args.dependencies.resolve()
    DEST=args.output.resolve()/(name+'-'+version+'-windows-x64')
    if DEST.exists():raise RuntimeError('Release directory already exists; inspect it before rebuilding.')
    internal=DEST/'_internal';internal.mkdir(parents=True)
    shutil.copy2(ROOT/'EchoCue.exe',DEST/'EchoCue.exe')
    shutil.copytree(ROOT/'app',internal/'app',ignore=ignore)
    shutil.copytree(dependencies/'vendor',internal/'vendor',ignore=ignore)
    if (ROOT / 'EDITION').is_file():
        shutil.copy2(ROOT / 'EDITION', internal / 'EDITION')
    (internal/'tools').mkdir()
    shutil.copy2(ROOT/'tools/login_antigravity.cmd',internal/'tools/login_antigravity.cmd')
    runtime=internal/'runtime';runtime.mkdir()
    shutil.copytree(dependencies/'runtime/asr',runtime/'asr',ignore=ignore)
    # The batch-transcription fallback still uses whisper.cpp independently of streaming ASR.
    legacy = dependencies / 'runtime/Release'
    if legacy.is_dir():
        (runtime / 'Release').mkdir()
        for item in legacy.iterdir():
            if item.is_file() and (item.suffix.lower() == '.dll' or item.name == 'whisper-cli.exe'):
                shutil.copy2(item, runtime / 'Release' / item.name)
    if (dependencies / 'runtime/ggml-base.bin').is_file():
        shutil.copy2(dependencies / 'runtime/ggml-base.bin', runtime / 'ggml-base.bin')
    python=Path(sys.base_prefix);embedded=runtime/'python';embedded.mkdir()
    for item in python.iterdir():
        if item.is_file() and (item.suffix.lower() in ('.dll','.exe') or item.name=='LICENSE.txt'):
            shutil.copy2(item,embedded/item.name)
    shutil.copytree(python/'DLLs',embedded/'DLLs',ignore=ignore)
    # Tcl 9 may embed its scripts in DLL zipfs; older Python uses a tcl directory.
    if (python/'tcl').is_dir():
        shutil.copytree(python/'tcl',embedded/'tcl',ignore=ignore)
    def library_ignore(folder,names):
        return ignore(folder,names)+[n for n in names if n in ('site-packages','ensurepip','idlelib')]
    shutil.copytree(python/'Lib',embedded/'Lib',ignore=library_ignore)
    (DEST/'START_HERE.txt').write_text('EchoCue Standard\nOpen EchoCue.exe from the complete folder. Configure a provider and audio, then select Prepare.\nSee README.md and docs/USER_GUIDE.md.\n', encoding='utf-8')
    if standard:
        (DEST / 'START_HERE.txt').write_text('EchoCue Standard\n\nOpen EchoCue.exe from this complete folder. Python and transcription models are included.\nConfigure a provider, audio devices and transcription model, then select Prepare.\nGlobal shortcuts are in Settings. Local authentication is required for CLI providers.\nPersonal settings and sessions are not included. See README.md and docs/USER_GUIDE.md.\n', encoding='utf-8')
    for name in ('README.md', 'README_ZH.md'):
        content = (ROOT/name).read_text(encoding='utf-8').replace('src="app/assets/', 'src="_internal/app/assets/')
        (DEST/name).write_text(content, encoding='utf-8')
    shutil.copy2(ROOT/'CHANGELOG.md',DEST/'CHANGELOG.md')
    shutil.copy2(ROOT/'VERSION',DEST/'VERSION')
    shutil.copy2(ROOT/'requirements.txt',DEST/'requirements.txt')
    shutil.copy2(ROOT/'tools/asr_models.json',DEST/'asr_models.json')
    shutil.copytree(ROOT/'docs',DEST/'docs',ignore=ignore)
    archive=Path(shutil.make_archive(str(DEST),'zip',root_dir=DEST.parent,base_dir=DEST.name))
    digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(str(archive),flush=True)

if __name__=='__main__':main()
