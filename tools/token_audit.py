"""Optional token-length audit. This is NOT a reproduction of all mechanistic figures.

Usage: python tools/token_audit.py --tokenizer <HF-ID-or-local-path> --n 1000
No approximate 'characters / 4' token counts are used.
"""
import argparse
import csv
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repro.core import ROOT, DATA, REPRESENTATIONS, setup, read_csv, encode

def main():
    from transformers import AutoTokenizer
    p=argparse.ArgumentParser()
    p.add_argument('--tokenizer', required=True)
    p.add_argument('--n', type=int, default=1000)
    p.add_argument('--out', default=str(ROOT/'results/token_audit.csv'))
    args=p.parse_args()
    setup()
    tokenizer=AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=False)
    rows=[]
    for item in read_csv(DATA/'chebi20_test.csv')[:args.n]:
        for rep in REPRESENTATIONS:
            value=encode(item['smiles'],rep,item.get('iupac'),42)
            rows.append({'molecule_id':item['molecule_id'],'representation':rep,
                         'tokenizer':args.tokenizer, 'n_chars':len(value) if value else None,
                         'n_tokens':len(tokenizer.encode(value,add_special_tokens=False)) if value else None})
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(out)

if __name__=='__main__':main()
