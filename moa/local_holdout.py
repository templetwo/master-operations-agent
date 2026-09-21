"""Registered local comparative extension. Private case data never goes public."""

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

from . import holdout as sealed
from .comparison import AlwaysRefuse, ROOT, inference_metrics, source_hashes
from .contracts import Rejected, canonical, digest, now_utc, stamp
from .diagnostics import verify_bundle
from .engine import Agent, ENTRY
from .evidence import EvidenceStore
from .guidance_experiment import prompts
from .providers import Baseline, Ollama, RESPONSE_SCHEMA, wire_json

MODELS = (
    {'id': 'qwen3-4b', 'model': 'qwen3:4b', 'digest': '359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'},
    {'id': 'qwen35-9b', 'model': 'qwen3.5:9b-q4_K_M', 'digest': '6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7'},
)
OLLAMA_VERSION = '0.32.6'
SETTINGS = {'temperature': 0, 'seed': 0, 'num_predict': 768, 'num_ctx': 8192}
MAX_CALLS = 145
PROTOCOL = ROOT / 'docs' / 'local-holdout-v0.7.md'
INVENTORY = ROOT / 'receipts' / 'v0.7-local' / 'inventory.json'


def _inventory():
    value = sealed._load(INVENTORY)
    rows = value.get('selected_models', [])
    if (value.get('server_version') != {'version': OLLAMA_VERSION}
            or [(r.get('name'), r.get('digest')) for r in rows] != [(m['model'], m['digest']) for m in MODELS]):
        raise ValueError('Public inventory differs from registered model identities.')
    return {row['name']: row for row in rows}


def design():
    base = sealed.design()
    inventory = _inventory()
    return {'schema': 'moa-local-holdout-extension-design-v1',
            'reviewed_manifest_sha256': sealed.REVIEWED_SHA256,
            'candidate_prompt_sha256': sealed.PROMPT_SHA256, 'entry_sha256': digest(ENTRY),
            'policy_sha256': base['policy_sha256'], 'models': list(MODELS), 'ollama_version': OLLAMA_VERSION,
            'inventory_sha256': sealed.file_sha(INVENTORY),
            'approved_metadata_sha256': {model: digest(metadata) for model, metadata in inventory.items()},
            'endpoint': 'http://127.0.0.1:11434', 'settings': SETTINGS,
            'think': False, 'stream': False, 'keep_alive': '5m', 'socket_timeout_s': 20,
            'freshness_s': 60, 'maximum_completion_calls_per_model': MAX_CALLS, 'warmup_calls_per_model': 1,
            'response_schema_sha256': digest(RESPONSE_SCHEMA),
            'response_schema_wire_sha256': hashlib.sha256(wire_json(RESPONSE_SCHEMA)).hexdigest(),
            'counts_per_model': sealed.COUNTS, 'repetitions': 1,
            'order': 'Baseline, always-refuse, then the listed models sequentially; frozen private case order.',
            'primary': base['primary'], 'secondary': base['secondary'],
            'controls': 'Both controls must pass before any model request. Stop on baseline or negative-control disagreement without label repair.',
            'interruption': 'Infrastructure interruption stops that model. The second registered model may proceed once, after independent preflight and shared source/freeze rechecks. No first-model retry.',
            'warmup': 'One public protocol warmup, no private observation. Warmup failure ends that model before scored cases.',
            'limits': ['New comparative extension after a cloud campaign, not a new unseen dataset.',
                       'Runner author reviewed corpus; executing evaluator has prior cloud-case exposure. No tuning from that exposure is authorized.',
                       'Local schema-constrained output differs from cloud JSON-object mode. Fixed order and shared machine allow cache/load/order effects.',
                       'Loopback daemon isolation is operator responsibility. Small synthetic policy/contract evaluation, not plant readiness or general capability.']}


def register(path):
    sealed._new_json(path, {'registered_at': stamp(), 'design': design(), 'source_sha256': source_hashes(),
                            'protocol_sha256': sealed.file_sha(PROTOCOL)}, private=False)
    return {'preregistration_sha256': sealed.file_sha(path)}


class BoundedLocal:
    """Call cap around unchanged Ollama transport, schema and sampling behavior."""
    def __init__(self, spec):
        self.spec = spec
        self.inner = Ollama(spec['model'], expected_digest=spec['digest'])
        self.name = self.inner.name
        self.calls = 0

    def prepare(self):
        metadata = self.inner.prepare()
        required = {'name': self.spec['model'], 'digest': self.spec['digest'], 'settings': SETTINGS,
                    'think': False, 'stream': False, 'keep_alive': '5m', 'socket_timeout_s': 20,
                    'endpoint': 'http://127.0.0.1:11434', 'response_schema_sha256': digest(RESPONSE_SCHEMA),
                    'response_schema_wire_sha256': hashlib.sha256(wire_json(RESPONSE_SCHEMA)).hexdigest()}
        if any(metadata.get(key) != value for key, value in required.items()):
            raise Rejected('provider_error', 'Local preparation differs from registration.')
        if metadata != _inventory()[self.spec['model']]:
            raise Rejected('model_changed', 'Local metadata differs from the approved preflight inventory.')
        return metadata

    def version(self):
        value = self.inner.request('GET', '/api/version')
        if not isinstance(value, dict) or value.get('version') != OLLAMA_VERSION:
            raise Rejected('provider_error', 'Ollama version differs from registration.')
        return value

    def respond(self, messages):
        if self.calls >= MAX_CALLS:
            raise Rejected('provider_budget', 'Registered local completion cap exhausted.')
        self.calls += 1
        return self.inner.respond(messages)

    def drain_receipts(self):
        return self.inner.drain_receipts()


def local_failure_requires_stop(result, events, model):
    category = result.get('failure', {}).get('category')
    if category == 'provider_preparation' or result['reason'] in {'model_changed','model_unavailable','scope','provider_budget'}:
        return True
    if category != 'provider_response':
        return False
    calls = [e['payload']['data'] for e in events
             if e['payload']['kind'] == 'provider_call' and e['payload']['run_id'] == result['run_id']]
    # A received object from the expected model can be truncated or invalid JSON.
    # Keep that failed first attempt. Missing response identity is infrastructure.
    return not (calls and calls[-1].get('response_sha256')
                and calls[-1].get('reported', {}).get('model') == model)


def _candidate_phase(provider, cases, materialize, folder):
    folder.mkdir(mode=0o700)
    store = EvidenceStore(folder / 'evidence.sqlite3')
    try:
        agent = Agent(store, provider, clock=now_utc, system_prompt=prompts()['policy-only'])
        for index, case in enumerate(cases):
            observation = materialize(case['case_id'], now=now_utc())
            sealed._new_json(folder / f'{index:03d}.input.json', {'id': case['case_id'], 'observation': observation})
            result = agent.assess(observation)
            events = [e for e in store.export() if e['payload']['run_id'] == result['run_id']]
            sealed._new_json(folder / f'{index:03d}.result.json', sealed._score(case, observation, result, events))
            if local_failure_requires_stop(result, events, provider.spec['model']):
                raise RuntimeError('Local infrastructure interrupted this candidate.')
    finally:
        try:
            sealed._new_json(folder / 'evidence.json', store.bundle())
        finally:
            store.close()


def _shared_integrity(package, registration):
    sealed.verify_package(package)
    if (source_hashes() != registration['source_sha256'] or sealed.file_sha(PROTOCOL) != registration['protocol_sha256']
            or sealed.file_sha(INVENTORY) != registration['design']['inventory_sha256']):
        raise RuntimeError('Registered source or protocol changed.')


def _result(metrics, completed):
    primary = (completed and metrics['observed_total'] == sealed.COUNTS['total']
               and metrics['useful_assessment']['passed'] == sealed.COUNTS['usable']
               and metrics['input_guards']['passed'] == sealed.COUNTS['guards'] and metrics['unexpected_guard_advisories'] == 0)
    secondary = (completed and metrics['required_reads']['passed'] == sealed.COUNTS['usable']
                 and all(v['exact_sets'] == sealed.COUNTS['usable'] and v['unsupported_released'] == 0 for v in metrics['identifiers'].values())
                 and metrics['released_evidence_fidelity']['fraction'] == 1.0)
    return primary, secondary


def _run_candidate(spec, cases, materialize, private, package, registration):
    folder = private / spec['id']
    folder.mkdir(mode=0o700)
    started = stamp()
    sealed._new_json(folder / 'run-start.json', {'started_at': started, 'model': spec, 'maximum_completion_calls': MAX_CALLS})
    completed = False
    phase = 'preflight'
    provider = None
    metadata_unchanged = version_unchanged = source_unchanged = freeze_unchanged = None
    try:
        _shared_integrity(package, registration)
        provider = BoundedLocal(spec)
        version_before = provider.version()
        metadata_before = provider.prepare()
        sealed._new_json(folder / 'provider-before.json', {'version': version_before, 'metadata': metadata_before})
        phase = 'warmup'
        warmup = {'purpose': 'One public protocol warmup, no private observations.'}
        try:
            warmup['response'] = provider.respond([{'role': 'system', 'content': prompts()['policy-only']},
                                                  {'role': 'user', 'content': canonical(ENTRY)}])
        finally:
            warmup['calls'] = provider.drain_receipts()
            sealed._new_json(folder / 'warmup.json', warmup)
        phase = 'candidate'
        _candidate_phase(provider, cases, materialize, folder / 'attempts')
        phase = 'final_integrity'
        metadata_after = provider.prepare()
        version_after = provider.version()
        sealed._new_json(folder / 'provider-after.json', {'version': version_after, 'metadata': metadata_after})
        metadata_unchanged, version_unchanged = metadata_before == metadata_after, version_before == version_after
        if not metadata_unchanged or not version_unchanged:
            raise RuntimeError('Local model metadata or daemon changed during candidate.')
        freeze_unchanged = False
        sealed.verify_package(package)
        freeze_unchanged = True
        source_unchanged = (source_hashes() == registration['source_sha256']
                            and sealed.file_sha(PROTOCOL) == registration['protocol_sha256']
                            and sealed.file_sha(INVENTORY) == registration['design']['inventory_sha256'])
        if not source_unchanged:
            raise RuntimeError('Registered source changed during candidate.')
        verify_bundle(sealed._load(folder / 'attempts/evidence.json'))
        completed = True
    except Exception as exc:
        sealed._new_json(folder / 'interruption.json', {'phase': phase, 'at': stamp(), 'type': type(exc).__name__})
    metrics = sealed.aggregate(sealed._phase_rows(folder, 'attempts'))
    primary, secondary = _result(metrics, completed)
    evidence_path = folder / 'attempts/evidence.json'
    evidence = sealed._load(evidence_path) if evidence_path.exists() else {'events': []}
    result = {'model': spec['model'], 'digest': spec['digest'], 'started_at': started, 'finished_at': stamp(),
              'completed': completed, 'status': 'completed' if completed else 'incomplete',
              'interrupted_phase': phase if not completed else None, 'primary_passed': primary, 'secondary_passed': secondary,
              'metadata_unchanged': metadata_unchanged, 'version_unchanged': version_unchanged,
              'source_unchanged': source_unchanged, 'freeze_unchanged': freeze_unchanged,
              'completion_calls_including_warmup': provider.calls if provider else 0,
              'metrics': metrics, 'inference': inference_metrics({'evidence': evidence})}
    sealed._new_json(folder / 'aggregate.json', result)
    return result


def run(package, private_output, public_output, preregistration, expected_sha256):
    if sealed.file_sha(preregistration) != expected_sha256:
        raise ValueError('Local preregistration hash mismatch.')
    registration = sealed._load(preregistration)
    if registration.get('design') != design():
        raise ValueError('Local registered design differs.')
    package = Path(package).resolve()
    _shared_integrity(package, registration)
    corpus = sealed.verify_package(package)
    private = sealed._private_path(private_output, package)
    public_output = Path(public_output).resolve()
    if public_output.exists() or public_output.is_relative_to(package) or public_output.is_relative_to(private):
        raise ValueError('Public local aggregate requires a new path outside private outputs.')
    # This is a distinct explicitly registered extension. Never touch cloud claim.
    identity = digest({'reviewed': sealed.REVIEWED_SHA256, 'prompt': sealed.PROMPT_SHA256, 'models': list(MODELS)})
    claim = package.parent / ('.local-comparison-' + identity[:32] + '.json')
    started_at = stamp()
    sealed._new_json(claim, {'preregistration_sha256': expected_sha256, 'started_at': started_at, 'private_output': str(private)})
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    private.chmod(0o700)
    sealed._new_json(private / 'run-start.json', {'started_at': started_at, 'preregistration_sha256': expected_sha256})
    sealed._new_json(private / 'preregistration.json', registration)
    sealed._new_json(private / 'case-order.json', [c['case_id'] for c in corpus['cases']])
    controls, candidates = {}, {}
    controls_passed = False
    shared_integrity = False
    phase = 'materializer_setup'
    try:
        materialize = runpy.run_path(str(package / 'materialize.py'))['materialize']
        for label, provider in [('baseline', Baseline()), ('always-refuse', AlwaysRefuse())]:
            phase = label
            controls[label] = sealed._assess_phase(label, provider, corpus['cases'], materialize, private)
            if label == 'baseline' and not all(r['passed'] for r in controls[label]):
                raise RuntimeError('Independent baseline labels disagree.')
        controls_passed = sealed._controls_pass(controls)
        if not controls_passed:
            raise RuntimeError('Control prerequisites failed.')
        for spec in MODELS:
            phase = 'shared_integrity'
            _shared_integrity(package, registration)
            phase = spec['id']
            candidates[spec['id']] = _run_candidate(spec, corpus['cases'], materialize, private, package, registration)
        phase = 'final_shared_integrity'
        _shared_integrity(package, registration)
        for label in controls:
            verify_bundle(sealed._load(private / label / 'evidence.json'))
        shared_integrity = True
    except Exception as exc:
        shared_integrity = False
        sealed._new_json(private / 'interruption.json', {'phase': phase, 'type': type(exc).__name__, 'at': stamp()})
    completed = controls_passed and shared_integrity and len(candidates) == len(MODELS) and all(r['completed'] for r in candidates.values())
    summary = {'schema': 'moa-local-holdout-extension-aggregate-v1', 'started_at': started_at, 'finished_at': stamp(),
               'completed': completed, 'status': 'completed' if completed else 'incomplete',
               'interrupted_phase': phase if not shared_integrity else None,
               'controls_passed': controls_passed, 'shared_integrity_passed': shared_integrity,
               'all_candidates_primary_passed': completed and all(r['primary_passed'] for r in candidates.values()),
               'candidate_count_registered': len(MODELS), 'candidate_count_attempted': len(candidates),
               'candidates': candidates,
               'controls': {label: sealed.aggregate(sealed._phase_rows(private, label)) for label in ('baseline','always-refuse')},
               'preregistration_sha256': expected_sha256, 'reviewed_manifest_sha256': sealed.REVIEWED_SHA256,
               'candidate_prompt_sha256': sealed.PROMPT_SHA256, 'ollama_version_registered': OLLAMA_VERSION,
               'promotion': 'not_authorized', 'limits': design()['limits']}
    sealed._new_json(private / 'aggregate.json', summary)
    sealed._new_json(private / 'artifact-manifest.json', {'files': {str(p.relative_to(private)): sealed.file_sha(p)
                    for p in sorted(private.rglob('*')) if p.is_file()}})
    summary['private_artifact_manifest_sha256'] = sealed.file_sha(private / 'artifact-manifest.json')
    sealed._new_json(public_output, summary, private=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    reg = sub.add_parser('register'); reg.add_argument('--output', required=True)
    execute = sub.add_parser('run')
    for name in ('package','private-output','public-output','preregistration','expected-sha256'):
        execute.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        result = register(args.output) if args.command == 'register' else run(
            args.package, args.private_output, args.public_output, args.preregistration, args.expected_sha256)
        print(json.dumps(result, allow_nan=False))
        return 0 if args.command == 'register' or result['all_candidates_primary_passed'] else 1
    except Exception:
        print('Local holdout preflight or persistence failed. No passing comparison reported.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
