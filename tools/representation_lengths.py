"""Character-length statistics of the 9 representations in the paper plan (v2).

v1 bug: CML/MolJSON strings are multi-line, so a per-line regex captured only
the XML declaration. Molecule strings run from their label to the next blank
line in these prompts.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.core import encode  # noqa: E402

REPS = ['canonical_smiles', 'isomeric_smiles', 'randomized_smiles', 'deepsmiles',
        'iupac', 'selfies', 'moljson', 'cml', 'inchi']

manifest = [json.loads(l) for l in (ROOT / 'plans' / 'paper' / 'manifest.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
lengths = defaultdict(list)


def between(text, start, end):
    i = text.find(start)
    if i < 0:
        return None
    i += len(start)
    j = text.find(end, i)
    return text[i:] if j < 0 else text[i:j]


for item in manifest:
    task, rep, prompt = item['task'], item['representation'], item['prompt']
    strings = []
    if task in (1, 2, 3):
        s = between(prompt, 'Molecule: ', '\n\n')
        if s:
            strings = [s]
    elif task in (5, 9, 10):
        s1 = between(prompt, 'Molecule 1: ', '\nMolecule 2: ')
        s2 = between(prompt, 'Molecule 2: ', '\n\n')
        if s1 and s2:
            strings = [s1, s2]
    elif task == 4:
        block = between(prompt, '\n\n', '\n\nPlease reason')
        if block:
            for letter in 'ABCD':
                nxt = 'ABCD'['ABCD'.index(letter) + 1] if letter != 'D' else None
                s = between(block, f'{letter}: ', f'\n{nxt}: ' if nxt else '')
                if s:
                    strings.append(s)
    for s in strings:
        lengths[(task, rep)].append(len(s))

# B6: reference molecule encoded in each target representation
seen = set()
for item in [i for i in manifest if i['task'] == 6]:
    key = (item['item_id'], item['representation'])
    if key in seen:
        continue
    seen.add(key)
    value = encode(item['ground_truth'], item['representation'])
    if value:
        lengths[(6, item['representation'])].append(len(value))

stats = {}
for (task, rep), values in sorted(lengths.items()):
    stats[f'B{task}:{rep}'] = {
        'n': len(values), 'mean': round(statistics.mean(values), 1),
        'p50': round(statistics.median(values), 1),
        'p95': round(sorted(values)[max(0, int(0.95 * len(values)) - 1)], 1),
        'max': max(values)}

print(f"{'task:rep':<38}{'n':>5}{'mean':>9}{'p50':>8}{'p95':>8}{'max':>8}")
for key, v in stats.items():
    print(f"{key:<38}{v['n']:>5}{v['mean']:>9}{v['p50']:>8}{v['p95']:>8}{v['max']:>8}")

print('\nper-representation mean chars (comprehension tasks, pooled):')
pooled = {}
for rep in REPS:
    vals = []
    for key, v in stats.items():
        task = int(key.split(':')[0][1:])
        r = key.split(':', 1)[1]
        if r == rep and task != 6:
            vals.extend([v['mean']] * v['n'])
    if vals:
        pooled[rep] = round(statistics.mean(vals), 1)
        print(f'  {rep:<20} mean={pooled[rep]:8.1f}')

out = ROOT / 'evidence' / 'representation_length_stats.json'
out.write_text(json.dumps({'stats': stats, 'pooled_comprehension_mean_chars': pooled,
                           'note': 'characters, not tokens; token counts need the served tokenizer'},
                          indent=2), encoding='utf-8')
print('saved:', out)
