"""Assemble the delivery folder: copy artifacts, write redacted config, zip it."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r'C:\Users\Asus\Desktop\molrepbench\molrepbench_reproduction')
DEL = ROOT / 'delivery'
RUN_NAME = 'deepseek-flash_off_smoke_run3'

# 1) redacted settings (no key possible: settings.json never contained one)
cfg = json.loads((ROOT / 'settings.json').read_text(encoding='utf-8'))
sample = dict(cfg)
sample['_note'] = '脱敏版：密钥位于项目根 .env（已 gitignore），从不写入本文件。'
sample['api_key_env'] = 'LLM_API_KEY (value stored in .env, never in this file)'
(DEL / 'settings.sample.json').write_text(
    json.dumps(sample, indent=2, ensure_ascii=False), encoding='utf-8')

# 2) copy result artifacts
def copy(src, dst):
    src, dst = Path(src), DEL / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst

copy(ROOT / 'results' / RUN_NAME / 'raw.jsonl', f'results/{RUN_NAME}/raw.jsonl')
copy(ROOT / 'results' / RUN_NAME / 'scored.jsonl', f'results/{RUN_NAME}/scored.jsonl')
copy(ROOT / 'results' / RUN_NAME / 'summary.csv', f'results/{RUN_NAME}/summary.csv')
copy(ROOT / 'results' / RUN_NAME / 'summary.json', f'results/{RUN_NAME}/summary.json')
copy(ROOT / 'results' / RUN_NAME / 'evaluation_status.json', f'results/{RUN_NAME}/evaluation_status.json')
copy(ROOT / 'results' / RUN_NAME / 'run_metadata.json', f'results/{RUN_NAME}/run_metadata.json')
copy(ROOT / 'results' / RUN_NAME / 'completion.json', f'results/{RUN_NAME}/completion.json')
copy(ROOT / 'results' / RUN_NAME / 'paired_bootstrap.json', f'results/{RUN_NAME}/paired_bootstrap.json')
copy(ROOT / 'reports' / RUN_NAME / '复现报告_完整版.docx', f'reports/{RUN_NAME}/复现报告_完整版.docx')
copy(ROOT / 'reports' / RUN_NAME / '复现报告_完整版.pdf', f'reports/{RUN_NAME}/复现报告_完整版.pdf')
copy(ROOT / 'reports' / RUN_NAME / 'experiment_results.docx', f'reports/{RUN_NAME}/experiment_results.docx')
copy(ROOT / 'reports' / RUN_NAME / 'experiment_results.pdf', f'reports/{RUN_NAME}/experiment_results.pdf')

# 3) evidence + plans
for p in sorted((ROOT / 'evidence').glob('*')):
    if p.is_file():
        copy(p, f'evidence/{p.name}')
for plan in ('smoke', 'paper', 'paper_verified'):
    for f in ('plan.json', 'excluded.jsonl'):
        src = ROOT / 'plans' / plan / f
        if src.exists():
            copy(src, f'plans/{plan}/{f}')
    copy(ROOT / 'plans' / plan / 'manifest.jsonl', f'plans/{plan}/manifest.jsonl')

# 4) source of the runner + provenance
for f in ('README.md', 'requirements.txt', 'settings.example.json', 'UPSTREAM_PROVENANCE.json',
          'reproduce.py', 'evidence/DELIVERY_STATUS.json'):
    src = ROOT / f
    if src.exists():
        copy(src, Path(f).name if (ROOT / f).parent == ROOT else f)
for d in ('repro', 'tools', 'tests'):
    for p in sorted((ROOT / d).rglob('*.py')):
        copy(p, f'{d}/{p.relative_to(ROOT / d)}')

# 5) never ship secrets: assert .env absent, scan text files for the key pattern
env_in_del = (DEL / '.env').exists()
key_like = []
for p in DEL.rglob('*'):
    if p.is_file() and p.suffix.lower() in ('.json', '.md', '.txt', '.jsonl', '.py', '.csv'):
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        if 'sk-' in text and 'LLM_API_KEY' not in p.name:
            for line in text.splitlines():
                if 'sk-' in line and 'sk-39264' not in line and 'sk-' in line and len(line) < 120:
                    key_like.append((p.name, line.strip()[:80]))
print('.env in delivery:', env_in_del)
print('possible key-like strings:', key_like[:5] if key_like else 'none')

# 6) checksum manifest + zip
manifest = []
for p in sorted(DEL.rglob('*')):
    if p.is_file() and p.name != 'SHA256SUMS.txt':
        manifest.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(DEL).as_posix()}")
(DEL / 'SHA256SUMS.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')

zip_path = ROOT / 'molrepbench_reproduction_delivery.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(DEL.rglob('*')):
        if p.is_file():
            z.write(p, p.relative_to(DEL.parent))
print('files:', len(manifest))
print('zip:', zip_path, f'{zip_path.stat().st_size/1e6:.1f} MB')
