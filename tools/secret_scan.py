"""Final safety scan: no real API key may exist in any deliverable text artifact."""
import re
import zipfile
from pathlib import Path

ROOT = Path(r'C:\Users\Asus\Desktop\molrepbench\molrepbench_reproduction')
PATTERN = re.compile(r'sk-[A-Za-z0-9]{20,}')
TARGETS = []
for base in ('delivery', 'evidence', 'results', 'reports', 'plans', 'tools', 'repro', 'tests'):
    for p in (ROOT / base).rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.json', '.md', '.txt', '.jsonl', '.py', '.csv'):
            TARGETS.append(p)
for name in ('settings.json', 'settings.example.json', 'README.md', 'reproduce.py', 'UPSTREAM_PROVENANCE.json'):
    p = ROOT / name
    if p.exists():
        TARGETS.append(p)

hits = []
for p in TARGETS:
    text = p.read_text(encoding='utf-8', errors='ignore')
    for m in PATTERN.finditer(text):
        s = m.group(0)
        if len(s) >= 30:                      # real keys are 35 chars
            hits.append((str(p.relative_to(ROOT)), len(s)))

zp = ROOT / 'molrepbench_reproduction_delivery.zip'
zhits = []
if zp.exists():
    with zipfile.ZipFile(zp) as z:
        for n in z.namelist():
            if n.lower().endswith(('.json', '.md', '.txt', '.jsonl', '.py', '.csv')):
                text = z.read(n).decode('utf-8', errors='ignore')
                for m in PATTERN.finditer(text):
                    if len(m.group(0)) >= 30:
                        zhits.append(n)

print('scanned files:', len(TARGETS))
print('real-key-like hits in project:', hits if hits else 'NONE')
print('real-key-like hits in zip     :', zhits if zhits else 'NONE')
print('.env present in delivery      :', (ROOT / 'delivery' / '.env').exists())
print('.env present in zip           :', any(n.endswith('.env') for n in zipfile.ZipFile(zp).namelist()) if zp.exists() else 'n/a')