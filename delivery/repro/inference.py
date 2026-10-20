"""OpenAI-compatible HTTP inference with frozen prompts and guarded resume.

Only item['prompt'] is sent. Reference labels never enter the model request.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import time
from .core import ROOT, digest, read_jsonl, write_json

def load_settings(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    if not cfg.get('model') or cfg['model'].startswith('REPLACE'):
        raise ValueError('Set the exact served model ID in settings.json first.')
    if cfg.get('thinking', 'unset') not in ('on', 'off', 'unset'):
        raise ValueError('thinking must be on, off or unset')
    return cfg

def request_payload(item, cfg):
    # Paper prompts are unchanged; reasoning mode is a separate backend parameter.
    body = {'model': cfg['model'], 'messages': [{'role': 'user', 'content': item['prompt']}],
            cfg.get('token_parameter', 'max_tokens'): cfg.get('max_tokens', 2048)}
    for key in ('temperature', 'top_p', 'seed'):
        if cfg.get(key) is not None:
            body[key] = cfg[key]
    # HTTP extension fields are top-level. SDK extra_body is not nested in JSON.
    extra = cfg.get('extra_body', {})
    if any(k in extra for k in ('model', 'messages', 'response_format', 'structured_outputs', 'guided_json')):
        raise ValueError('extra_body cannot override messages, model or schema fields')
    body.update(extra)
    if item['task'] == 6:
        mode = cfg.get('schema_mode', 'json_schema')
        if mode == 'json_schema':
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'molecule_output', 'strict': True, 'schema': item['json_schema']}}
        elif mode == 'vllm':
            body['structured_outputs'] = {'json': item['json_schema']}
        elif mode == 'legacy_guided_json':
            body['guided_json'] = item['json_schema']
        elif mode != 'prompt_only':
            raise ValueError(f'Unknown schema_mode: {mode}')
    return body

def run(plan_dir, settings_path, out, max_requests=None):
    import requests
    plan_dir, out = Path(plan_dir), Path(out)
    cfg = load_settings(settings_path)
    items = read_jsonl(plan_dir / 'manifest.jsonl')
    if not items:
        raise ValueError('No manifest. Run prepare first.')
    out.mkdir(parents=True, exist_ok=True)
    # The credential itself is never persisted, logged, or fingerprinted.
    api_env = cfg.get('api_key_env', 'LLM_API_KEY')
    api_key = os.environ.get(api_env, '')
    if cfg.get('require_api_key', False) and not api_key:
        raise ValueError(f'Set environment variable {api_env}; do not paste keys into files.')
    signature = digest(json.dumps(cfg, sort_keys=True) + (plan_dir / 'manifest.jsonl').read_text(encoding='utf-8'))
    meta_path = out / 'run_metadata.json'
    if meta_path.exists():
        old = json.loads(meta_path.read_text(encoding='utf-8'))
        if old['run_signature'] != signature:
            raise ValueError('Settings/manifest changed. Use a NEW output directory to avoid mixing runs.')
    else:
        write_json(meta_path, {'run_signature': signature, 'settings': cfg,
            'manifest_path': str(plan_dir.resolve()), 'started_utc': datetime.now(timezone.utc).isoformat(),
            'result_kind': 'real_model_inference', 'protocol': 'released-data-audited-v1'})
    raw_path = out / 'raw.jsonl'
    done = {r['id'] for r in read_jsonl(raw_path) if r.get('status') == 'ok'}
    pending = [x for x in items if x['id'] not in done]
    if max_requests:
        pending = pending[:max_requests]
    session = requests.Session()
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    endpoint = cfg['base_url'].rstrip('/') + '/chat/completions'
    print(f'{len(pending)} pending requests; {len(done)} already successful. Output: {out}')
    for index, item in enumerate(pending, 1):
        body = request_payload(item, cfg)
        started = time.perf_counter()
        record = {'id': item['id'], 'prompt_sha256': item['prompt_sha256'], 'status': 'error'}
        for attempt in range(cfg.get('retries', 2) + 1):
            try:
                response = session.post(endpoint, json=body, headers=headers,
                                        timeout=cfg.get('timeout_seconds', 180))
                if response.status_code != 200:
                    record['error'] = f'HTTP {response.status_code}'
                    if response.status_code not in (429, 500, 502, 503, 504):
                        break
                else:
                    value = response.json()
                    choice = value['choices'][0]
                    message = choice['message']
                    content = message.get('content')
                    if not isinstance(content, str) or not content.strip():
                        record['error'] = 'No final content; inspect token budget or backend reasoning configuration'
                        break
                    record.update(status='ok', raw_response=content,
                        reasoning_content=message.get('reasoning_content', message.get('reasoning')),
                        finish_reason=choice.get('finish_reason'), usage=value.get('usage'),
                        served_model=value.get('model'), request_id=value.get('id'))
                    break
            except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
                record['error'] = type(exc).__name__
            if attempt < cfg.get('retries', 2):
                time.sleep(min(2**attempt, 4))
        record['latency_seconds'] = round(time.perf_counter() - started, 4)
        with raw_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            f.flush()
        print(f'{index}/{len(pending)} {item["id"]} {record["status"]}', flush=True)
        if record['status'] != 'ok' and record.get('error') in ('HTTP 400', 'HTTP 401', 'HTTP 403', 'HTTP 404'):
            raise RuntimeError(f'{record["error"]}; fix settings before resuming. No silent model/schema fallback.')
    latest = {r['id']: r for r in read_jsonl(raw_path)}
    ok = sum(x.get('status') == 'ok' for x in latest.values())
    write_json(out / 'completion.json', {'expected': len(items), 'successful': ok,
        'pending_or_failed': len(items)-ok, 'inference_complete': ok == len(items)})

def import_responses(plan_dir, response_file, out):
    """Import externally run final answers, with exact prompt hash matching."""
    manifest = {r['id']: r for r in read_jsonl(Path(plan_dir) / 'manifest.jsonl')}
    rows = read_jsonl(response_file)
    seen = set()
    for r in rows:
        if r['id'] in seen or r['id'] not in manifest:
            raise ValueError('Duplicate or unknown ID in imported responses')
        seen.add(r['id'])
        if r.get('prompt_sha256') != manifest[r['id']]['prompt_sha256']:
            raise ValueError('Imported response prompt hash does not match the frozen manifest')
        if not isinstance(r.get('raw_response'), str):
            raise ValueError('raw_response must be actual model text')
        r['status'] = 'ok'
    out = Path(out)
    if (out / 'raw.jsonl').exists():
        raise ValueError('Choose a new directory for imported responses')
    from .core import write_jsonl
    write_jsonl(out / 'raw.jsonl', rows)
    write_json(out / 'run_metadata.json', {'result_kind': 'imported_model_responses',
        'manifest_path': str(Path(plan_dir).resolve()), 'source_file': str(response_file),
        'limitations': 'Model identity and inference parameters require separate external evidence'})
