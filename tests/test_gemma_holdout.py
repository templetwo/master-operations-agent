"""Single-model study tests use only public toy cases and mocked Ollama."""

import copy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from moa import gemma_holdout as gemma
from moa import holdout as sealed
from moa import local_holdout as local
from moa.contracts import Rejected, digest
import test_local_holdout as toy


class GemmaConfigurationTests(unittest.TestCase):
    def test_default_qwen_design_is_exactly_the_archived_registration(self):
        prior = sealed._load(local.ROOT / 'receipts/v0.7-local/preregistration.json')
        self.assertEqual(local.design(), prior['design'])

    def test_single_study_is_immutable_and_does_not_swap_default_globals(self):
        original_models = copy.deepcopy(local.MODELS)
        original_protocol, original_inventory = local.PROTOCOL, local.INVENTORY
        self.assertEqual(len(gemma.STUDY.models), 1)
        self.assertEqual(gemma.STUDY.models[0].model, 'gemma4:12b-it-q4_K_M')
        with self.assertRaises(FrozenInstanceError):
            gemma.STUDY.models = ()
        with self.assertRaises(FrozenInstanceError):
            gemma.STUDY.models[0].digest = '0' * 64
        detached = gemma.STUDY.models[0].record(); detached['model'] = 'changed'
        self.assertEqual(gemma.STUDY.models[0].model, 'gemma4:12b-it-q4_K_M')
        with self.assertRaises(ValueError):
            local.LocalStudy(list(gemma.STUDY.models), original_protocol, original_inventory)
        self.assertEqual(local.MODELS, original_models)
        self.assertEqual((local.PROTOCOL, local.INVENTORY), (original_protocol, original_inventory))
        with patch.object(gemma, 'local_main', return_value=7) as execute:
            self.assertEqual(gemma.main(['register', '--output', 'unused']), 7)
            execute.assert_called_once_with(['register','--output','unused'], study=gemma.STUDY)


class GemmaToyRunTests(unittest.TestCase):
    def setUp(self):
        # Existing helper authors public window_fixture cases; no private path is
        # read. Reusing setup does not inherit or repeat its Qwen campaign tests.
        toy.LocalHoldoutTests.setUp(self)
        self.protocol = self.folder / 'gemma-protocol.md'
        self.protocol.write_text('Public toy Gemma protocol, not a real evaluation.')
        self.inventory = self.folder / 'gemma-inventory.json'
        metadata = copy.deepcopy(local._inventory()[local.MODELS[0]['model']])
        metadata.update(name=gemma.STUDY.models[0].model, digest=gemma.STUDY.models[0].digest)
        self.metadata = metadata
        self.inventory.write_text(json.dumps({'server_version': {'version': local.OLLAMA_VERSION}, 'selected_models': [metadata]}))
        self.study = replace(gemma.STUDY, protocol=self.protocol, inventory=self.inventory)
        self.gemma_registration = self.folder / 'gemma-registration.json'
        self.gemma_receipt = local.register(self.gemma_registration, study=self.study)
        legacy_identity = digest({'reviewed': sealed.REVIEWED_SHA256, 'prompt': sealed.PROMPT_SHA256, 'models': list(local.MODELS)})
        self.qwen_claim = self.folder / ('.local-comparison-' + legacy_identity[:32] + '.json')
        self.qwen_claim.write_text('Existing Qwen claim remains unchanged')

    def fake_provider(self, broken=False):
        metadata = self.metadata
        class FakeGemma(toy.FakeOllama):
            def prepare(self):
                return copy.deepcopy(metadata)
            def respond(self, messages):
                if broken and self.calls >= 1:
                    self.calls += 1
                    self.receipts.append({'wall_ms':0,'error':'provider_error'})
                    raise Rejected('provider_error', 'Public toy transport interruption')
                return super().respond(messages)
        return FakeGemma

    def execute(self, broken=False):
        with patch.object(local, 'Ollama', self.fake_provider(broken)):
            return local.run(self.package,self.folder/'gemma-private',self.folder/'gemma-public.json',
                             self.gemma_registration,self.gemma_receipt['preregistration_sha256'],study=self.study)

    def test_single_candidate_register_run_preserves_previous_claims_and_defaults(self):
        default_before = local.design()
        registered = sealed._load(self.gemma_registration)
        self.assertEqual(len(registered['design']['models']), 1)
        self.assertEqual(registered['design']['inventory_sha256'], sealed.file_sha(self.inventory))
        self.assertEqual(registered['protocol_sha256'], sealed.file_sha(self.protocol))
        self.assertEqual(registered['design']['maximum_completion_calls_per_model'], 145)
        self.assertEqual(registered['design']['candidate_prompt_sha256'], sealed.PROMPT_SHA256)
        result = self.execute()
        self.assertTrue(result['completed']); self.assertTrue(result['all_candidates_primary_passed'])
        self.assertEqual(result['candidate_count_registered'], 1)
        self.assertEqual(result['candidate_count_attempted'], 1)
        self.assertEqual(list(result['candidates']), [self.study.models[0].id])
        candidate = result['candidates'][self.study.models[0].id]
        self.assertEqual(candidate['completion_calls_including_warmup'], 97)
        self.assertEqual(candidate['metrics']['useful_assessment'], {'passed':24,'total':24,'observed':24})
        self.assertEqual(candidate['metrics']['input_guards'], {'passed':6,'total':6,'observed':6})
        self.assertEqual([p.model for p in toy.FakeOllama.instances], [self.study.models[0].model])
        self.assertEqual(local.design(), default_before)
        self.assertEqual(self.qwen_claim.read_text(), 'Existing Qwen claim remains unchanged')
        self.assertEqual(self.cloud_claim.read_text(), 'ORIGINAL CLOUD CLAIM MUST REMAIN')
        public = (self.folder/'gemma-public.json').read_text()
        for value in ('toy-private','reactor_warming','authored-window','reported_alarms','run_id'):
            self.assertNotIn(value, public)
        with self.assertRaises(FileExistsError):
            local.run(self.package,self.folder/'retry-private',self.folder/'retry-public',
                      self.gemma_registration,self.gemma_receipt['preregistration_sha256'],study=self.study)

    def test_single_model_interruption_has_no_alternate_or_retry(self):
        result = self.execute(broken=True)
        self.assertFalse(result['completed']); self.assertFalse(result['all_candidates_primary_passed'])
        self.assertEqual(result['candidate_count_attempted'], 1)
        report = result['candidates'][self.study.models[0].id]
        self.assertEqual(report['completion_calls_including_warmup'], 2)
        self.assertEqual(report['metrics']['useful_assessment'], {'passed':0,'total':24,'observed':1})
        self.assertEqual(len(toy.FakeOllama.instances), 1)
        self.assertTrue((self.folder/'gemma-private'/self.study.models[0].id/'attempts/000.result.json').exists())

    def test_study_specific_inventory_protocol_source_and_wrong_study_block_before_inference(self):
        args = (self.package,self.folder/'gemma-private',self.folder/'gemma-public.json',
                self.gemma_registration,self.gemma_receipt['preregistration_sha256'])
        with patch.object(local, 'Ollama') as provider:
            with self.assertRaises(ValueError): local.run(*args)
            with patch.object(local, 'source_hashes', return_value={}):
                with self.assertRaises(RuntimeError): local.run(*args, study=self.study)
            original_protocol = self.protocol.read_text()
            self.protocol.write_text(original_protocol + ' changed')
            with self.assertRaises(RuntimeError): local.run(*args, study=self.study)
            self.protocol.write_text(original_protocol)
            self.inventory.write_text(self.inventory.read_text()+'\n')
            with self.assertRaises(ValueError): local.run(*args, study=self.study)
            provider.assert_not_called()
        self.assertEqual(len(list(self.folder.glob('.local-comparison-*'))), 1)


if __name__ == '__main__':
    unittest.main()
