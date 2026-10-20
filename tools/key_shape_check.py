"""Key shape diagnosis without revealing the key.

Prints only: length, character-class analysis and a short SHA-256 fingerprint.
Official DeepSeek keys look like sk- + 32 lowercase hex characters. A key that is
sk- + 32 chars but not hex usually belongs to another provider or relay.
"""
import hashlib
import os
import re
import string
import sys

key = os.environ.get('LLM_API_KEY', '')
if not key:
    print('NO KEY in environment')
    raise SystemExit(2)

body = key[3:] if key.startswith('sk-') else key
hex_like = bool(re.fullmatch(r'[0-9a-fA-F]+', body))
base62 = bool(re.fullmatch(r'[0-9a-zA-Z]+', body))
special = sorted(set(body) & set(string.punctuation))

print('length          :', len(key))
print('starts with sk- :', key.startswith('sk-'))
print('body is hex     :', hex_like)
print('body is alnum   :', base62)
print('special chars   :', special if special else 'none')
print('sha256[:12]     :', hashlib.sha256(key.encode()).hexdigest()[:12])
print()
print('official DeepSeek key pattern: sk- + 32 lowercase hex chars')