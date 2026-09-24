"""Public diagnostic tests. No daemon requests or private-corpus reads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa.providers import Ollama, wire_json

spec = importlib.util.spec_from_file_location('timing', Path(__file__).resolve().parents[1] / 'scripts/probe_warmup_timing.py')
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


class WarmupTimingTests(unittest.TestCase):
    def test_request_bytes_match_unchanged_production_provider(self):
        provider = Ollama(timing.MODEL, expected_digest=timing.DIGEST)
        provider.receipt = {'digest': timing.DIGEST}
        request = timing.body()
        response = {'model': timing.MODEL, 'done': True, 'done_reason': 'stop',
                    'message': {'content': '{"kind":"tool","name":"read_snapshot","arguments":{}}'}}
        with patch.object(provider, 'request', return_value=response) as send:
            provider.respond(request['messages'])
        method, path, actual = send.call_args.args
        self.assertEqual((method, path), ('POST', '/api/chat'))
        self.assertEqual(wire_json(actual), wire_json(request))

    def test_no_timeout_recommendation_from_missing_or_failed_samples(self):
        rows = [{'state': state, 'wall_ms': 25000 if state == 'unloaded' else 1000,
                 'valid_first_read': True} for _ in range(3) for state in ('unloaded', 'loaded')]
        self.assertEqual(timing.recommendation(rows, True)['proposed_warmup_timeout_s'], 60)
        self.assertIsNone(timing.recommendation(rows[:-1], True)['proposed_warmup_timeout_s'])
        self.assertIsNone(timing.recommendation(rows, False)['proposed_warmup_timeout_s'])
        rows[-1]['valid_first_read'] = False
        self.assertIsNone(timing.recommendation(rows, True)['proposed_warmup_timeout_s'])

    def test_loaded_latency_can_disqualify_longer_warmup(self):
        rows = [{'state': state, 'wall_ms': 55000 if state == 'unloaded' else 21000,
                 'valid_first_read': True} for _ in range(3) for state in ('unloaded', 'loaded')]
        result = timing.recommendation(rows, True)
        self.assertEqual(result['status'], 'longer_warmup_alone_not_supported')
        self.assertIsNone(result['proposed_warmup_timeout_s'])

    def test_other_loaded_model_is_not_unloaded(self):
        class Provider:
            def request(self, method, path):
                self.assertion = (method, path)
                return {'models': [{'name': 'another:local', 'digest': '0'*64}]}
        provider = Provider()
        with self.assertRaises(RuntimeError):
            timing.loaded(provider)
        self.assertEqual(provider.assertion, ('GET', '/api/ps'))

    def test_timeout_is_preserved_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(timing.http.client, 'HTTPConnection') as factory:
                connection = factory.return_value
                connection.getresponse.side_effect = TimeoutError('public test')
                result = timing.completion(Path(tmp), 'unloaded')
            self.assertEqual(connection.request.call_count, 1)
            connection.close.assert_called_once()
            self.assertFalse(result['valid_first_read'])
            self.assertEqual(result['error_type'], 'TimeoutError')
            self.assertTrue((Path(tmp)/'result.json').exists())
            self.assertFalse((Path(tmp)/'response.txt').exists())

    def test_disappearing_registered_input_still_finalizes_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            registration = Path(tmp)/'registered.json'
            registration.write_text(json.dumps({'design': {'public': 'toy'}}))
            output = Path(tmp)/'run'
            with patch.object(timing, 'design', side_effect=[{'public':'toy'}, FileNotFoundError(), FileNotFoundError()]):
                with patch.object(timing, 'Ollama') as provider:
                    result = timing.run(registration, timing.sha(registration), output)
            provider.return_value.request.assert_not_called()
            self.assertEqual(result['completion_attempts'], 0)
            self.assertFalse(result['source_unchanged'])
            self.assertEqual(result['status'], 'interrupted')
            self.assertEqual(json.loads((output/'run.json').read_text())['recommendation']['status'], 'inconclusive')


if __name__ == '__main__':
    unittest.main()
