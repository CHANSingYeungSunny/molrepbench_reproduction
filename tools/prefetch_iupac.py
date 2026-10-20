"""Parallel OPSIN prefetch for the IUPAC input audit.

Why: the single-threaded audit --iupac loop needs one HTTPS round trip per
distinct IUPAC name (~4-5 s each from this machine to opsin.ch.cam.ac.uk),
i.e. several hours for the full member set. This tool only *warms* the exact
same cache (results/opsin_cache.json) with the exact same endpoint, status
mapping and JSON shape that repro.core.decode() uses, so that the subsequent
`reproduce.py audit --iupac` run is a cache hit and produces identical output.

No LLM calls. No SMILES is ever written into an IUPAC field; failures are kept.
"""
import csv
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.core import DATA, ROOT as REPRO_ROOT, write_json  # noqa: E402

CACHE = ROOT / 'results' / 'opsin_cache.json'
FAILURES = ROOT / 'results' / 'opsin_failures.jsonl'
OPSIN = 'https://opsin.ch.cam.ac.uk/opsin/'
WORKERS = 8
TIMEOUT = 20


def member_names():
    names = set()
    with open(DATA / 'chebi20_test.csv', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('iupac'):
                names.add(r['iupac'])
    for name in ('isomer_pairs.csv', 'tautomer_pairs250.csv', 'protonation_pairs250.csv'):
        with open(DATA / name, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                for side in ('1', '2'):
                    if r.get('iupac_' + side):
                        names.add(r['iupac_' + side])
    return names


def fetch(name):
    """Same endpoint/status mapping as repro.core.decode(..., allow_network=True)."""
    try:
        r = requests.get(OPSIN + quote(name, safe='') + '.smi', timeout=TIMEOUT)
    except requests.RequestException as exc:
        return name, None, type(exc).__name__
    if r.status_code == 200:
        return name, {'status': 'ok', 'smiles': r.text.strip()}, None
    if r.status_code in (400, 404):
        return name, {'status': 'invalid', 'smiles': None}, None
    return name, None, f'HTTP {r.status_code}'


def main():
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    names = member_names()
    todo = [n for n in sorted(names) if n not in cache]
    print(f'{len(names)} distinct names; {len(cache)} cached; {len(todo)} to fetch', flush=True)
    lock = threading.Lock()
    failures, done = [], 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch, n): n for n in todo}
        for fut in as_completed(futures):
            name, value, error = fut.result()
            with lock:
                if value is not None:
                    cache[name] = value
                else:
                    failures.append({'iupac': name, 'error': error})
                done += 1
                if done % 100 == 0:
                    write_json(CACHE, cache)
                    print(f'{done}/{len(todo)} fetched, {time.time()-started:.0f}s elapsed', flush=True)
    write_json(CACHE, cache)
    if failures:
        with FAILURES.open('a', encoding='utf-8') as f:
            for rec in failures:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    ok = sum(1 for v in cache.values() if v.get('status') == 'ok')
    print(f'cache now {len(cache)} entries ({ok} ok, {len(cache)-ok} invalid); '
          f'{len(failures)} fetch failures recorded in {FAILURES.name}', flush=True)


if __name__ == '__main__':
    main()
