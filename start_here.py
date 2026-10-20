#!/usr/bin/env python3
"""One-command environment setup and offline validation. Never calls an LLM."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import venv

def main():
    p=argparse.ArgumentParser(description='Install this project and prepare all nine representations. No LLM calls.')
    p.add_argument('--skip-install',action='store_true')
    args=p.parse_args()
    if sys.version_info[:2] not in ((3,11),(3,12)):
        raise SystemExit('Use 64-bit Python 3.12 or 3.11. Windows: py -3.12 start_here.py')
    root=Path(__file__).resolve().parent
    os.chdir(root)
    executable=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not executable.exists():
        print('Creating isolated .venv...',flush=True)
        venv.EnvBuilder(with_pip=True).create(root/'.venv')
    def call(*parts):
        subprocess.run([str(executable),*parts],check=True)
    if not args.skip_install:
        call('-m','pip','install','-r','requirements.txt')
    for command in ('doctor','verify-vendor','setup'):
        call('reproduce.py',command)
    call('-m','unittest','discover','-s','tests','-v')
    call('reproduce.py','prepare','--profile','smoke','--out','plans/smoke')
    print('\nOffline setup complete: 270 prompts; no model results yet.\n'
          'Next: open CODEBUDDY_PROMPT.txt and configure your existing model service.')

if __name__=='__main__':main()
