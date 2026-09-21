"""Local extension tests use public toy fixtures, never the private holdout."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa import holdout as sealed
from moa import local_holdout as local
from moa.comparison import AlwaysRefuse
from moa.contracts import Rejected
from moa.providers import Baseline
from test_holdout import FINDINGS, CHECKS, EVIDENCE, MATERIALIZER


class FakeOllama(Baseline):
    instances = []

    def __init__(self, model, *, expected_digest):
        self.model = model
        self.name = 'ollama:' + model
        self.expected_digest = expected_digest
        self.calls = 0
        self.receipts = []
        self.messages = []
        self.instances.append(self)

    def prepare(self):
        return copy.deepcopy(local._inventory()[self.model])

    def request(self, method, path):
        assert (method, path) == ('GET', '/api/version')
        return {'version': local.OLLAMA_VERSION}

    def respond(self, messages):
        self.calls += 1
        self.messages.append(copy.deepcopy(messages))
        self.receipts.append({'wall_ms': 0, 'response_sha256': 'public-test-response',
                              'reported': {'model': self.model, 'eval_count': 1, 'prompt_eval_count': 2,
                                           'eval_duration': 3, 'load_duration': 0}})
        return super().respond(messages)

    def drain_receipts(self):
        values, self.receipts = self.receipts, []
        return values


class LocalHoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.package = self.folder / 'package'
        (self.package / 'review').mkdir(parents=True)
        cases = [{'case_id': f'toy-private-useful-{i}', 'expected': {'status': 'usable',
                  'findings': FINDINGS, 'checks': CHECKS, 'evidence': EVIDENCE}} for i in range(24)]
        cases += [{'case_id': f'toy-private-guard-{i}', 'expected': {'status':'rejected','reason':'stale',
                   'findings': [], 'checks': [], 'evidence': []}} for i in range(6)]
        (self.package / 'cases.json').write_text(json.dumps({'cases': cases}))
        (self.package / 'materialize.py').write_text(MATERIALIZER)
        (self.package / 'review/preregistration.json').write_text('{}')
        manifest = {'files': {name: sealed.file_sha(self.package / name) for name in
                             ('cases.json','materialize.py','review/preregistration.json')}}
        (self.package / 'reviewed-manifest.json').write_text(json.dumps(manifest))
        freeze = patch.object(sealed, 'REVIEWED_SHA256', sealed.file_sha(self.package / 'reviewed-manifest.json'))
        freeze.start(); self.addCleanup(freeze.stop)
        self.registration = self.folder / 'registered.json'
        self.registered = local.register(self.registration)
        self.cloud_claim = self.package.parent / ('.campaign-' + sealed.REVIEWED_SHA256[:16] + '-' + sealed.PROMPT_SHA256[:16] + '.json')
        self.cloud_claim.write_text('ORIGINAL CLOUD CLAIM MUST REMAIN')
        FakeOllama.instances = []

    def execute(self, provider=FakeOllama):
        with patch.object(local, 'Ollama', provider):
            return local.run(self.package, self.folder/'private', self.folder/'public.json',
                             self.registration, self.registered['preregistration_sha256'])

    def test_registration_binds_fixed_models_prompt_inventory_and_protocol(self):
        data = json.loads(self.registration.read_text())
        self.assertEqual([m['model'] for m in data['design']['models']], ['qwen3:4b', 'qwen3.5:9b-q4_K_M'])
        self.assertEqual(data['design']['candidate_prompt_sha256'], sealed.PROMPT_SHA256)
        self.assertEqual(data['design']['maximum_completion_calls_per_model'], 145)
        self.assertEqual(data['design']['inventory_sha256'], sealed.file_sha(local.INVENTORY))
        self.assertEqual(data['protocol_sha256'], sealed.file_sha(local.PROTOCOL))
        self.assertNotIn('toy-private', self.registration.read_text())
        with self.assertRaises(FileExistsError): local.register(self.registration)

    def test_preflight_drift_stops_before_models_or_new_claim(self):
        args = (self.package,self.folder/'private',self.folder/'public.json',self.registration,
                self.registered['preregistration_sha256'])
        with patch.object(local, 'Ollama') as provider:
            with self.assertRaises(ValueError): local.run(*args[:-1], 'bad')
            with patch.object(local, 'source_hashes', return_value={}):
                with self.assertRaises(RuntimeError): local.run(*args)
            original = (self.package/'materialize.py').read_text()
            (self.package/'materialize.py').write_text(original + '# changed')
            with self.assertRaises(ValueError): local.run(*args)
            provider.assert_not_called()
        self.assertFalse(list(self.folder.glob('.local-comparison-*')))
        self.assertEqual(self.cloud_claim.read_text(), 'ORIGINAL CLOUD CLAIM MUST REMAIN')

    def test_cap_counts_warmup_and_failed_send_and_never_sends_attempt_146(self):
        class Rejecting(FakeOllama):
            def respond(self, messages):
                self.calls += 1
                raise Rejected('provider_error', 'mock transport failed')
        with patch.object(local, 'Ollama', Rejecting):
            provider = local.BoundedLocal(local.MODELS[0])
            for _ in range(145):
                with self.assertRaises(Rejected): provider.respond([])
            self.assertEqual(provider.calls, 145)
            with self.assertRaises(Rejected) as error: provider.respond([])
            self.assertEqual(error.exception.code, 'provider_budget')
            self.assertEqual(provider.inner.calls, 145)

    def test_classifier_keeps_confirmed_malformed_output_but_stops_transport_identity(self):
        result = {'run_id':'r','reason':'invalid_json','failure':{'category':'provider_response'}}
        events = [{'payload':{'run_id':'r','kind':'provider_call','data':{'response_sha256':'test',
                    'reported':{'model':local.MODELS[0]['model'],'done_reason':'length'}}}}]
        self.assertFalse(local.local_failure_requires_stop(result, events, local.MODELS[0]['model']))
        self.assertTrue(local.local_failure_requires_stop(result, [], local.MODELS[0]['model']))
        self.assertTrue(local.local_failure_requires_stop(result, events, local.MODELS[1]['model']))
        self.assertTrue(local.local_failure_requires_stop(dict(result,reason='model_changed'), events, local.MODELS[0]['model']))

    def test_completed_models_are_sequential_private_and_cannot_rerun(self):
        result = self.execute()
        self.assertTrue(result['completed']); self.assertTrue(result['all_candidates_primary_passed'])
        self.assertTrue(result['controls_passed']); self.assertTrue(result['shared_integrity_passed'])
        self.assertEqual([p.model for p in FakeOllama.instances], [m['model'] for m in local.MODELS])
        for spec in local.MODELS:
            report = result['candidates'][spec['id']]
            self.assertEqual(report['completion_calls_including_warmup'], 97)
            self.assertEqual(report['inference']['calls'], 96)
            self.assertEqual(report['metrics']['useful_assessment'], {'passed':24,'total':24,'observed':24})
            self.assertTrue(report['metadata_unchanged']); self.assertTrue(report['version_unchanged'])
            self.assertTrue(report['source_unchanged']); self.assertTrue(report['freeze_unchanged'])
        public = (self.folder/'public.json').read_text()
        for value in ('toy-private', 'reactor_warming', 'authored-window', 'reported_alarms', 'run_id'):
            self.assertNotIn(value, public)
        for instance in FakeOllama.instances:
            for messages in instance.messages:
                for message in messages:
                    self.assertNotIn('toy-private', message['content'])
                    self.assertNotIn('"expected"', message['content'])
        self.assertEqual(self.cloud_claim.read_text(), 'ORIGINAL CLOUD CLAIM MUST REMAIN')
        manifest = sealed._load(self.folder/'private/artifact-manifest.json')
        for relative, expected in manifest['files'].items():
            self.assertEqual(sealed.file_sha(self.folder/'private'/relative), expected)
        with self.assertRaises(FileExistsError):
            local.run(self.package,self.folder/'second-private',self.folder/'second-public',
                      self.registration,self.registered['preregistration_sha256'])

    def test_first_transport_interruption_does_not_retry_or_hide_second_model(self):
        class FirstBreaks(FakeOllama):
            def respond(self, messages):
                if self.model == local.MODELS[0]['model'] and self.calls >= 1:
                    self.calls += 1
                    self.receipts.append({'wall_ms':0,'error':'provider_error'})
                    raise Rejected('provider_error','toy-private transport details')
                return super().respond(messages)
        result = self.execute(FirstBreaks)
        self.assertFalse(result['completed']); self.assertFalse(result['all_candidates_primary_passed'])
        first, second = (result['candidates'][s['id']] for s in local.MODELS)
        self.assertFalse(first['completed']); self.assertEqual(first['completion_calls_including_warmup'], 2)
        self.assertEqual(first['metrics']['useful_assessment'], {'passed':0,'total':24,'observed':1})
        self.assertEqual(first['interrupted_phase'], 'candidate')
        self.assertTrue(second['completed']); self.assertTrue(second['primary_passed'])
        self.assertEqual(second['completion_calls_including_warmup'], 97)
        self.assertNotIn('toy-private', (self.folder/'public.json').read_text())
        self.assertEqual(self.cloud_claim.read_text(), 'ORIGINAL CLOUD CLAIM MUST REMAIN')

    def test_metadata_or_version_mismatch_prevents_inference(self):
        with patch.object(local, 'Ollama', FakeOllama):
            provider = local.BoundedLocal(local.MODELS[0])
            provider.inner.request = lambda *args: {'version':'unexpected'}
            with self.assertRaises(Rejected): provider.version()
            wrong = provider.inner.prepare(); wrong['template_sha256'] = 'different'
            provider.inner.prepare = lambda: wrong
            with self.assertRaises(Rejected): provider.prepare()
            self.assertEqual(provider.calls, 0)

    def test_final_control_chain_failure_cannot_publish_completed_pass(self):
        original = local.verify_bundle
        calls = []
        def broken_control_chain(bundle):
            calls.append(bundle)
            # Each model chain is checked first, then the control chains.
            if len(calls) == 3:
                raise ValueError('public toy control integrity failure')
            return original(bundle)
        with patch.object(local, 'verify_bundle', side_effect=broken_control_chain):
            result = self.execute()
        self.assertFalse(result['completed'])
        self.assertFalse(result['shared_integrity_passed'])
        self.assertFalse(result['all_candidates_primary_passed'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['interrupted_phase'], 'final_shared_integrity')
        self.assertTrue(all(candidate['completed'] for candidate in result['candidates'].values()))
        self.assertTrue((self.folder/'private/interruption.json').exists())

    def test_controls_fail_before_any_local_provider(self):
        with patch.object(local, 'Baseline', AlwaysRefuse), patch.object(local, 'Ollama') as provider:
            result = local.run(self.package,self.folder/'private',self.folder/'public.json',
                               self.registration,self.registered['preregistration_sha256'])
            provider.assert_not_called()
        self.assertFalse(result['completed']); self.assertFalse(result['controls_passed'])
        self.assertEqual(result['candidate_count_attempted'], 0)


if __name__ == '__main__':
    unittest.main()
