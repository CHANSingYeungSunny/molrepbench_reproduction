"""Probe three inference settings for the served model, one request each.

Observed problem: with max_tokens=2048 and no thinking switch, the API returned
HTTP 200 but empty message content ("No final content..."), which is the
signature of a reasoning model whose trace consumed the whole token budget.
This script sends the SAME first smoke question under three settings, each in
its own result directory, and prints what came back. No key is read here; run it
through tools/run_with_key.py.

Variants:
  A  extra_body {"thinking":{"type":"disabled"}}, max_tokens 2048
  B  no extra_body,                                   max_tokens 8192
  C  extra_body {"thinking":{"type":"disabled"}}, max_tokens 8192
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'settings.json').read_text(encoding='utf-8'))
DISABLED = {'thinking': {'type': 'disabled'}}

VARIANTS = [
    ('A_thinking_off_2048', {'extra_body': DISABLED, 'max_tokens': 2048}),
    ('B_default_8192', {'extra_body': {}, 'max_tokens': 8192}),
    ('C_thinking_off_8192', {'extra_body': DISABLED, 'max_tokens': 8192}),
]


def main():
    for name, patch in VARIANTS:
        cfg = dict(BASE)
        cfg.update(patch)
        cfg_path = ROOT / 'results' / f'probe_{name}' / 'settings_used.json'
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
        out_dir = ROOT / 'results' / f'probe_{name}' / 'run'
        print('=' * 70)
        print(f'VARIANT {name}: extra_body={cfg["extra_body"]} max_tokens={cfg["max_tokens"]}')
        subprocess.run([sys.executable, str(ROOT / 'reproduce.py'), 'run',
                        '--plan', 'plans/smoke', '--settings', str(cfg_path),
                        '--out', str(out_dir), '--max-requests', '1'],
                       cwd=str(ROOT))
        raw = out_dir / 'raw.jsonl'
        if not raw.exists():
            print('  no raw.jsonl produced')
            continue
        for line in raw.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            print('  status        :', r.get('status'))
            print('  error         :', r.get('error'))
            print('  served_model  :', r.get('served_model'))
            print('  finish_reason :', r.get('finish_reason'))
            print('  usage         :', r.get('usage'))
            text = r.get('raw_response') or ''
            print('  content(head) :', text[:400].replace('\n', ' | '))
            rc = r.get('reasoning_content')
            if rc:
                print('  reasoning len :', len(rc), '| head:', rc[:200].replace('\n', ' | '))


if __name__ == '__main__':
    main()