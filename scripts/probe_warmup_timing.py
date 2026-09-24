"""Fixed public Gemma timing diagnostic. No holdout access or benchmark rerun."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from moa.comparison import ROOT, hardware, source_hashes, write_json
from moa.contracts import MAX_BYTES, canonical, stamp, strict_json
from moa.engine import ENTRY
from moa.guidance_experiment import prompts
from moa.providers import Ollama, RESPONSE_SCHEMA, wire_json

MODEL = 'gemma4:12b-it-q4_K_M'
DIGEST = '4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c'
INVENTORY = ROOT / 'receipts/v0.7-gemma-gguf/inventory.json'
PROTOCOL = ROOT / 'docs/gemma-warmup-timing.md'
TIMEOUT = 120
PAIRS = 3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body():
    return {'model': MODEL, 'messages': [
        {'role': 'system', 'content': prompts()['policy-only']},
        {'role': 'user', 'content': canonical(ENTRY)}],
        'format': RESPONSE_SCHEMA, 'stream': False,
        'options': {'temperature': 0, 'seed': 0, 'num_predict': 768, 'num_ctx': 8192},
        'think': False, 'keep_alive': '5m'}


def design():
    return {'scope': 'public full-protocol warmup timing only', 'model': MODEL, 'digest': DIGEST,
            'pairs': PAIRS, 'maximum_completion_attempts': PAIRS * 2,
            'measurement_socket_timeout_s': TIMEOUT, 'scored_request_timeout_s_unchanged': 20,
            'request_wire_sha256': hashlib.sha256(wire_json(body())).hexdigest(),
            'inventory_sha256': sha(INVENTORY), 'protocol_sha256': sha(PROTOCOL),
            'source_sha256': source_hashes()}


def register(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump({'registered_at': stamp(), 'design': design()}, f, indent=2)
        f.write('\n')
    return {'registration_sha256': sha(path)}


def recommendation(rows, intact):
    if not intact or len(rows) != 6 or not all(row['valid_first_read'] for row in rows):
        return {'status': 'inconclusive', 'proposed_warmup_timeout_s': None}
    cold = max(row['wall_ms'] for row in rows if row['state'] == 'unloaded') / 1000
    warm = max(row['wall_ms'] for row in rows if row['state'] == 'loaded') / 1000
    result = {'unloaded_max_s': cold, 'loaded_max_s': warm, 'proposed_warmup_timeout_s': None}
    if warm > 20:
        result['status'] = 'longer_warmup_alone_not_supported'
    elif cold <= 20:
        result['status'] = 'longer_warmup_not_shown_necessary'
    else:
        allowance = next((x for x in (60, 120) if cold * 1.5 <= x), None)
        result.update(status='separate_warmup_registration_supported' if allowance else 'inconclusive',
                      proposed_warmup_timeout_s=allowance)
    return result


def loaded(provider):
    value = provider.request('GET', '/api/ps')
    rows = value['models']
    if any(m.get('name') != MODEL or m.get('digest') != DIGEST for m in rows):
        raise RuntimeError('Another model or artifact is loaded; do not evict it.')
    if len(rows) > 1:
        raise RuntimeError('Ambiguous loaded model inventory.')
    return rows


def completion(folder, label):
    row = {'state': label, 'started_at': stamp(), 'valid_first_read': False}
    encoded = wire_json(body())
    (folder / 'request.json').write_bytes(encoded)
    row['request_wire_sha256'] = hashlib.sha256(encoded).hexdigest()
    connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=TIMEOUT)
    started = time.monotonic()
    try:
        connection.request('POST', '/api/chat', encoded, {'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(MAX_BYTES + 1)
        (folder / 'response.txt').write_bytes(raw)
        row.update(http_status=response.status, response_wire_sha256=hashlib.sha256(raw).hexdigest())
        result = strict_json(raw)
        row['reported'] = {k: result[k] for k in ('model','done','done_reason','total_duration',
            'load_duration','prompt_eval_count','prompt_eval_cached_count','prompt_eval_duration',
            'eval_count','eval_duration') if k in result}
        candidate = strict_json(result['message']['content'])
        row['parsed_content'] = candidate
        row['valid_first_read'] = (response.status == 200 and result.get('model') == MODEL
            and result.get('done') is True and result.get('done_reason') == 'stop'
            and candidate == {'kind': 'tool', 'name': 'read_snapshot', 'arguments': {}})
    except Exception as exc:
        row['error_type'] = type(exc).__name__
    finally:
        row['wall_ms'] = round((time.monotonic() - started) * 1000, 2)
        connection.close()
        write_json(folder / 'result.json', row)
    return row


def run(registration, expected_sha, output):
    plan = json.loads(Path(registration).read_text())
    if sha(registration) != expected_sha or plan['design'] != design():
        raise ValueError('Registration or source changed before diagnostic.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    record = {'started_at': stamp(), 'status': 'preparing', 'registration_sha256': expected_sha,
              'hardware': hardware(), 'completion_attempts': 0, 'rows': [], 'private_data_accessed': False}
    write_json(output / 'run.json', record)
    write_json(output / 'registration.json', plan)
    provider = Ollama(MODEL, expected_digest=DIGEST)
    approved = json.loads(INVENTORY.read_text())
    def integrity():
        if design() != plan['design']:
            raise RuntimeError('Registered source or inputs changed.')
        if provider.prepare() != approved['selected_models'][0]:
            raise RuntimeError('Provider metadata changed.')
        if provider.request('GET', '/api/version') != approved['server_version']:
            raise RuntimeError('Daemon version changed.')
    try:
        integrity()
        record['metadata_before'] = provider.receipt
        for pair in range(PAIRS):
            folder = output / f'pair-{pair+1}'
            folder.mkdir()
            before = loaded(provider)
            write_json(folder / 'before-unload.json', before)
            if before:
                # Documented residency command only. Never unload another model.
                reply = provider.request('POST', '/api/generate', {'model': MODEL, 'keep_alive': 0, 'stream': False})
                write_json(folder / 'unload.json', reply)
            after = loaded(provider)
            write_json(folder / 'after-unload.json', after)
            if after:
                raise RuntimeError('Model did not unload; no inference attempted in this pair.')
            for state in ('unloaded', 'loaded'):
                integrity()
                if state == 'loaded':
                    state_rows = loaded(provider)
                    write_json(folder / 'before-loaded.json', state_rows)
                    if not state_rows or state_rows[0].get('context_length') != 8192:
                        raise RuntimeError('Loaded counterpart unavailable or context differs.')
                attempt = folder / state
                attempt.mkdir()
                record['completion_attempts'] += 1
                write_json(output / 'run.json', record)
                row = completion(attempt, state)
                record['rows'].append(dict(row, pair=pair+1))
                write_json(output / 'run.json', record)
                if not row['valid_first_read']:
                    raise RuntimeError('Public protocol request failed; stop without retry.')
        integrity()
        record['metadata_after'] = provider.receipt
        record['loaded_after'] = loaded(provider)
        record['status'] = 'completed'
    except Exception as exc:
        record.update(status='interrupted', error_type=type(exc).__name__)
    finally:
        try:
            record['source_unchanged'] = plan['design'] == design()
        except Exception:
            record['source_unchanged'] = False
        if not record['source_unchanged']:
            record['status'] = 'interrupted'
        record['recommendation'] = recommendation(record['rows'], record['status'] == 'completed' and record['source_unchanged'])
        record['finished_at'] = stamp()
        write_json(output / 'run.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    reg = sub.add_parser('register'); reg.add_argument('--output', required=True)
    execute = sub.add_parser('run')
    for name in ('registration', 'expected-sha256', 'output'):
        execute.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = register(args.output) if args.command == 'register' else run(args.registration, args.expected_sha256, args.output)
    print(json.dumps(result))
    return 0 if args.command == 'register' or result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
