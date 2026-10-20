"""Software checks only. Perfect fixtures are NOT LLM experiment results."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from repro.core import ROOT, DATA, TASKS, REPRESENTATIONS, read_csv, read_jsonl, prepare, write_jsonl, encode, decode, canonical
from repro.inference import request_payload, run
from repro.scoring import parse, score

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.plan = Path(cls.tmp.name) / 'plan'
        prepare(cls.plan, n=1)
        cls.items = read_jsonl(cls.plan / 'manifest.jsonl')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_task_every_representation(self):
        self.assertEqual({r['task'] for r in self.items}, set(TASKS))
        self.assertEqual(len(self.items), 135)
        for task in TASKS:
            self.assertEqual({r['representation'] for r in self.items if r['task'] == task}, set(REPRESENTATIONS))
        self.assertEqual(len({r['id'] for r in self.items}), len(self.items))

    def test_retrieval_choices_paired_across_representations(self):
        choices = [r['choice_ids'] for r in self.items if r['task'] == 4]
        self.assertTrue(all(c == choices[0] for c in choices))

    def test_repeatable_prompts(self):
        other = Path(self.tmp.name) / 'again'
        prepare(other, n=1)
        self.assertEqual((self.plan / 'manifest.jsonl').read_bytes(), (other / 'manifest.jsonl').read_bytes())

    def test_parser_does_not_take_reasoning_numbers(self):
        self.assertIsNone(parse('There are 6 atoms, but I am not sure.', 1))
        self.assertIsNone(parse('<think>42 atoms', 1))
        self.assertEqual(parse('Some text 17. The answer is \\boxed{6}', 1), 6)
        self.assertEqual(parse('\\boxed{3} then \\boxed{5}', 1), 5)
        self.assertEqual(parse('\\boxed{No}', 5), False)
        self.assertIsNone(parse('Yes and no', 5))
        self.assertIsNone(parse('\\boxed{2.5}', 1))
        self.assertEqual(parse('Final answer: -1.3e-2', 3), -0.013)

    def test_ground_truth_not_in_request_fields(self):
        item = self.items[0]
        body = request_payload(item, {'model': 'fixture', 'extra_body': {}})
        self.assertNotIn('ground_truth', body)
        self.assertEqual(body['messages'], [{'role':'user', 'content':item['prompt']}])

    def test_eight_local_representations_roundtrip(self):
        from rdkit import Chem
        smiles='CC(=O)Oc1ccccc1C(=O)O'
        for rep in REPRESENTATIONS:
            if rep=='iupac':continue
            molecule,status=decode(encode(smiles,rep),rep)
            self.assertEqual(status,'ok',rep)
            self.assertEqual(canonical(Chem.MolToSmiles(molecule),False),canonical(smiles,False),rep)

    def test_b5_csv_matches_exact_identity_for_all_pairs(self):
        rows=read_csv(DATA/'isomer_pairs.csv')
        self.assertEqual(len(rows),500)
        for row in rows:
            expected=canonical(row['smiles_1'])==canonical(row['smiles_2'])
            self.assertEqual(expected,row['ground_truth'].lower()=='true')

    def test_verified_iupac_excludes_unreviewed_inputs(self):
        root=Path(self.tmp.name)/'strict_root'
        (root/'evidence').mkdir(parents=True,exist_ok=True)
        (root/'evidence/iupac_input_audit.json').write_text('[]')
        with patch('repro.core.ROOT',root):
            dest=Path(self.tmp.name)/'verified'
            prepare(dest,n=1,iupac_policy='verified')
        items=read_jsonl(dest/'manifest.jsonl')
        self.assertFalse(any(r['representation']=='iupac' and r['task']!=6 for r in items))
        self.assertTrue(any(r['representation']=='iupac' and r['task']==6 for r in items))

    def test_missing_requests_not_dropped_from_denominator(self):
        dest = Path(self.tmp.name) / 'empty_results'
        dest.mkdir(exist_ok=True)
        result = score(self.plan, dest)
        self.assertFalse(result['inference_complete'])
        self.assertEqual(result['expected_requests'], 135)
        self.assertEqual(result['api_success'], 0)
        summary = json.loads((dest / 'summary.json').read_text())
        self.assertTrue(all(r['accuracy_all'] == 0 for r in summary if 'accuracy_all' in r))

    def test_software_fixture_metrics_and_iupac_unknown(self):
        dest = Path(self.tmp.name) / 'software_fixture'
        fixture = []
        for item in self.items:
            truth = item['ground_truth']
            if item['task'] == 6:
                # A fixed known valid string exercises generation decoding; not a model answer.
                output = json.dumps({'molecule':'ethanol' if item['representation']=='iupac' else 'CCO'})
            elif isinstance(truth, bool):
                output = '\\boxed{' + ('Yes' if truth else 'No') + '}'
            else:
                output = '\\boxed{' + str(truth) + '}'
            fixture.append({'id':item['id'], 'prompt_sha256':item['prompt_sha256'],
                            'status':'ok', 'raw_response':output})
        write_jsonl(dest / 'raw.jsonl', fixture)
        result = score(self.plan, dest)
        self.assertTrue(result['inference_complete'])
        summary = json.loads((dest / 'summary.json').read_text())
        self.assertTrue(all(r['accuracy_all'] == 1 for r in summary if 'accuracy_all' in r))
        iupac = next(r for r in summary if r['task']==6 and r['representation']=='iupac')
        # Without OPSIN answers (offline or cache-miss) the rate must stay empty rather
        # than being counted as invalid; with a warm cache it must be reported.
        if iupac['n_decoder_evaluated'] == 0:
            self.assertIsNone(iupac['validity_rate'])
        else:
            self.assertIsNotNone(iupac['validity_rate'])
            self.assertIsNotNone(iupac['validity_evaluated_only'])

    def test_resume_and_changed_config_guard(self):
        dest = Path(self.tmp.name) / 'transport_fixture'
        cfgpath = Path(self.tmp.name) / 'settings.json'
        cfg = {'model':'fixture-model', 'base_url':'http://127.0.0.1:9/v1', 'retries':0}
        cfgpath.write_text(json.dumps(cfg))
        class Response:
            status_code = 200
            def json(self):
                return {'choices':[{'message':{'content':'\\boxed{5}'}, 'finish_reason':'stop'}]}
        with patch('requests.Session.post', return_value=Response()) as mock:
            run(self.plan, cfgpath, dest, max_requests=1)
            self.assertEqual(mock.call_count, 1)
            run(self.plan, cfgpath, dest, max_requests=1)
            self.assertEqual(mock.call_count, 2)
            self.assertEqual(len({r['id'] for r in read_jsonl(dest/'raw.jsonl')}),2)
            cfg['max_tokens']=500
            cfgpath.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                run(self.plan, cfgpath, dest, max_requests=1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
