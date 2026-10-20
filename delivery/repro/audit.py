"""Read-only checks on the released dataset; no LLM calls."""
from collections import Counter
from pathlib import Path
import json
from .core import DATA, REPRESENTATIONS, ROOT, canonical, decode, read_csv, setup, write_json

def audit(output, iupac=False):
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    import selfies
    setup()
    findings = {'scope': 'released data, not model performance', 'iupac_network_requested': iupac}
    disagreements = []
    for task, file in [(5, 'isomer_pairs.csv'), (9, 'tautomer_pairs250.csv'), (10, 'protonation_pairs250.csv')]:
        rows = read_csv(DATA / file)
        bad_label, old_bad, bad_selfies, name_collapses = [], [], [], []
        tau = rdMolStandardize.TautomerEnumerator()
        uncharger = rdMolStandardize.Uncharger()
        for idx, r in enumerate(rows):
            a, b = (Chem.MolFromSmiles(r[k]) for k in ('smiles_1', 'smiles_2'))
            if a is None or b is None:
                bad_label.append(idx)
                continue
            truth = r['ground_truth'].lower() in ('yes', 'true', '1')
            if task == 5:
                expected = canonical(r['smiles_1']) == canonical(r['smiles_2'])
                if (r['pair_type'] in ('natural', 'stereoisomer')) != truth:
                    old_bad.append(idx)
            elif task == 9:
                expected = Chem.MolToSmiles(tau.Canonicalize(a)) == Chem.MolToSmiles(tau.Canonicalize(b))
            else:
                expected = Chem.MolToSmiles(uncharger.uncharge(a)) == Chem.MolToSmiles(uncharger.uncharge(b))
            if expected != truth:
                bad_label.append(idx)
                disagreements.append({'task': task, 'pair_index': idx, 'released_label': truth,
                    'current_rdkit_label': expected, 'reason': 'version_or_standardization_difference_requires_review'})
            if r.get('iupac_1') and r.get('iupac_1') == r.get('iupac_2') and canonical(r['smiles_1']) != canonical(r['smiles_2']):
                name_collapses.append(idx)
            for side in ('1', '2'):
                value = r.get('selfies_' + side)
                if value:
                    try:
                        if canonical(selfies.decoder(value)) != canonical(r['smiles_' + side]):
                            bad_selfies.append({'pair_index': idx, 'side': side})
                    except Exception:
                        bad_selfies.append({'pair_index': idx, 'side': side})
        findings['B' + str(task)] = {'rows': len(rows), 'pair_types': dict(Counter(r['pair_type'] for r in rows)),
            'label_counts': dict(Counter(r['ground_truth'] for r in rows)),
            'source_values': dict(Counter(r.get('source', 'not_recorded') for r in rows)),
            'labels_disagree_current_rdkit': len(bad_label), 'label_disagreement_first10': bad_label[:10],
            'released_code_disagrees_csv_labels': len(old_bad) if task == 5 else None,
            'stored_selfies_member_mismatches': len(bad_selfies), 'selfies_mismatch_first5': bad_selfies[:5],
            'identical_iupac_for_distinct_stereo_smiles': len(name_collapses)}
    test = read_csv(DATA / 'chebi20_test.csv')
    by_id = {r['molecule_id']: r for r in test}
    ids = [r['molecule_id'] for r in read_csv(DATA / 'comprehension_subset_ids.csv')]
    masses, rings = [], []
    for mid in ids:
        mol = Chem.MolFromSmiles(by_id[mid]['smiles'])
        masses.append(Descriptors.MolWt(mol)); rings.append(mol.GetRingInfo().NumRings())
    distractors = Counter(r['target_molecule_id'] for r in read_csv(DATA / 'retrieval_distractors.csv'))
    findings['comprehension'] = {'test_rows': len(test), 'subset_rows': len(ids),
        'minimum_molecular_weight': min(masses), 'minimum_rings': min(rings),
        'retrieval_targets_with_3_distractors': sum(distractors[i] == 3 for i in ids),
        'nonempty_representations_in_test': {rep: sum(bool(r.get(rep)) for r in test) for rep in REPRESENTATIONS}}
    if iupac:
        results = []
        # Audit all distinct member/name mappings, including pairs, not just the base table.
        members = {(r['smiles'], r['iupac']) for r in test if r.get('iupac')}
        for file in ('isomer_pairs.csv', 'tautomer_pairs250.csv', 'protonation_pairs250.csv'):
            for r in read_csv(DATA / file):
                for side in ('1', '2'):
                    if r.get('iupac_' + side):
                        members.add((r['smiles_' + side], r['iupac_' + side]))
        for index, (smiles, name) in enumerate(sorted(members), 1):
            mol, status = decode(name, 'iupac', allow_network=True)
            result = {'smiles': smiles, 'iupac': name, 'decoder_status': status,
                'exact_stereo_match': None, 'connectivity_match': None}
            if mol is not None:
                found = Chem.MolToSmiles(mol, isomericSmiles=True)
                result.update(exact_stereo_match=canonical(smiles) == canonical(found),
                    connectivity_match=canonical(smiles, False) == canonical(found, False))
            results.append(result)
            print(f'IUPAC input audit {index}/{len(members)}', flush=True)
        write_json(Path(output).with_name('iupac_input_audit.json'), results)
        findings['iupac_audit_counts'] = dict(Counter(r['decoder_status'] for r in results))
    write_json(output, findings)
    write_json(Path(output).with_name('label_disagreements.json'), disagreements)
    return findings

def doctor():
    import importlib.metadata
    import platform
    from .core import obabel_exe
    versions = {}
    for name in ('rdkit', 'selfies', 'deepsmiles', 'openbabel-wheel', 'openbabel',
                 'numpy', 'scipy', 'pandas', 'requests', 'python-docx', 'reportlab'):
        try: versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name] = 'MISSING'
    exe = obabel_exe()
    note = ('CML encode/decode uses the OpenBabel CLI (obabel). '
            'Windows openbabel-wheel lacks the cml format and the conda-forge '
            'Python binding fails to load formats_common/formats_xml plugins '
            'in-process, so the author-style CLI path is used; real CML only, '
            'never SMILES-as-CML.')
    return {'python': platform.python_version(), 'platform': platform.platform(),
        'dependencies': versions, 'obabel_executable': exe,
        'obabel_on_path': exe is not None,
        'note': note,
        'source_repo': 'https://github.com/arunraja-hub/molrepbench',
        'source_commit': '21d36941cddf0dc1ffb5f3590296592dc68e4ac8'}
