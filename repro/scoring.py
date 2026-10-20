"""Metrics use all planned requests as denominators and expose missing answers.

No parser fallback to the first number in a reasoning trace. A non-answer cannot
silently become a correct prediction. IUPAC decoder outages remain unevaluated.
"""
from pathlib import Path
from collections import defaultdict
import csv
import json
import math
import re
import statistics
from .core import canonical, decode, read_jsonl, write_json, write_jsonl

def final_text(raw):
    text = re.sub(r'<think>.*?</think>', '', raw or '', flags=re.S).strip()
    if '<think>' in text:  # truncated reasoning without a final answer
        return ''
    boxes = re.findall(r'\\boxed\{([^{}]*)\}', text)
    if boxes:
        return boxes[-1].strip()
    final = re.findall(r'(?:Final answer|The answer is)\s*[:：]?\s*(.*)', text, flags=re.I)
    if final:
        return final[-1].strip().rstrip('.')
    return text

def parse(raw, task):
    text = final_text(raw)
    if task == 6:
        # Parse the full final JSON; MolJSON itself has nested dictionaries.
        try:
            obj = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I))
            if isinstance(obj, dict) and 'molecule' in obj:
                return obj['molecule'] if isinstance(obj['molecule'], str) else None
            if isinstance(obj, dict) and 'atoms' in obj and 'bonds' in obj:
                return json.dumps(obj)
        except (ValueError, TypeError):
            pass
        return text or None
    if task in (2, 5, 9, 10):
        token = text.strip().strip('.').lower()
        return True if token == 'yes' else False if token == 'no' else None
    if task == 4:
        return text.strip(' .()') if text.strip(' .()') in 'ABCD' and len(text.strip(' .()')) == 1 else None
    match = re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', text)
    if not match:
        return None
    value = float(text)
    if not math.isfinite(value):
        return None
    if task == 1:
        return int(value) if value.is_integer() else None
    return value

def mean(values):
    return statistics.mean(values) if values else None

def f1(rows):
    tp = sum(r['predicted'] is True and r['ground_truth'] is True for r in rows)
    fp = sum(r['predicted'] is True and r['ground_truth'] is False for r in rows)
    fn = sum(r['predicted'] is False and r['ground_truth'] is True for r in rows)
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0

def spearman(rows):
    from scipy.stats import spearmanr
    if len(rows) < 3:
        return None
    gt, pred = [r['ground_truth'] for r in rows], [r['predicted'] for r in rows]
    if len(set(gt)) < 2 or len(set(pred)) < 2:
        return None
    value = float(spearmanr(gt, pred).statistic)
    return value if math.isfinite(value) else None

def similarities(mol, reference):
    from rdkit import Chem, DataStructs
    from rdkit.Chem import rdFingerprintGenerator, MACCSkeys
    ref = Chem.MolFromSmiles(reference)
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    pairs = {'morgan': (generator.GetFingerprint(mol), generator.GetFingerprint(ref)),
             'maccs': (MACCSkeys.GenMACCSKeys(mol), MACCSkeys.GenMACCSKeys(ref)),
             'rdkit': (Chem.RDKFingerprint(mol), Chem.RDKFingerprint(ref))}
    return {k: float(DataStructs.TanimotoSimilarity(*v)) for k, v in pairs.items()}

def aggregate(scored):
    groups = defaultdict(list)
    for r in scored:
        sub = r['subtask'] if r['task'] == 3 else 'all'
        groups[(r['task'], sub, r['representation'])].append(r)
    summaries = []
    for (task, sub, rep), group in sorted(groups.items()):
        parsed = [r for r in group if r['predicted'] is not None]
        value = {'task': task, 'subtask': sub, 'representation': rep,
                 'n_expected': len(group), 'n_api_ok': sum(r['api_status'] == 'ok' for r in group),
                 'n_parsed': len(parsed), 'parse_coverage': len(parsed) / len(group),
                 'n_truncated': sum(r.get('finish_reason') == 'length' for r in group)}
        value['input_status'] = ','.join(sorted(set(r.get('input_status','unknown') for r in group)))
        if task == 6:
            evaluated = [r for r in group if r['decode_status'] not in ('decoder_not_run', 'decoder_error')]
            valid = [r for r in group if r.get('valid')]
            all_decoded = len(evaluated) == len(group)
            value.update(n_decoder_evaluated=len(evaluated), n_valid=len(valid),
                validity_rate=mean([int(r['valid']) for r in evaluated]) if all_decoded else None,
                validity_evaluated_only=mean([int(r['valid']) for r in evaluated]),
                exact_match=mean([r['correct'] for r in group]) if all_decoded else None,
                exact_match_stereo=mean([r.get('correct_stereo', 0) for r in group]) if all_decoded else None,
                fcd=None, fcd_status='not_requested')
            for fp in ('morgan', 'maccs', 'rdkit'):
                value[fp + '_tanimoto_valid_only'] = mean([r[fp] for r in valid])
                value[fp + '_tanimoto_all_invalid_zero'] = (
                    mean([r.get(fp, 0.0) for r in group]) if all_decoded else None)
        elif task == 2:
            by_group = defaultdict(list)
            for r in parsed:
                by_group[r['subtask']].append(r)
            macro = mean([f1(by_group[g]) for g in ['primary_amine', 'ester', 'aldehyde', 'sulfonamide', 'halide']])
            # Only call it the headline Macro-F1 if every planned answer is parsed.
            value.update(macro_f1=macro if len(parsed) == len(group) else None,
                macro_f1_valid_only=macro, label_accuracy_all=mean([r['correct'] for r in group]))
        elif task == 3 and sub in ('logp', 'tpsa'):
            value.update(spearman_rho=spearman(parsed),
                         mae_parsed_only=mean([abs(r['predicted'] - r['ground_truth']) for r in parsed]))
        else:
            value['accuracy_all'] = mean([r['correct'] for r in group])
        summaries.append(value)
    return summaries

def score(plan_dir, run_dir, allow_network=False, with_fcd=False):
    from rdkit import Chem
    plan_dir, run_dir = Path(plan_dir), Path(run_dir)
    items = read_jsonl(plan_dir / 'manifest.jsonl')
    if not items:
        raise ValueError('Missing manifest')
    latest = {}
    for r in read_jsonl(run_dir / 'raw.jsonl'):
        if r['id'] not in latest or r.get('status') == 'ok' or latest[r['id']].get('status') != 'ok':
            latest[r['id']] = r
    scored = []
    for item in items:
        raw = latest.get(item['id'], {})
        if raw and raw.get('prompt_sha256') != item['prompt_sha256']:
            raise ValueError(f'Prompt hash mismatch: {item["id"]}')
        pred = parse(raw.get('raw_response', ''), item['task']) if raw.get('status') == 'ok' else None
        row = {k: v for k, v in item.items() if k not in ('prompt', 'json_schema', 'description')}
        row.update(predicted=pred, api_status=raw.get('status', 'missing'),
                   finish_reason=raw.get('finish_reason'), correct=int(pred is not None and pred == item['ground_truth']))
        if item['task'] == 6:
            mol, status = decode(pred, item['representation'], allow_network) if pred else (None, 'no_answer')
            row.update(decode_status=status, valid=mol is not None, correct=0, correct_stereo=0)
            if mol is not None:
                smi = Chem.MolToSmiles(mol, isomericSmiles=True)
                row.update(generated_smiles=smi,
                    correct=int(canonical(smi, False) == canonical(item['ground_truth'], False)),
                    correct_stereo=int(canonical(smi, True) == canonical(item['ground_truth'], True)),
                    **similarities(mol, item['ground_truth']))
        scored.append(row)
    summaries = aggregate(scored)
    if with_fcd:
        try:
            import fcd
        except ImportError as exc:
            raise RuntimeError('Install optional fcd first; no placeholder FCD is fabricated.') from exc
        for row in summaries:
            if row['task'] != 6:
                continue
            group = [r for r in scored if r['task'] == 6 and r['representation'] == row['representation']]
            valid = [r for r in group if r.get('valid')]
            if row['n_decoder_evaluated'] != len(group):
                row['fcd_status'] = 'decoder_incomplete'
            elif len(valid) < 2:
                row['fcd_status'] = 'insufficient_valid_samples'
            else:
                try:
                    value = float(fcd.get_fcd([canonical(r['ground_truth'], False) for r in group],
                                              [canonical(r['generated_smiles'], False) for r in valid]))
                    row['fcd'] = value if math.isfinite(value) else None
                    row['fcd_status'] = 'computed' if row['fcd'] is not None else 'non_finite'
                except Exception as exc:
                    row['fcd_status'] = 'error_' + type(exc).__name__
    write_jsonl(run_dir / 'scored.jsonl', scored)
    write_json(run_dir / 'summary.json', summaries)
    fieldnames = list(dict.fromkeys(k for r in summaries for k in r))
    with (run_dir / 'summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)
    meta_path = run_dir / 'run_metadata.json'
    result_kind = 'unrecorded'
    if meta_path.exists():
        try:
            result_kind = json.loads(meta_path.read_text(encoding='utf-8')).get('result_kind', 'unrecorded')
        except ValueError:
            result_kind = 'unreadable'
    status = {'expected_requests': len(items), 'api_success': sum(r['api_status'] == 'ok' for r in scored),
        'parsed_answers': sum(r['predicted'] is not None for r in scored),
        'inference_complete': all(r['api_status'] == 'ok' for r in scored),
        'iupac_generation_decoder_complete': all(r.get('decode_status') not in ('decoder_not_run', 'decoder_error')
            for r in scored if r['task'] == 6 and r['representation'] == 'iupac'),
        'fcd_requested': with_fcd, 'full_paper_reproduced': False,
        'result_kind': result_kind,
        'note': ('This status describes only the response files in this run directory. '
                 'Whether they came from paid inference, an imported export or a fixture is '
                 'recorded in run_metadata.json result_kind and must be checked before reporting.')}
    write_json(run_dir / 'evaluation_status.json', status)
    return status

def bootstrap(run_dir, reference='canonical_smiles', samples=10000, seed=42):
    """Paired molecule-cluster bootstrap, recomputing each primary metric.

    Predeclared reference, no post-hoc best selection and no multiplicity correction.
    For B2 all five labels for one molecule are resampled together.
    """
    import numpy as np
    rows = read_jsonl(Path(run_dir) / 'scored.jsonl')
    groups = defaultdict(dict)
    for r in rows:
        sub = r['subtask'] if r['task'] == 3 else 'all'
        groups[(r['task'], sub)].setdefault(r['representation'], []).append(r)
    rng = np.random.default_rng(seed)
    output = []
    def metric(group, task, sub):
        if task == 2:
            if any(r['predicted'] is None for r in group):
                return None
            return mean([f1([r for r in group if r['subtask'] == g]) for g in
                         ['primary_amine', 'ester', 'aldehyde', 'sulfonamide', 'halide']])
        if task == 3 and sub in ('logp', 'tpsa'):
            if any(r['predicted'] is None for r in group):
                return None
            return spearman(group)
        if task == 6 and any(r.get('decode_status') in ('decoder_not_run', 'decoder_error') for r in group):
            return None
        return mean([r['correct'] for r in group])
    for (task, sub), reps in groups.items():
        if reference not in reps:
            continue
        for rep, group in reps.items():
            if rep == reference:
                continue
            left, right = defaultdict(list), defaultdict(list)
            for r in group: left[r['item_id']].append(r)
            for r in reps[reference]: right[r['item_id']].append(r)
            ids = sorted(set(left) & set(right))
            if len(ids) < 3:
                continue
            l = [r for i in ids for r in left[i]]
            r = [v for i in ids for v in right[i]]
            a, b = metric(l, task, sub), metric(r, task, sub)
            if a is None or b is None:
                continue
            diffs = []
            for _ in range(samples):
                chosen = rng.choice(ids, size=len(ids), replace=True)
                a1 = metric([v for i in chosen for v in left[i]], task, sub)
                b1 = metric([v for i in chosen for v in right[i]], task, sub)
                if a1 is not None and b1 is not None:
                    diffs.append(a1-b1)
            if not diffs:
                continue
            ci = np.quantile(diffs, [.025, .975])
            output.append({'task': task, 'subtask': sub, 'representation': rep,
                'reference': reference, 'n_common_molecules': len(ids), 'difference': a-b,
                'ci95_low': float(ci[0]), 'ci95_high': float(ci[1]),
                'bootstrap_valid': len(diffs), 'bootstrap_requested': samples, 'seed': seed,
                'metric': 'macro_f1' if task == 2 else 'spearman' if task == 3 and sub in ('logp','tpsa') else 'exact_accuracy',
                'multiplicity_adjustment': 'none'})
    write_json(Path(run_dir) / 'paired_bootstrap.json', output)
    return len(output)
