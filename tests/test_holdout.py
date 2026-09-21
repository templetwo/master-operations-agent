"""Public toy fixtures only. Never opens the private reviewed holdout."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa import holdout
from moa.contracts import Rejected
from moa.providers import Baseline

FINDINGS = ['reported_alarms','reactor_warming','jacket_warming','coolant_output_high',
            'cooling_path_unconfirmed','cause_unresolved']
CHECKS = ['inspect_alarm_context','compare_independent_measurement','review_cooling_evidence']
EVIDENCE = ['snapshot:alarms','policy:lab-v2'] + ['history:' + tag for tag in ('TIC201','TIC202','FIC102','LIC101','TIC202.OP')]
MATERIALIZER = '''from datetime import timedelta
from moa.fixtures import window_fixture
def materialize(case_id, now):
    return window_fixture(now=now-timedelta(seconds=61) if case_id.startswith('toy-private-guard') else now)
'''


class FakeDeepSeek(Baseline):
    name = 'public-test-double'
    instances = []

    def __init__(self, key, *, allow_cloud_synthetic, max_calls):
        assert allow_cloud_synthetic is True and max_calls == 145
        self.calls = 0
        self.receipts = []
        self.messages = []
        self.instances.append(self)

    def prepare(self):
        return {'requested_model': 'deepseek-flash', 'maximum_inference_calls': 145,
                'settings': {k: v for k, v in holdout.SETTINGS.items() if k != 'model'}}

    def inspect_models(self):
        return {'listed': True}

    def drain_receipts(self):
        values, self.receipts = self.receipts, []
        return values

    def respond(self, messages):
        self.calls += 1
        self.messages.append(copy.deepcopy(messages))
        self.receipts.append({'wall_ms': 0, 'response_sha256': 'public-test-response',
                              'reported': {'model': 'deepseek-flash'}})
        return super().respond(messages)


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.package = self.folder / 'package'
        self.package.mkdir()
        (self.package / 'review').mkdir()
        cases = [{'case_id': f'toy-private-useful-{index}', 'expected': {'status':'usable',
                  'findings': FINDINGS, 'checks': CHECKS, 'evidence': EVIDENCE}} for index in range(24)]
        cases += [{'case_id': f'toy-private-guard-{index}', 'expected': {'status':'rejected','reason':'stale',
                   'findings': [], 'checks': [], 'evidence': []}} for index in range(6)]
        self.cases = cases
        (self.package / 'cases.json').write_text(json.dumps({'cases': cases}))
        (self.package / 'materialize.py').write_text(MATERIALIZER)
        (self.package / 'review/preregistration.json').write_text('{}')
        self.freeze()
        self.registration = self.folder / 'registered.json'
        self.registered = holdout.register(self.registration)
        FakeDeepSeek.instances = []

    def freeze(self):
        manifest = {'files': {name: holdout.file_sha(self.package / name) for name in
                             ('cases.json','materialize.py','review/preregistration.json')}}
        (self.package / 'reviewed-manifest.json').write_text(json.dumps(manifest))
        self.manifest_patch = patch.object(holdout, 'REVIEWED_SHA256', holdout.file_sha(self.package / 'reviewed-manifest.json'))
        self.manifest_patch.start()
        self.addCleanup(self.manifest_patch.stop)

    def execute(self, provider=FakeDeepSeek):
        with patch.object(holdout, 'DeepSeek', provider), patch.object(holdout, 'read_api_key', return_value='never-published-test-key'):
            return holdout.run(self.package, 'not-opened.env', self.folder/'private', self.folder/'public.json',
                               self.registration, self.registered['preregistration_sha256'], allow_cloud_synthetic=True)

    def test_registration_is_public_separate_and_refuses_overwrite(self):
        data = json.loads(self.registration.read_text())
        self.assertEqual(data['design']['counts'], {'usable':24,'guards':6,'total':30})
        self.assertEqual(data['design']['maximum_completion_calls'], 145)
        self.assertEqual(data['protocol_sha256'], holdout.file_sha(holdout.PROTOCOL))
        self.assertNotIn('toy-private', self.registration.read_text())
        with self.assertRaises(FileExistsError):
            holdout.register(self.registration)

    def test_exact_v06_prompt_is_pinned(self):
        self.assertEqual(holdout.design()['system_prompt_sha256'], holdout.PROMPT_SHA256)
        with patch.object(holdout, 'prompts', return_value={'policy-only':'altered'}):
            with self.assertRaises(ValueError):
                holdout.design()

    def test_consent_source_and_registration_fail_before_credentials_or_claim(self):
        args = (self.package, 'unused', self.folder/'private', self.folder/'public.json', self.registration,
                self.registered['preregistration_sha256'])
        with patch.object(holdout, 'read_api_key') as key:
            with self.assertRaises(ValueError): holdout.run(*args)
            with self.assertRaises(ValueError): holdout.run(*args[:-1], 'bad', allow_cloud_synthetic=True)
            with patch.object(holdout, 'source_hashes', return_value={}):
                with self.assertRaises(ValueError): holdout.run(*args, allow_cloud_synthetic=True)
            key.assert_not_called()
        self.assertFalse(list(self.folder.glob('.campaign-*')))

    def test_freeze_tamper_extra_files_and_symlinks_rejected(self):
        self.assertEqual(len(holdout.verify_package(self.package)['cases']), 30)
        materializer = self.package/'materialize.py'
        original = materializer.read_text()
        materializer.write_text(original+'# changed\n')
        with self.assertRaises(ValueError): holdout.verify_package(self.package)
        materializer.write_text(original)
        extra = self.package/'extra.json'; extra.write_text('{}')
        with self.assertRaises(ValueError): holdout.verify_package(self.package)
        extra.unlink()
        extra.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(ValueError): holdout.verify_package(self.package)
        extra.unlink()
        materializer.unlink(); materializer.symlink_to(self.registration)
        with self.assertRaises(ValueError): holdout.verify_package(self.package)

    def test_completed_toy_campaign_keeps_all_case_evidence_private(self):
        summary = self.execute()
        self.assertTrue(summary['completed'])
        self.assertTrue(summary['primary_passed'])
        self.assertTrue(summary['secondary_passed'])
        self.assertTrue(summary['controls_passed'])
        self.assertTrue(summary['source_unchanged'])
        self.assertTrue(summary['freeze_unchanged'])
        self.assertLessEqual(summary['started_at'], summary['finished_at'])
        self.assertEqual(json.loads((self.folder/'private/run-start.json').read_text())['started_at'], summary['started_at'])
        metrics = summary['reports']['candidate']
        self.assertEqual(metrics['useful_assessment'], {'passed':24,'total':24,'observed':24})
        self.assertEqual(metrics['input_guards'], {'passed':6,'total':6,'observed':6})
        self.assertEqual(metrics['required_reads']['passed'], 24)
        self.assertEqual(metrics['identifiers']['findings']['micro_precision'], 1)
        self.assertEqual(metrics['released_evidence_fidelity']['fraction'], 1)
        self.assertEqual(summary['completion_calls_including_warmup'], 97)
        self.assertEqual(metrics['latency_ms']['useful_accepted']['count'], 24)
        public = (self.folder/'public.json').read_text()
        for forbidden in ('toy-private', 'never-published-test-key', 'authored-window', 'reactor_warming', 'reported_alarms', 'run_id'):
            self.assertNotIn(forbidden, public)
        self.assertTrue((self.folder/'private/case-order.json').exists())
        self.assertEqual(len(list((self.folder/'private/candidate').glob('*.input.json'))), 30)
        artifact = json.loads((self.folder/'private/artifact-manifest.json').read_text())
        for relative, checksum in artifact['files'].items():
            self.assertEqual(holdout.file_sha(self.folder/'private'/relative), checksum)
        for messages in FakeDeepSeek.instances[0].messages:
            for message in messages:
                self.assertNotIn('toy-private', message['content'])
                self.assertNotIn('"expected"', message['content'])
        self.assertEqual((self.folder/'private').stat().st_mode & 0o777, 0o700)
        with self.assertRaises(FileExistsError):
            with patch.object(holdout, 'read_api_key') as key:
                holdout.run(self.package,'unused',self.folder/'second-private',self.folder/'second-public',
                            self.registration,self.registered['preregistration_sha256'],allow_cloud_synthetic=True)
                key.assert_not_called()

    def test_control_disagreement_stops_before_key_or_model(self):
        with patch.object(holdout, 'Baseline', holdout.AlwaysRefuse), patch.object(holdout, 'read_api_key') as key, patch.object(holdout, 'DeepSeek') as provider:
            result = holdout.run(self.package,'unused',self.folder/'private',self.folder/'public.json',
                                 self.registration,self.registered['preregistration_sha256'],allow_cloud_synthetic=True)
        self.assertFalse(result['completed']); self.assertFalse(result['primary_passed'])
        self.assertFalse(result['controls_passed'])
        self.assertEqual(result['interrupted_phase'], 'baseline')
        self.assertIsNone(result['source_unchanged'])
        self.assertIsNone(result['freeze_unchanged'])
        self.assertEqual(result['reports']['candidate']['observed_total'], 0)
        self.assertIsNone(result['reports']['candidate']['released_evidence_fidelity']['fraction'])
        key.assert_not_called(); provider.assert_not_called()
        self.assertEqual(len(list(self.folder.glob('.campaign-*'))), 1)

    def test_provider_failure_retains_attempt_and_reports_incomplete_not_pass(self):
        class Broken(FakeDeepSeek):
            def respond(self, messages):
                if self.calls >= 1:
                    raise Rejected('provider_http_error', 'toy-private message must never be public')
                return super().respond(messages)
        result = self.execute(Broken)
        self.assertFalse(result['completed']); self.assertFalse(result['primary_passed'])
        self.assertEqual(result['interrupted_phase'], 'candidate')
        self.assertEqual(result['reports']['candidate']['observed_total'], 1)
        self.assertEqual(result['reports']['candidate']['useful_assessment']['total'], 24)
        self.assertEqual(result['reports']['candidate']['failure_categories'], {'provider_response':1})
        self.assertTrue((self.folder/'private/candidate/000.input.json').exists())
        self.assertTrue((self.folder/'private/candidate/000.result.json').exists())
        self.assertNotIn('toy-private', (self.folder/'public.json').read_text())

    def test_delivered_malformed_first_answer_is_counted_without_retry(self):
        class BadContent(FakeDeepSeek):
            def respond(self, messages):
                answer = super().respond(messages)
                if answer['kind'] == 'advice':
                    answer['unexpected'] = 'toy-private-hidden-text'
                return answer
        result = self.execute(BadContent)
        self.assertTrue(result['completed']); self.assertFalse(result['primary_passed'])
        metric = result['reports']['candidate']
        self.assertEqual(metric['useful_assessment']['passed'], 0)
        self.assertEqual(metric['failure_categories']['candidate_shape'], 24)
        self.assertEqual(metric['identifiers']['findings']['exact_sets'], 24)
        self.assertEqual(metric['exact_advice_envelopes'], 0)
        self.assertEqual(metric['latency_ms']['withheld_usable']['count'], 24)
        self.assertEqual(result['completion_calls_including_warmup'], 97)
        self.assertNotIn('toy-private', (self.folder/'public.json').read_text())

    def test_empty_diagnostic_denominators_are_undefined(self):
        summary = holdout.aggregate([])
        self.assertEqual(summary['useful_assessment']['total'], 24)
        for field in ('findings','checks','evidence'):
            self.assertIsNone(summary['identifiers'][field]['micro_precision'])
            self.assertIsNone(summary['identifiers'][field]['micro_recall'])
        self.assertIsNone(summary['latency_ms']['useful_accepted']['median'])


if __name__ == '__main__':
    unittest.main()
