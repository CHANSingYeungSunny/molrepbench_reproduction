"""Run a reproduce.py command with the API key from .env or hidden input.

Key resolution order:
1. LLM_API_KEY already in the environment
2. .env file in the project root (gitignored; never printed, never logged)
3. hidden getpass prompt in your terminal

The key is only ever placed in the child process environment. It is never
written to settings.json, results files, logs, reports or Git.

Usage:
  .venv\\Scripts\\python.exe tools\\run_with_key.py reproduce.py run --plan plans/smoke \
      --settings settings.json --out results\\deepseek-flash_off_smoke_run2
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

ENV_NAME = 'LLM_API_KEY'
PLACEHOLDER = 'PASTE_'
ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'


def load_env_file():
    """Read KEY=VALUE pairs from .env without overriding existing variables."""
    if not ENV_FILE.exists():
        return None
    value = None
    for line in ENV_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        if key.strip() == ENV_NAME:
            value = val.strip().strip('"').strip("'")
    if value and not value.startswith(PLACEHOLDER):
        return value
    return None


def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/run_with_key.py <command> [args...]')
        return 2
    if os.environ.get(ENV_NAME):
        print(f'{ENV_NAME} found in environment.')
    else:
        from_file = load_env_file()
        if from_file:
            os.environ[ENV_NAME] = from_file
            print(f'{ENV_NAME} loaded from .env (value not shown).')
        else:
            if ENV_FILE.exists():
                print(f'.env exists but still holds the placeholder; falling back to hidden input.')
            key = getpass.getpass(f'{ENV_NAME} (hidden input, kept in memory only): ')
            if not key.strip():
                print('Empty key. Aborting; nothing was written.')
                return 2
            os.environ[ENV_NAME] = key.strip()
    print(f'Running: {sys.executable} ' + ' '.join(sys.argv[1:]))
    return subprocess.run([sys.executable] + sys.argv[1:]).returncode


if __name__ == '__main__':
    raise SystemExit(main())