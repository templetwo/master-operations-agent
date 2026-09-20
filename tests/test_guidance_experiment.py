import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa.guidance_experiment import ARMS, design, prompts, register, run, provider_failure_requires_stop
from moa.providers import Baseline


class ExperimentTests(unittest.TestCase):
    def test_factor_design_and_separate_preregistration(self):
        p = prompts()
        self.assertEqual(set(p), set(ARMS))
        self.assertTrue(p['both'].startswith(p['output-only']))
        self.assertTrue(p['policy-only'].startswith(p['unchanged']))
        self.assertEqual(design()['maximum_completion_calls'], 244)
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / 'registered.json'
            receipt = register(file)
            self.assertEqual(receipt['sha256'], hashlib.sha256(file.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError): register(file)

    def test_consent_hash_and_design_checked_before_credentials(self):
        with tempfile.TemporaryDirectory() as d, patch('moa.guidance_experiment.read_api_key') as key:
            file = Path(d) / 'registered.json'; receipt = register(file)
            args = ('unused', 'unused', Path(d) / 'out', file, receipt['sha256'])
            with self.assertRaises(ValueError): run(*args)
            with self.assertRaises(ValueError): run(*args[:-1], 'bad', allow_cloud_synthetic=True)
            with patch('moa.guidance_experiment.source_hashes', return_value={}):
                with self.assertRaises(ValueError): run(*args, allow_cloud_synthetic=True)
            data = json.loads(file.read_text()); data['design']['maximum_completion_calls'] = 999
            file.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                run(*args[:-1], hashlib.sha256(file.read_bytes()).hexdigest(), allow_cloud_synthetic=True)
            key.assert_not_called()

    def test_delivered_invalid_content_is_counted_transport_stops(self):
        result = {'run_id': 'r', 'reason': 'invalid_json', 'failure': {'category': 'provider_response'}}
        delivered = [{'payload': {'run_id': 'r', 'kind': 'provider_call', 'data': {
            'response_sha256': 'hash', 'reported': {'model': 'deepseek-flash'}}}}]
        self.assertFalse(provider_failure_requires_stop(result, delivered))
        self.assertTrue(provider_failure_requires_stop(result, []))
        self.assertTrue(provider_failure_requires_stop(dict(result, reason='model_changed'), delivered))
        self.assertTrue(provider_failure_requires_stop(dict(result, failure={'category': 'provider_preparation'}), []))

    def test_preparation_failure_leaves_interrupted_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); registration = folder / 'registered.json'; receipt = register(registration)
            baseline = {'passed': True, 'metrics': {}}
            control = {'passed': False, 'metrics': {'useful_assessment': {'passed': 0, 'total': 10},
                       'input_guards': {'passed': 8, 'total': 8}}}
            with patch('moa.guidance_experiment.read_api_key', return_value='fake'), \
                 patch('moa.guidance_experiment.evaluate_drills', side_effect=[baseline, control]), \
                 patch('moa.guidance_experiment.DeepSeek') as provider:
                provider.return_value.prepare.side_effect = ValueError('mocked failure')
                with self.assertRaises(ValueError):
                    run('unused', 'unused', folder / 'out', registration, receipt['sha256'], allow_cloud_synthetic=True)
            state = json.loads((folder / 'out' / 'run.json').read_text())
            self.assertEqual(state['status'], 'interrupted')
            self.assertFalse((folder / 'out' / 'comparison.json').exists())

    @unittest.skipUnless(os.environ.get('MOA_SIM_REPO'), 'Set MOA_SIM_REPO for mocked-cloud factorial integration')
    def test_interleaved_real_exports_and_mocked_provider(self):
        instances = []
        class FakeDeepSeek(Baseline):
            name = 'mocked-deepseek'
            def __init__(self, key, *, allow_cloud_synthetic):
                self.calls = 0; self.receipts = []; self.messages = []; instances.append(self)
            def prepare(self): return {'requested_model': 'deepseek-flash', 'listed': True}
            def inspect_models(self): return self.prepare()
            def respond(self, messages):
                self.calls += 1; self.messages.append(messages)
                self.receipts.append({'wall_ms': 0, 'reported': {'model': 'mock-only'}})
                return super().respond(messages)
            def drain_receipts(self):
                values, self.receipts = self.receipts, []; return values
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); reg = folder / 'registered.json'; receipt = register(reg)
            seen = []
            with patch('moa.guidance_experiment.read_api_key', return_value='not-a-real-key'), patch('moa.guidance_experiment.DeepSeek', FakeDeepSeek):
                result = run(os.environ['MOA_SIM_REPO'], 'unused', folder / 'result', reg, receipt['sha256'],
                             allow_cloud_synthetic=True, progress=lambda arm, row: seen.append((arm, row['id'])))
            self.assertTrue(result['experiment_valid'])
            self.assertEqual([i.calls for i in instances], [41] * 4)
            for index in range(18):
                expected = ARMS[index % 4:] + ARMS[:index % 4]
                self.assertEqual([arm for arm, _ in seen[index*4:index*4+4]], list(expected))
                self.assertEqual(len({case for _, case in seen[index*4:index*4+4]}), 1)
            for arm in ARMS:
                self.assertEqual(result['arms'][arm]['metrics']['useful_assessment'], {'passed': 10, 'total': 10})
            for instance in instances:
                for messages in instance.messages:
                    for m in messages:
                        if m['role'] == 'user':
                            self.assertNotIn('"expected"', m['content'])
                            self.assertNotIn('"seed"', m['content'])
                            self.assertNotIn('"scenario"', m['content'])
            with patch('moa.guidance_experiment.read_api_key') as key:
                with self.assertRaises(FileExistsError):
                    run('unused', 'unused', folder / 'result', reg, receipt['sha256'], allow_cloud_synthetic=True)
                key.assert_not_called()


if __name__ == '__main__': unittest.main()
