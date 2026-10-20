import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
run_dir = ROOT / 'results' / 'deepseek-flash_off_smoke_run3'
raw = run_dir / 'raw.jsonl'
if not raw.exists():
    print('no raw.jsonl yet')
else:
    latest = {}
    for line in raw.read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r['id'] not in latest or r.get('status') == 'ok':
                latest[r['id']] = r
    records = list(latest.values())
    ok = [r for r in records if r.get('status') == 'ok']
    err = [r for r in records if r.get('status') != 'ok']
    print(f'ids touched: {len(records)}/270 | ok: {len(ok)} | error: {len(err)}')
    if ok:
        tokens = [r['usage']['total_tokens'] for r in ok if r.get('usage')]
        if tokens:
            tokens_sorted = sorted(tokens)
            print(f'usage total_tokens: mean={sum(tokens)/len(tokens):.0f} '
                  f'p50={tokens_sorted[len(tokens)//2]} max={max(tokens)}')
        fr = Counter(r.get('finish_reason') for r in ok)
        print('finish_reason:', dict(fr))
        rc = sum(1 for r in ok if r.get('reasoning_content'))
        print('responses carrying reasoning_content (should be 0):', rc)
    if err:
        print('errors:', dict(Counter(r.get('error') for r in err)))
    print('last 3 ids:', [r['id'] for r in records[-3:]])