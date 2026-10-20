#!/usr/bin/env python3
"""Start here: python reproduce.py --help"""
import argparse
import json
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description='MolRepBench portable audited reproduction')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('setup', help='Extract bundled author data; no download or LLM')
    commands.add_parser('doctor', help='Print dependency versions')
    commands.add_parser('verify-vendor', help='Check frozen author files against SHA256 provenance')
    a = commands.add_parser('audit', help='Audit labels and stored representations without an LLM')
    a.add_argument('--output', default='evidence/dataset_audit.json')
    a.add_argument('--iupac', action='store_true', help='Additionally query OPSIN to validate all released IUPAC input names')
    a = commands.add_parser('prepare', help='Create all actual prompts and reference labels; no inference')
    a.add_argument('--profile', choices=['smoke', 'paper'], default='smoke')
    a.add_argument('--n', type=int, help='Override per-task molecule/pair cap')
    a.add_argument('--seed', type=int, default=42)
    a.add_argument('--out', default='plans/smoke')
    a.add_argument('--representations', default='all')
    a.add_argument('--iupac-policy', choices=['released','verified'], default='released')
    a = commands.add_parser('run', help='Call your configured model; paid endpoints can incur charges')
    a.add_argument('--plan', default='plans/smoke')
    a.add_argument('--settings', default='settings.json')
    a.add_argument('--out', default='results/smoke')
    a.add_argument('--max-requests', type=int, help='Limit additional calls for connectivity testing')
    a = commands.add_parser('import-responses', help='Import actual externally executed model answers')
    a.add_argument('--plan', required=True); a.add_argument('--file', required=True); a.add_argument('--out', required=True)
    a = commands.add_parser('score', help='Evaluate actual raw responses; preserve missing and undecoded statuses')
    a.add_argument('--plan', default='plans/smoke'); a.add_argument('--run', default='results/smoke')
    a.add_argument('--allow-network', action='store_true', help='Permit OPSIN IUPAC output decoding')
    a.add_argument('--fcd', action='store_true', help='Require optional fcd package; may need weights')
    a = commands.add_parser('bootstrap', help='Paired bootstrap on common molecules with a predeclared reference')
    a.add_argument('--run', default='results/paper'); a.add_argument('--reference', default='canonical_smiles')
    a.add_argument('--samples', type=int, default=10000); a.add_argument('--seed', type=int, default=42)
    a = commands.add_parser('report', help='Generate truthful Chinese DOCX/PDF from saved results')
    a.add_argument('--run', default='results/paper'); a.add_argument('--out', default='reports')
    a = commands.add_parser('judge', help='Optional LLM-as-judge extension on actual B6 outputs')
    a.add_argument('--run', required=True); a.add_argument('--plan', required=True)
    a.add_argument('--settings', required=True); a.add_argument('--n', type=int, default=10)
    args = p.parse_args()
    # All relative paths resolve within the extracted project, even when invoked elsewhere.
    from repro.core import ROOT
    import os
    os.chdir(ROOT)
    if args.command == 'setup':
        from repro.core import setup
        value = {'extracted_files': setup()}
    elif args.command == 'doctor':
        from repro.audit import doctor
        value = doctor()
    elif args.command == 'verify-vendor':
        import hashlib
        records = json.loads((ROOT / 'UPSTREAM_PROVENANCE.json').read_text(encoding='utf-8'))
        bad = []
        for name, expected in records['files_sha256'].items():
            file = ROOT / 'vendor' / 'molrepbench' / name
            if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                bad.append(name)
        value = {'files_checked': len(records['files_sha256']), 'changed_or_missing': bad}
        if bad: raise RuntimeError(str(value))
    elif args.command == 'audit':
        from repro.audit import audit
        value = audit(args.output, args.iupac)
    elif args.command == 'prepare':
        from repro.core import prepare
        value = prepare(args.out, args.profile, args.n, args.seed,
                        None if args.representations == 'all' else args.representations.split(','), args.iupac_policy)
    elif args.command == 'run':
        from repro.inference import run
        run(args.plan, args.settings, args.out, args.max_requests); return
    elif args.command == 'import-responses':
        from repro.inference import import_responses
        import_responses(args.plan, args.file, args.out); return
    elif args.command == 'score':
        from repro.scoring import score
        value = score(args.plan, args.run, args.allow_network, args.fcd)
    elif args.command == 'bootstrap':
        if args.samples < 1: raise ValueError('samples must be positive')
        from repro.scoring import bootstrap
        value = {'comparisons': bootstrap(args.run, args.reference, args.samples, args.seed)}
    elif args.command == 'report':
        from repro.reporting import report
        value = report(args.run, args.out)
    elif args.command == 'judge':
        from repro.extensions import judge
        value = judge(args.plan, args.run, args.settings, args.n)
    print(json.dumps(value, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
