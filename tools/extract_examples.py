"""Extract per-task worked examples and real failure cases from the run.

Reads plans/smoke/manifest.jsonl (prompt + ground truth) and
results/deepseek-flash_off_smoke_run3/{raw,scored}.jsonl, and writes
evidence/report_examples.json for the report builder. No invented content.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUN = ROOT / 'results' / 'deepseek-flash_off_smoke_run3'


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding='utf-8').splitlines() if l.strip()]


manifest = {r['id']: r for r in read_jsonl(ROOT / 'plans' / 'smoke' / 'manifest.jsonl')}
raw = {}
for r in read_jsonl(RUN / 'raw.jsonl'):
    raw[r['id']] = r          # last record wins
scored = read_jsonl(RUN / 'scored.jsonl')

examples = {}
# one worked example per task: prefer canonical_smiles, else first available
for task in (1, 2, 3, 4, 5, 6, 9, 10):
    cands = [s for s in scored if s['task'] == task and s.get('api_status') == 'ok']
    pick = next((s for s in cands if s['representation'] == 'canonical_smiles'), None) or cands[0]
    m = manifest[pick['id']]
    r = raw[pick['id']]
    examples[f'B{task}'] = {
        'id': pick['id'], 'subtask': m.get('subtask'), 'representation': pick['representation'],
        'prompt': m['prompt'], 'ground_truth': pick['ground_truth'],
        'raw_answer_head': (r.get('raw_response') or '')[:1200],
        'raw_answer_chars': len(r.get('raw_response') or ''),
        'parsed': pick['predicted'], 'correct': pick['correct'],
        'usage': r.get('usage'), 'finish_reason': r.get('finish_reason'),
        'decode_status': pick.get('decode_status'),
        'metric': ('exact match' if task in (1, 2, 4, 5, 9, 10) else
                   ('Spearman' if task == 3 else 'validity + exact match')),
    }

# failure cases, real ones only
failures = []

# 1) truncation
for s in scored:
    if s.get('finish_reason') == 'length':
        r = raw[s['id']]
        failures.append({
            'kind': '输出被截断', 'id': s['id'], 'task': s['task'], 'subtask': s.get('subtask'),
            'representation': s['representation'],
            'why': f"finish_reason=length，消耗 {r['usage']['total_tokens']} tokens（上限 8192）",
            'prompt_head': manifest[s['id']]['prompt'][:200],
            'answer_tail': (r.get('raw_response') or '')[-300:],
            'parsed': s['predicted'], 'correct': s['correct'],
            'counted_as': '未解析答案，记为未评估，不删除',
        })

# 2) wrong answers (model answered but wrong), one per task where possible
for task in (1, 2, 5, 9, 10, 3):
    wrong = [s for s in scored if s['task'] == task
             and s.get('correct') is not None and not s['correct']]
    if wrong:
        s = wrong[0]
        r = raw[s['id']]
        failures.append({
            'kind': '答案错误', 'id': s['id'], 'task': task, 'subtask': s.get('subtask'),
            'representation': s['representation'],
            'why': '模型给出了可解析的答案，但与标准答案不一致',
            'prompt_head': manifest[s['id']]['prompt'][:200],
            'answer_tail': (r.get('raw_response') or '')[-300:],
            'ground_truth': s['ground_truth'], 'parsed': s['predicted'], 'correct': False,
            'counted_as': '记为错误（计入分母）',
        })

# 3) invalid generation (B6 decode failures)
for s in scored:
    if s['task'] == 6 and s.get('decode_status') not in (None, 'ok'):
        r = raw[s['id']]
        failures.append({
            'kind': '生成结果无法解码', 'id': s['id'], 'task': 6, 'subtask': s.get('subtask'),
            'representation': s['representation'],
            'why': f"decode_status={s.get('decode_status')}",
            'prompt_head': manifest[s['id']]['prompt'][:200],
            'answer_tail': (r.get('raw_response') or '')[-300:],
            'ground_truth': s['ground_truth'], 'parsed': s['predicted'], 'correct': s['correct'],
            'counted_as': 'validity=0，计入分母',
        })
        break

# coverage
coverage = {}
for s in scored:
    coverage.setdefault((s['task'], s['representation']), {'n': 0, 'scored': 0, 'correct': 0})
    c = coverage[(s['task'], s['representation'])]
    c['n'] += 1
    if s.get('correct') is not None:
        c['scored'] += 1
        c['correct'] += int(bool(s['correct']))

out = {'examples': examples,
       'failures': failures,
       'coverage': {f'B{t}:{rep}': v for (t, rep), v in sorted(coverage.items())}}
p = ROOT / 'evidence' / 'report_examples.json'
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print('examples:', list(examples))
print('failure cases:', len(failures))
for f in failures:
    print(f"  - {f['kind']:<16} {f['id']}  ({f['why'][:60]})")
print('saved:', p)