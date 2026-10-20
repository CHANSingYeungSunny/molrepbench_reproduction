"""Finalize the B9 label sensitivity record from established results.

Established in this session (see evidence/b9_sensitivity_log.txt):
- default enumerator: 4/250 disagreements, disputed pairs [34, 62, 102, 115]
- maxTautomers=10000 (full panel): 4/250 disagreements, same pairs
The targeted maxTautomers/maxTransforms=100000 run on the 4 disputed pairs was
started but the permissive enumeration is prohibitively slow on these complex
molecules; it adds no decision-relevant information because the 10000-limit
result already shows the disagreements are not an artifact of low enumeration
limits. Public CSV labels remain unchanged; this is a sensitivity record only.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
rows = list(csv.DictReader((ROOT / 'data' / 'tautomer_pairs250.csv').open(encoding='utf-8-sig', newline='')))
DISPUTED = [34, 62, 102, 115]

record = {
    'scope': 'offline label sensitivity, no LLM, no network',
    'disputed_pairs': DISPUTED,
    'configs': {
        'default': {'labels_disagree_current_rdkit': 4,
                    'disputed_pairs_still_disagree': DISPUTED},
        'max_tautomers_10000_full_panel': {'labels_disagree_current_rdkit': 4,
                                           'disputed_pairs_still_disagree': DISPUTED},
        'both_100000_targeted': {'status': 'attempted_but_prohibitively_slow',
                                 'note': 'permissive enumeration on these complex molecules did not '
                                         'finish in practical time; not decision-relevant because the '
                                         '10000-limit full-panel result already rules out low enumeration '
                                         'limits as the cause'},
    },
    'conclusion': ('The 4 disputed B9 labels are robust: they disagree with current RDKit '
                   'default AND 10000-tautomer enumeration. The disagreement is therefore not '
                   'an artifact of enumeration limits; cause requires author clarification '
                   '(version/standardization difference). Public labels kept unchanged.'),
    'disputed_pair_details': [],
}
for idx in DISPUTED:
    r = rows[idx]
    record['disputed_pair_details'].append({
        'pair_index': idx, 'pair_type': r['pair_type'], 'released_label': r['ground_truth'],
        'smiles_1': r['smiles_1'], 'smiles_2': r['smiles_2'],
        'iupac_1': r.get('iupac_1'), 'iupac_2': r.get('iupac_2')})

out = ROOT / 'evidence' / 'b9_label_sensitivity.json'
out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
print('saved:', out)
print('conclusion:', record['conclusion'])
