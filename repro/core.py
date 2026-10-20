"""Reuse the author's prompts, chemistry definitions and representation converters.

The frozen vendor tree is never edited. Only config paths are overridden in memory.
"""
from pathlib import Path
import csv
import hashlib
import importlib
import json
import logging
import os
import subprocess
import sys
import types
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor' / 'molrepbench'
DATA = ROOT / 'data'
REPRESENTATIONS = ['canonical_smiles', 'isomeric_smiles', 'randomized_smiles',
                   'deepsmiles', 'iupac', 'selfies', 'moljson', 'cml', 'inchi']
TASKS = [1, 2, 3, 4, 5, 6, 9, 10]

def digest(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def read_jsonl(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(s) for s in f if s.strip()]

def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')

def write_jsonl(path, values):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8', newline='\n') as f:
        for v in values:
            f.write(json.dumps(v, ensure_ascii=False, allow_nan=False) + '\n')

def setup():
    wanted = {'chebi20_test.csv', 'comprehension_subset_ids.csv', 'isomer_pairs.csv',
              'retrieval_distractors.csv', 'tautomer_pairs250.csv', 'protonation_pairs250.csv',
              'chebi_prepared_500.csv', 'fewshot_examples.csv', 'iupac_failures.csv'}
    DATA.mkdir(exist_ok=True)
    with zipfile.ZipFile(VENDOR / 'benchmark_data_small.zip') as z:
        for name in z.namelist():
            base = Path(name).name
            if base in wanted:
                dest = DATA / base
                if not dest.exists():
                    dest.write_bytes(z.read(name))
    missing = [x for x in wanted if not (DATA / x).exists()]
    if missing:
        raise RuntimeError(f'Missing released data files: {missing}')
    return sorted(wanted)

def vendor_modules():
    if 'config' not in sys.modules:
        path = VENDOR / 'scripts' / 'config.py'
        source = path.read_text(encoding='utf-8')
        source = source.replace('DATA_DIR = Path("/node2/arunraja/benchmark_data_small")',
                                f'DATA_DIR = Path({str(DATA)!r})')
        source = source.replace('RESULTS_DIR = PROJECT_ROOT / "results_small"',
                                f'RESULTS_DIR = Path({str(ROOT / "results" / "official")!r})')
        source = source.replace('FIGURES_DIR = PROJECT_ROOT / "figures"',
                                f'FIGURES_DIR = Path({str(ROOT / "results" / "official_figures")!r})')
        module = types.ModuleType('config')
        module.__file__ = str(path)
        sys.modules['config'] = module
        exec(compile(source, str(path), 'exec'), module.__dict__)
        sys.path.insert(0, str(VENDOR / 'scripts'))
    config = sys.modules['config']
    return (config, importlib.import_module('utils.prompts'),
            importlib.import_module('utils.representations'),
            importlib.import_module('utils.chemistry'))

def canonical(smiles, stereo=True):
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol, isomericSmiles=stereo) if mol else None

def obabel_exe():
    """Locate the OpenBabel CLI used by the Windows CML platform adapter.

    Why this exists (platform diagnosis, not a shortcut):
    - PyPI openbabel-wheel 3.1.1.23 (Windows) registers 137 formats but NOT cml
      (verified: 'cml' absent from pybel.informats/outformats), so the author's
      in-process pybel path mol.write("cml") / pybel.readstring("cml") fails.
    - conda-forge openbabel 3.2.1 (Windows) has no cml format at all;
      conda-forge openbabel 3.1.1 has cml in the obabel CLI (185 formats) but its
      Python binding silently fails to load formats_common/formats_xml plugins.
    - The author's own utils/representations.py cml_to_smiles already shells out
      to the `obabel` executable. This adapter therefore uses the same OpenBabel
      3.1.1 through its CLI for CML encode/decode. Real CML is produced and
      consumed; SMILES is never substituted for CML.
    """
    import shutil
    found = shutil.which('obabel')
    if found:
        return found
    env = os.environ.get('OBABEL_EXE')
    if env and Path(env).exists():
        return env
    for candidate in (Path(sys.prefix) / 'Library' / 'bin' / 'obabel.exe',
                      ROOT / '.venv' / 'Scripts' / 'obabel.exe',
                      ROOT / '.venv' / 'bin' / 'obabel'):
        if candidate.exists():
            return str(candidate)
    return None

def cml_from_smiles(smiles):
    """SMILES -> CML via the OpenBabel CLI (platform adapter)."""
    exe = obabel_exe()
    if not exe:
        return None
    r = subprocess.run([exe, '-ismi', '-ocml'], input=smiles,
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return None

def encode(smiles, representation, name=None, seed=42):
    """Regenerate non-IUPAC representations from the actual member's SMILES.

    Random SMILES are fresh per manifest seed but frozen for paired model comparisons.
    As in the author's main converter, canonical/random/DeepSMILES omit stereo.
    """
    from rdkit import Chem
    _, _, rep, _ = vendor_modules()
    if representation == 'iupac':
        return str(name).strip() if name and str(name).strip() else None
    if representation == 'randomized_smiles':
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToRandomSmilesVect(mol, 1, randomSeed=max(1, seed % (2**31-1)),
                                         isomericSmiles=False)[0]
    if representation == 'cml':
        # Author's in-process pybel path first (native Linux behaviour); the
        # OpenBabel CLI adapter only kicks in when the platform lacks the CML
        # format in-process (verified on Windows).
        value = rep.convert_to_representation(smiles, 'cml')
        if value:
            return value
        return cml_from_smiles(smiles)
    return rep.convert_to_representation(smiles, representation)

def decode(text, representation, allow_network=False):
    from rdkit import Chem
    _, _, rep, _ = vendor_modules()
    if representation == 'iupac':
        cache_path = ROOT / 'results' / 'opsin_cache.json'
        cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
        if text not in cache:
            if not allow_network:
                return None, 'decoder_not_run'
            import requests
            from urllib.parse import quote
            try:
                r = requests.get('https://opsin.ch.cam.ac.uk/opsin/' + quote(text, safe='') + '.smi', timeout=20)
                if r.status_code == 200:
                    cache[text] = {'status': 'ok', 'smiles': r.text.strip()}
                elif r.status_code in (400, 404):
                    cache[text] = {'status': 'invalid', 'smiles': None}
                else:
                    return None, 'decoder_error'
                write_json(cache_path, cache)
            except requests.RequestException:
                return None, 'decoder_error'
        item = cache[text]
        mol = Chem.MolFromSmiles(item['smiles']) if item['smiles'] else None
        return mol, ('ok' if mol else 'invalid')
    if representation == 'cml':
        # Author's own cml_to_smiles shells out to the obabel executable; the
        # OpenBabel CLI is the reliable CML reader on Windows (see obabel_exe).
        exe = obabel_exe()
        if exe:
            try:
                r = subprocess.run([exe, '-icml', '-osmi'], input=text,
                                   capture_output=True, text=True, timeout=20)
                value = r.stdout.strip().split()[0] if r.stdout.strip() else ''
                mol = Chem.MolFromSmiles(value) if r.returncode == 0 and value else None
                return mol, ('ok' if mol else 'invalid')
            except subprocess.TimeoutExpired:
                return None, 'decoder_error'
        # Fall back to the isolated Python OpenBabel subprocess (Linux path).
        code = ('import sys; from openbabel import pybel; '
                'm=pybel.readstring("cml",sys.stdin.read()); print(m.write("smi"))')
        try:
            r = subprocess.run([sys.executable, '-c', code], input=text, capture_output=True,
                               text=True, timeout=20)
            if 'No module named' in r.stderr:
                return None, 'decoder_not_run'
            value = r.stdout.strip().split()[0] if r.stdout.strip() else ''
            mol = Chem.MolFromSmiles(value) if r.returncode == 0 and value else None
            return mol, ('ok' if mol else 'invalid')
        except subprocess.TimeoutExpired:
            return None, 'decoder_error'
    mol = rep.parse_representation(text, representation)
    return mol, ('ok' if mol else 'invalid')

def generation_schema(representation):
    if representation == 'moljson':
        sys.path.insert(0, str(VENDOR / 'moljson'))
        return importlib.import_module('schema').GetSchema()
    return {'type': 'object', 'properties': {'molecule': {'type': 'string'}},
            'required': ['molecule'], 'additionalProperties': False}

def prepare(out, profile='smoke', n=None, seed=42, reps=None, iupac_policy='released'):
    """Build all prompts before inference, with IDs, truth, provenance and exclusions."""
    from rdkit import Chem, rdBase
    setup()
    config, prompts, _, chemistry = vendor_modules()
    reps = reps or REPRESENTATIONS
    verified_names = set()
    if iupac_policy == 'verified':
        audit_path = ROOT / 'evidence' / 'iupac_input_audit.json'
        if not audit_path.exists():
            raise ValueError('Run audit --iupac first. No network lookup is hidden inside prepare.')
        verified_names = {(x['smiles'], x['iupac']) for x in json.loads(audit_path.read_text(encoding='utf-8'))
                          if x.get('exact_stereo_match') is True}
    unknown = set(reps) - set(REPRESENTATIONS)
    if unknown:
        raise ValueError(f'Unknown representations: {unknown}')
    limit = n if n is not None else (2 if profile == 'smoke' else None)
    if limit is not None and limit < 1:
        raise ValueError('n must be positive')
    rows = read_csv(DATA / 'chebi20_test.csv')
    by_id = {r['molecule_id']: r for r in rows}
    ids = [r['molecule_id'] for r in read_csv(DATA / 'comprehension_subset_ids.csv')]
    all_ids = ids[:limit] if limit else ids
    manifest, excluded, cache = [], [], {}
    def enc(row, rep, key, suffix=''):
        smi = row.get('smiles' + suffix)
        name = row.get('iupac' + suffix)
        if rep == 'iupac' and iupac_policy == 'verified' and (smi, name) not in verified_names:
            return None
        token = (smi, rep, name, key)
        if token not in cache:
            rs = int(digest(f'{seed}:{key}')[:8], 16) % (2**31-1)
            cache[token] = encode(smi, rep, name, rs)
        return cache[token]
    def add(task, item, subtask, rep, prompt, truth, **extra):
        record = {'id': f'B{task}:{item}:{subtask}:{rep}', 'task': task,
                  'item_id': str(item), 'subtask': subtask, 'representation': rep,
                  'prompt': prompt, 'ground_truth': truth, **extra}
        record['input_status'] = ('iupac_verified_exact' if iupac_policy == 'verified' else 'iupac_released_unverified') if rep == 'iupac' and task != 6 else 'regenerated_from_smiles' if task != 6 else 'caption_only'
        record['prompt_sha256'] = digest(prompt)
        manifest.append(record)
    def missing(task, item, rep, reason):
        excluded.append({'task': task, 'item_id': str(item), 'representation': rep, 'reason': reason})
    for mid in all_ids:
        row = by_id[mid]
        mol = Chem.MolFromSmiles(row['smiles'])
        if mol is None:
            raise ValueError(f'Invalid reference SMILES: {mid}')
        counts = chemistry.get_atom_counts(mol)
        elements = [e for e in config.ELEMENTS if counts.get(e, 0)]
        import random
        element = random.Random(int(mid)).choice(elements)  # int IDs match author's hash(int) seed
        props = chemistry.calculate_all_properties(mol)
        for rep in reps:
            s = enc(row, rep, mid)
            if not s:
                for t in (1, 2, 3):
                    missing(t, mid, rep, 'input_conversion_failed')
                continue
            add(1, mid, element, rep, prompts.create_atom_counting_prompt(s, element, rep), counts[element])
            for group, definition in config.FUNCTIONAL_GROUPS.items():
                truth = chemistry.has_substructure(mol, definition['smarts'])
                add(2, mid, group, rep, prompts.create_functional_group_prompt(s, definition['name'], rep), truth)
            for prop in ['logp', 'tpsa', 'hbd', 'hba']:
                add(3, mid, prop, rep, prompts.create_property_estimation_prompt(s, prop, rep), props[prop])
    distractors = {}
    for row in read_csv(DATA / 'retrieval_distractors.csv'):
        distractors.setdefault(row['target_molecule_id'], []).append(row['distractor_molecule_id'])
    retrieval_ids = []
    for mid in ids:
        other = distractors.get(mid, [])
        if len(other) == 3 and all(x in by_id for x in other):
            retrieval_ids.append(mid)
    retrieval_ids = retrieval_ids[:limit] if limit else retrieval_ids
    for mid in retrieval_ids:
        import random
        choices = [mid] + distractors[mid]
        random.Random(int(digest(f'{seed}:retrieval:{mid}')[:8], 16)).shuffle(choices)
        truth = 'ABCD'[choices.index(mid)]
        for rep in reps:
            strings = [enc(by_id[x], rep, x) for x in choices]
            if not all(strings):
                missing(4, mid, rep, 'candidate_conversion_failed')
                continue
            add(4, mid, 'choice', rep, prompts.create_retrieval_prompt(
                by_id[mid]['description'], dict(zip('ABCD', strings)), rep), truth,
                choice_ids=choices)
    for task, filename, prompt_function in [
        (5, 'isomer_pairs.csv', prompts.create_isomer_discrimination_prompt),
        (9, 'tautomer_pairs250.csv', prompts.create_tautomer_recognition_prompt),
        (10, 'protonation_pairs250.csv', prompts.create_protonation_recognition_prompt)]:
        pairs = read_csv(DATA / filename)
        pairs = pairs[:limit] if limit else pairs
        for idx, row in enumerate(pairs):
            item = row.get('pair_id', str(idx))
            truth = row['ground_truth'].strip().lower() in ('yes', 'true', '1')
            for rep in reps:
                strings = [enc(row, rep, f'B{task}:{item}:{side}', '_' + side) for side in ('1', '2')]
                if not all(strings):
                    missing(task, item, rep, 'pair_conversion_failed')
                    continue
                add(task, item, 'binary', rep, prompt_function(*strings, rep), truth,
                    pair_type=row['pair_type'], input_strings_equal=strings[0] == strings[1],
                    reference_smiles_1=row['smiles_1'], reference_smiles_2=row['smiles_2'])
    gen_n = limit if limit else 200  # supplied paper Appendix C; released config says 250
    for row in rows[:gen_n]:
        mid = row['molecule_id']
        for rep in reps:
            add(6, mid, 'generation', rep,
                prompts.create_generation_prompt(row['description'], rep, use_json_format=True),
                row['smiles'], json_schema=generation_schema(rep), description=row['description'])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / 'manifest.jsonl', manifest)
    write_jsonl(out / 'excluded.jsonl', excluded)
    from collections import Counter
    plan = {'protocol': 'released-data-audited-v1', 'profile': profile, 'seed': seed,
            'n_override': n, 'rdkit_version': rdBase.rdkitVersion,
            'representations': reps, 'request_count': len(manifest),
            'task_counts': dict(Counter(str(x['task']) for x in manifest)),
            'manifest_sha256': digest((out / 'manifest.jsonl').read_text(encoding='utf-8')),
            'excluded_count': len(excluded), 'retrieval_eligible_total': len([
                mid for mid in ids if len(distractors.get(mid, [])) == 3]),
            'data_files_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in sorted(DATA.glob('*.csv'))},
            'iupac_policy': iupac_policy,
            'iupac_status': ('Only OPSIN exact-stereo-verified input names retained' if iupac_policy == 'verified'
                             else 'released names reused; member-specific validity NOT verified offline'),
            'deviations': ['B5 uses CSV same-molecule labels; released code disagrees on 375/500',
                           'B6 cap 200 per supplied paper, not released config cap 250',
                           'B4 identical option order across representations',
                           'Random SMILES frozen per explicit manifest seed',
                           'All non-IUPAC pair inputs regenerated from member-specific SMILES',
                           'No blank-line stop sequence; prevent premature answer truncation',
                           'B9/B10 released CSV source says ChEBI-20, paper says ZINC250K']}
    write_json(out / 'plan.json', plan)
    return plan
