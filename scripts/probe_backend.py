"""Public-only local compatibility probe. Never opens a private holdout.

One schema-conflict request, then at most six calls for one public window when
the schema probe passes. No retries, repairs, downloads or cloud requests.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from moa.comparison import source_hashes, write_json
from moa.contracts import MAX_BYTES, canonical, stamp, strict_json
from moa.engine import Agent
from moa.evidence import EvidenceStore
from moa.fixtures import window_fixture
from moa.guidance_experiment import prompts
from moa.providers import Ollama, wire_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--expected-digest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--schema-only', action='store_true', help='Stop after one schema request.')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    provider = Ollama(args.model, expected_digest=args.expected_digest)
    record = {'started_at': stamp(), 'status': 'preparing', 'scope': 'public-fixture-backend-diagnostic',
              'source_sha256': source_hashes(), 'maximum_completion_attempts': 1 if args.schema_only else 7,
              'schema_only': args.schema_only,
              'design': 'Schema must override a contradictory public prompt; run one public window only if it passes.',
              'context_limit': 'Requested 8192; api/ps is a daemon report, not independent proof of enforcement.',
              'private_holdout_accessed': False, 'retries': 0}
    write_json(output / 'run.json', record)
    try:
        record['metadata_before'] = provider.prepare()
        record['version_before'] = provider.request('GET', '/api/version')
        body = {'model': args.model, 'messages': [{'role': 'user', 'content':
                'Return exactly this JSON and nothing else: {"probe":"user_requested_wrong","extra":true}'}],
                'format': {'type': 'object', 'required': ['probe'], 'additionalProperties': False,
                           'properties': {'probe': {'type': 'string', 'enum': ['schema_only_7c92']}}},
                'options': dict(provider.settings), 'think': False, 'stream': False, 'keep_alive': '5m'}
        encoded = wire_json(body)
        (output / 'schema.request.json').write_bytes(encoded)
        schema = {'started_at': stamp(), 'request_wire_sha256': hashlib.sha256(encoded).hexdigest(),
                  'passed': False}
        write_json(output / 'schema.json', schema)
        connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=20)
        started = time.monotonic()
        try:
            connection.request('POST', '/api/chat', body=encoded, headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(MAX_BYTES + 1)
            (output / 'schema.response.txt').write_bytes(raw)
            schema['http_status'] = response.status
            schema['response_sha256'] = hashlib.sha256(raw).hexdigest()
            parsed = strict_json(raw)
            content = parsed.get('message', {}).get('content')
            schema['reported_model'] = parsed.get('model')
            schema['done'] = parsed.get('done')
            schema['finish_reason'] = parsed.get('done_reason')
            if response.status == 200 and parsed.get('model') == args.model and parsed.get('done') is True:
                schema['parsed_content'] = strict_json(content)
                schema['passed'] = schema['parsed_content'] == {'probe': 'schema_only_7c92'}
        except Exception as exc:
            schema['error_type'] = type(exc).__name__
        finally:
            connection.close()
            schema['wall_ms'] = round((time.monotonic() - started) * 1000, 2)
            write_json(output / 'schema.json', schema)
        record['schema_constraint_passed'] = schema['passed']
        loaded = provider.request('GET', '/api/ps')
        record['loaded_model_reports'] = [{k: m[k] for k in ('name','digest','context_length','size','size_vram') if k in m}
                                          for m in loaded.get('models', []) if m.get('name') == args.model]
        record['public_window_attempted'] = False
        if schema['passed'] and not args.schema_only:
            store = EvidenceStore(output / 'public-window.sqlite3')
            record['public_window_attempted'] = True
            try:
                result = Agent(store, provider, system_prompt=prompts()['policy-only']).assess(window_fixture())
                write_json(output / 'public-window.json', {'result': result, 'evidence': store.bundle()})
                record['public_window_status'] = result['status']
                record['public_window_reason'] = result['reason']
            finally:
                store.close()
        record['metadata_after'] = provider.prepare()
        record['version_after'] = provider.request('GET', '/api/version')
        record['metadata_unchanged'] = record['metadata_before'] == record['metadata_after']
        record['source_unchanged'] = record['source_sha256'] == source_hashes()
        record['status'] = 'completed'
    except Exception as exc:
        record['status'] = 'interrupted'
        record['error_type'] = type(exc).__name__
    finally:
        record['finished_at'] = stamp()
        write_json(output / 'run.json', record)
    print(json.dumps({k: record[k] for k in ('status','schema_constraint_passed','public_window_attempted',
                                           'public_window_status','public_window_reason','loaded_model_reports') if k in record}))
    return 0 if record.get('schema_constraint_passed') and record['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
