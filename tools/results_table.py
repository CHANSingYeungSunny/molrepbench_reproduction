import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
run = ROOT / 'results' / 'deepseek-flash_off_smoke_run3'
summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
rows = list(csv.DictReader((run / 'summary.csv').open(encoding='utf-8-sig', newline='')))

print('=== task x representation (smoke, 270 requests, deepseek-flash thinking off) ===')
hdr = ['task', 'representation', 'n', 'accuracy_all', 'macro_f1', 'logp_spearman', 'tpsa_spearman',
       'validity_rate', 'exact_match', 'n_decoder_evaluated']
print(f"{'task':<5}{'representation':<20}{'n':>4}{'acc':>8}{'macroF1':>9}{'logp_rho':>10}{'tpsa_rho':>10}{'valid':>8}{'exact':>8}")
for r in rows:
    def g(k):
        v = r.get(k, '')
        return v if v not in ('', 'None', None) else '-'
    print(f"B{r['task']:<4}{r['representation']:<20}{r.get('n',''):>4}{g('accuracy_all'):>8}{g('macro_f1'):>9}"
          f"{g('logp_spearman'):>10}{g('tpsa_spearman'):>10}{g('validity_rate'):>8}{g('exact_match'):>8}")

status = json.loads((run / 'evaluation_status.json').read_text(encoding='utf-8'))
print('\nstatus:', json.dumps({k: v for k, v in status.items() if k != 'note'}, ensure_ascii=False, indent=2))

scored = [json.loads(l) for l in (run / 'scored.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
unparsed = [s for s in scored if s['predicted'] is None]
print('\nunparsed answers:', len(unparsed))
for s in unparsed:
    print('  ', s['id'], '| api_status', s['api_status'], '| finish', s.get('finish_reason'))
trunc = [s for s in scored if s.get('finish_reason') == 'length']
print('truncated (finish_reason=length):', [s['id'] for s in trunc])

# per-task overall
per_task = defaultdict(list)
for s in scored:
    per_task[s['task']].append(s['correct'])
print('\nper-task overall correct rate (all representations pooled):')
for t in sorted(per_task):
    vals = [v for v in per_task[t] if v is not None]
    n_all = len(per_task[t])
    print(f"  B{t}: {sum(vals)}/{len(vals)} = {sum(vals)/len(vals):.2f}"
          + ('' if len(vals) == n_all else f'   (scored {len(vals)}/{n_all})'))