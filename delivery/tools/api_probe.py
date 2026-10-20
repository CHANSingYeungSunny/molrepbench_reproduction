"""One-shot API connectivity probe for settings.json diagnosis.

Sends the same request shape as repro/inference.py and prints the HTTP status
and response body so auth/URL/payload problems can be told apart. The key is
read from the environment (LLM_API_KEY) exactly like the runner; only its
length and sk- prefix are printed, never its content.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests


def main():
    cfg = json.loads((ROOT / 'settings.json').read_text(encoding='utf-8'))
    key = os.environ.get(cfg.get('api_key_env', 'LLM_API_KEY'), '')
    if not key:
        print('NO KEY in environment. Run via tools/run_with_key.py.')
        return 2
    print('key shape: len=%d prefix=%r' % (len(key), key[:3]))

    url = cfg['base_url'].rstrip('/') + '/chat/completions'
    body = {'model': cfg['model'],
            'messages': [{'role': 'user', 'content': 'ping: reply with the single word pong'}],
            cfg.get('token_parameter', 'max_tokens'): 16}
    for k in ('temperature', 'top_p'):
        if cfg.get(k) is not None:
            body[k] = cfg[k]
    body.update(cfg.get('extra_body', {}))
    print('POST', url)
    print('body:', json.dumps({k: v for k, v in body.items() if k != 'messages'}, ensure_ascii=False))
    r = requests.post(url, json=body,
                      headers={'Content-Type': 'application/json',
                               'Authorization': 'Bearer ' + key},
                      timeout=cfg.get('timeout_seconds', 60))
    print('HTTP', r.status_code)
    print('response body:', r.text[:800])
    return 0 if r.status_code == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
