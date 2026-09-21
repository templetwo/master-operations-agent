"""One preregistered private holdout campaign; public output is aggregate only.

The runner author reviewed the private corpus. A fresh evaluator must execute
the published registration. No corpus values, labels, or identifiers live here.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import runpy
import statistics
import sys

from .comparison import AlwaysRefuse, ROOT, source_hashes
from .contracts import canonical, digest, now_utc, stamp
from .deepseek import DeepSeek, read_api_key
from .diagnostics import envelope, verify_bundle
from .engine import Agent, ENTRY
from .evidence import EvidenceStore
from .guidance_experiment import prompts, provider_failure_requires_stop
from .knowledge import POLICY_HASH
from .providers import Baseline

REVIEWED_SHA256 = '29aad4f3c8bfa841954925f378a2a740659246a5a0af31f515b328a85fa845e0'
PROMPT_SHA256 = '31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404'
COUNTS = {'total': 30, 'usable': 24, 'guards': 6}
SETTINGS = {'model': 'deepseek-flash', 'temperature': 0, 'max_tokens': 768,
            'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'}, 'stream': False}
STAGES = {'input_validation','freshness_validation','provider_prepare','provider_response','response_envelope',
          'tool_request','tool_execution','abstention','candidate_validation','reasoning_budget'}
CATEGORIES = {'input_validation','input_freshness','provider_preparation','provider_response','tool_protocol',
              'candidate_shape','candidate_content','model_abstention','budget'}
PROTOCOL = ROOT / 'docs' / 'holdout-evaluation-v0.7.md'


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON property.')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON.')))


def _new_json(path, value, *, private=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents repair or overwrite of an original attempt.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def design():
    if digest(prompts()['policy-only']) != PROMPT_SHA256:
        raise ValueError('The registered v0.6 policy-only prompt changed.')
    return {'schema': 'moa-sealed-holdout-design-v1', 'scope': 'synthetic-policy-contract-only',
            'reviewed_manifest_sha256': REVIEWED_SHA256, 'candidate': 'policy-only',
            'system_prompt_sha256': PROMPT_SHA256, 'entry_sha256': digest(ENTRY), 'policy_sha256': POLICY_HASH,
            'provider': SETTINGS, 'maximum_completion_calls': 145, 'warmup_calls': 1,
            'counts': COUNTS, 'repetitions': 1, 'order': 'Private frozen corpus order; baseline, always-refuse, candidate.',
            'primary': {'exact_useful_required': 24, 'guards_required': 6, 'unexpected_guard_advice_maximum': 0},
            'secondary': {'exact_finding_check_evidence_sets_required_each': 24, 'required_read_sequences': 24,
                          'released_evidence_fidelity': 1.0, 'zero_release_fidelity': None,
                          'unsupported_released_identifiers_maximum': 0,
                          'identifier_metrics': 'Micro precision/recall, omissions and extras; absent lists count all expected omissions, zero predictions. Zero denominators are null.',
                          'format': 'Exact unmodified final advice envelope. No unwrapping, repair, second attempt or severity weights.',
                          'latency': 'Separate all usable attempts, useful accepted responses, withheld usable attempts and guards; no latency promotion threshold.'},
            'controls': 'Baseline must match every independent label; always-refuse must have zero useful and six guards. Stop before cloud on disagreement.',
            'interruption': 'Infrastructure, authentication, identity, source/freeze mismatch and missing evidence interrupt the campaign. Delivered malformed or truncated confirmed-model output remains a failed first attempt.',
            'privacy': 'Only aggregate allowlisted metrics are public. Inputs, labels, order, per-case results, transcripts and provider IDs remain private.',
            'limits': ['Runner author reviewed corpus; execution by a fresh agent is procedural separation, not independent organization or controls review.',
                       'Cloud alias is mutable; no weight/deployment pin. Single small synthetic set; no plant or general capability claim.']}


def register(path):
    value = {'registered_at': stamp(), 'design': design(), 'source_sha256': source_hashes(),
             'protocol_sha256': file_sha(PROTOCOL)}
    _new_json(path, value, private=False)
    return {'preregistration_sha256': file_sha(path)}


def verify_package(package):
    """Verify the externally retained head before reading cases or executing code."""
    package = Path(package).resolve()
    if package.is_relative_to(ROOT.resolve()):
        raise ValueError('Private holdout must remain outside the repository.')
    manifest_path = package / 'reviewed-manifest.json'
    if manifest_path.is_symlink() or file_sha(manifest_path) != REVIEWED_SHA256:
        raise ValueError('Reviewed holdout manifest hash mismatch.')
    manifest = _load(manifest_path)
    files = manifest.get('files')
    if not isinstance(files, dict) or not {'cases.json','materialize.py','review/preregistration.json'} <= files.keys():
        raise ValueError('Incomplete reviewed file manifest.')
    for relative, expected in files.items():
        path = package / relative
        if (Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink()
                or not path.resolve().is_relative_to(package) or file_sha(path) != expected):
            raise ValueError('A frozen holdout file changed.')
    inventory = list(package.rglob('*'))
    if any(p.is_symlink() for p in inventory):
        raise ValueError('Symlinks are excluded from the private package.')
    actual = {str(p.relative_to(package)) for p in inventory if p.is_file()}
    if actual != set(files) | {'reviewed-manifest.json'}:
        raise ValueError('Unexpected private package files.')
    corpus = _load(package / 'cases.json')
    cases = corpus.get('cases', [])
    if (len(cases) != COUNTS['total'] or len({c['case_id'] for c in cases}) != len(cases)
            or sum(c['expected']['status'] == 'usable' for c in cases) != COUNTS['usable']
            or sum(c['expected']['status'] == 'rejected' for c in cases) != COUNTS['guards']):
        raise ValueError('Frozen case denominators differ from registration.')
    return corpus


def _private_path(path, package):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT.resolve()) or path.is_relative_to(package):
        raise ValueError('Private campaign output must be outside the repository and frozen package.')
    if path.exists():
        raise FileExistsError('Use a new private output path; no overwrite or resume.')
    return path


def _fidelity(observation, result):
    if result.get('status') != 'advisory':
        return None
    history = observation['history']
    expected = {'snapshot:alarms': observation['alarms'],
                'policy:lab-v2': {'id': 'lab-advisory-policy-v2', 'sha256': POLICY_HASH}}
    for tag in observation['tags']:
        expected['history:' + tag['id']] = {'clock': history['clock'], 'epoch_id': history['epoch_id'], 'unit': tag['unit'],
            'samples': [{'sequence': s['sequence'], 'elapsed_s': s['elapsed_s'], 'value': s['values'][tag['id']],
                         'quality': s['quality'][tag['id']]} for s in history['samples']]}
    supplied = result.get('evidence', [])
    return (isinstance(supplied, list) and len(supplied) == len(expected)
            and {e['ref']: e['value'] for e in supplied} == expected)


def _identifier_sets(result):
    return {'findings': [f['id'] for f in result['findings']],
            'checks': [c['id'] for c in result['checks']], 'evidence': [e['ref'] for e in result['evidence']]}


def _score(case, observation, result, events):
    expected = case['expected']
    sets = _identifier_sets(result)
    fidelity = _fidelity(observation, result)
    usable = expected['status'] == 'usable'
    if usable:
        passed = (result['status'] == 'advisory' and result['reason'] == 'supported' and fidelity is True
                  and all(set(sets[k]) == set(expected[k]) and len(sets[k]) == len(set(sets[k])) for k in sets))
    else:
        passed = (result['status'] == 'abstain' and result['reason'] == expected['reason'] and not any(sets.values()))
    reads = {e['payload']['data']['name'] for e in events if e['payload']['kind'] == 'tool_read'}
    responses = [e for e in events if e['payload']['kind'] == 'provider_response']
    candidate = responses[-1]['payload']['data']['response'] if responses else None
    if responses and any(e['seq'] > responses[-1]['seq'] and e['payload']['kind'] == 'provider_call' for e in events):
        candidate = None
    return {'id': case['case_id'], 'expected': expected, 'observation': observation, 'actual': result,
            'passed': passed, 'evidence_fidelity': fidelity, 'candidate': candidate,
            'required_reads_complete': {'read_snapshot','read_policy','read_history'} <= reads}


def _stats(values):
    return {'count': len(values), 'median': statistics.median(values) if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None}


def aggregate(rows):
    """Numeric/allowlisted fields only. Never copy identifiers or arbitrary text."""
    usable = [r for r in rows if r['expected']['status'] == 'usable']
    guards = [r for r in rows if r['expected']['status'] == 'rejected']
    released = [r for r in usable if r['actual']['status'] == 'advisory']
    content = {}
    for field, candidate_field in [('findings','finding_ids'), ('checks','check_ids'), ('evidence','evidence')]:
        matched = target = predicted = exact = observed = extras_released = 0
        for row in usable:
            candidate = row['candidate']
            values = candidate.get(candidate_field) if isinstance(candidate, dict) and candidate.get('kind') == 'advice' else None
            present = isinstance(values, list) and all(isinstance(v, str) for v in values)
            ids = set(values) if present else set()
            expected = set(row['expected'][field])
            matched += len(ids & expected); target += len(expected); predicted += len(ids)
            observed += present
            exact += bool(present and values and len(values) <= 16 and len(values) == len(ids) and ids == expected)
            if row['actual']['status'] == 'advisory':
                extras_released += len(set(_identifier_sets(row['actual'])[field]) - expected)
        content[field] = {'exact_sets': exact, 'total_cases': len(usable), 'observed_lists': observed,
                          'fixed_campaign_usable_total': COUNTS['usable'],
                          'matched': matched, 'expected': target, 'predicted': predicted,
                          'omitted': target-matched, 'extras': predicted-matched,
                          'micro_precision': matched/predicted if predicted else None,
                          'micro_recall': matched/target if target else None,
                          'unsupported_released': extras_released}
    failures = [r['actual'].get('failure', {}) for r in rows if r['actual']['status'] == 'abstain']
    return {'observed_total': len(rows),
            'useful_assessment': {'passed': sum(r['passed'] for r in usable), 'total': COUNTS['usable'], 'observed': len(usable)},
            'input_guards': {'passed': sum(r['passed'] for r in guards), 'total': COUNTS['guards'], 'observed': len(guards)},
            'unexpected_guard_advisories': sum(r['actual']['status'] == 'advisory' for r in guards),
            'required_reads': {'passed': sum(r['required_reads_complete'] for r in usable), 'total': COUNTS['usable'], 'observed': len(usable)},
            'exact_advice_envelopes': sum(isinstance(r['candidate'], dict) and r['candidate'].get('kind') == 'advice' and envelope(r['candidate'])['valid'] for r in usable),
            'identifiers': content,
            'released_evidence_fidelity': {'passed': sum(r['evidence_fidelity'] is True for r in released), 'total': len(released),
                                          'fraction': sum(r['evidence_fidelity'] is True for r in released)/len(released) if released else None},
            'failure_categories': dict(Counter(f.get('category') if f.get('category') in CATEGORIES else 'unclassified' for f in failures)),
            'failure_stages': dict(Counter(f.get('stage') if f.get('stage') in STAGES else 'unclassified' for f in failures)),
            'latency_ms': {name: _stats([r['actual']['elapsed_ms'] for r in cohort]) for name, cohort in {
                'usable_attempts': usable, 'useful_accepted': [r for r in usable if r['passed']],
                'withheld_usable': [r for r in usable if r['actual']['status'] == 'abstain'], 'guard_attempts': guards}.items()}}


def _assess_phase(label, provider, cases, materialize, private, *, stop_on_provider=False):
    folder = private / label
    folder.mkdir(mode=0o700)
    rows = []
    store = EvidenceStore(folder / 'evidence.sqlite3')
    try:
        agent = Agent(store, provider, clock=now_utc, system_prompt=prompts()['policy-only'])
        for index, case in enumerate(cases):
            observation = materialize(case['case_id'], now=now_utc())
            # Persist the exact first attempt before Agent or provider can fail.
            _new_json(folder / f'{index:03d}.input.json', {'id': case['case_id'], 'observation': observation})
            result = agent.assess(observation)
            events = [e for e in store.export() if e['payload']['run_id'] == result['run_id']]
            row = _score(case, observation, result, events)
            _new_json(folder / f'{index:03d}.result.json', row)
            rows.append(row)
            if stop_on_provider and (provider_failure_requires_stop(result, events) or result['reason'] == 'provider_budget'):
                raise RuntimeError('Provider infrastructure interrupted campaign.')
        return rows
    finally:
        try:
            _new_json(folder / 'evidence.json', store.bundle())
        finally:
            store.close()


def _phase_rows(private, label):
    folder = private / label
    return [_load(p) for p in sorted(folder.glob('*.result.json'))] if folder.exists() else []


def _controls_pass(reports):
    baseline, refusal = (aggregate(reports[name]) for name in ('baseline','always-refuse'))
    return (baseline['observed_total'] == COUNTS['total'] and baseline['useful_assessment']['passed'] == COUNTS['usable']
            and baseline['input_guards']['passed'] == COUNTS['guards'] and baseline['unexpected_guard_advisories'] == 0
            and refusal['observed_total'] == COUNTS['total'] and refusal['useful_assessment']['passed'] == 0
            and refusal['input_guards']['passed'] == COUNTS['guards'] and refusal['unexpected_guard_advisories'] == 0)


def run(package, env_file, private_output, public_output, preregistration, expected_sha256, *, allow_cloud_synthetic=False):
    if allow_cloud_synthetic is not True:
        raise ValueError('Explicit cloud-synthetic consent required.')
    if file_sha(preregistration) != expected_sha256:
        raise ValueError('Public preregistration hash mismatch.')
    registration = _load(preregistration)
    if (registration.get('design') != design() or registration.get('source_sha256') != source_hashes()
            or registration.get('protocol_sha256') != file_sha(PROTOCOL)):
        raise ValueError('Registered source or design changed.')
    package = Path(package).resolve()
    corpus = verify_package(package)
    private = _private_path(private_output, package)
    public_output = Path(public_output).resolve()
    if public_output.exists() or public_output.is_relative_to(package) or public_output.is_relative_to(private):
        raise ValueError('Public result requires a new path outside private outputs.')
    claim = package.parent / ('.campaign-' + REVIEWED_SHA256[:16] + '-' + PROMPT_SHA256[:16] + '.json')
    started_at = stamp()
    _new_json(claim, {'preregistration_sha256': expected_sha256, 'claimed_at': started_at, 'private_output': str(private)})
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    private.chmod(0o700)
    _new_json(private / 'preregistration.json', registration)
    _new_json(private / 'case-order.json', [case['case_id'] for case in corpus['cases']])
    _new_json(private / 'run-start.json', {'started_at': started_at, 'preregistration_sha256': expected_sha256,
                                         'reviewed_manifest_sha256': REVIEWED_SHA256, 'candidate_prompt_sha256': PROMPT_SHA256})
    reports = {}
    completed, failure = False, None
    source_unchanged = freeze_unchanged = None
    phase = 'materializer_setup'
    provider = None
    try:
        materialize = runpy.run_path(str(package / 'materialize.py'))['materialize']
        for label, control in [('baseline', Baseline()), ('always-refuse', AlwaysRefuse())]:
            phase = label
            reports[label] = _assess_phase(label, control, corpus['cases'], materialize, private)
            if label == 'baseline' and not all(r['passed'] for r in reports[label]):
                raise RuntimeError('Independent baseline control disagreed.')
        if not _controls_pass(reports):
            raise RuntimeError('Negative control prerequisites failed.')
        verify_package(package)
        if source_hashes() != registration['source_sha256']:
            raise RuntimeError('Source changed before candidate inference.')
        phase = 'provider_preparation'
        provider = DeepSeek(read_api_key(env_file), allow_cloud_synthetic=True, max_calls=145)
        metadata = provider.prepare()
        _new_json(private / 'provider-metadata.json', metadata)
        if (metadata.get('settings') != {k: v for k, v in SETTINGS.items() if k != 'model'}
                or metadata.get('requested_model') != SETTINGS['model']
                or metadata.get('maximum_inference_calls') != 145):
            raise RuntimeError('Prepared provider differs from registration.')
        warmup = {'purpose': 'One public protocol warmup without private observations.'}
        phase = 'warmup'
        try:
            warmup['response'] = provider.respond([{'role': 'system', 'content': prompts()['policy-only']},
                                                  {'role': 'user', 'content': canonical(ENTRY)}])
        finally:
            warmup['calls'] = provider.drain_receipts()
            _new_json(private / 'warmup.json', warmup)
        phase = 'candidate'
        reports['candidate'] = _assess_phase('candidate', provider, corpus['cases'], materialize, private, stop_on_provider=True)
        phase = 'final_integrity'
        _new_json(private / 'provider-after.json', provider.inspect_models())
        freeze_unchanged = False
        verify_package(package)
        freeze_unchanged = True
        source_unchanged = source_hashes() == registration['source_sha256'] and file_sha(PROTOCOL) == registration['protocol_sha256']
        if not source_unchanged:
            raise RuntimeError('Source changed during campaign.')
        for label in reports:
            verify_bundle(_load(private / label / 'evidence.json'))
        completed = True
    except Exception as exc:
        # No exception message, case identifier, remote body or credential can
        # reach public status. Partial immutable private evidence stays in place.
        failure = 'campaign_interrupted'
        _new_json(private / 'interruption.json', {'at': stamp(), 'type': type(exc).__name__, 'phase': phase})
    summaries = {label: aggregate(_phase_rows(private, label)) for label in ('baseline','always-refuse','candidate')}
    candidate = summaries['candidate']
    controls_passed = _controls_pass({label: _phase_rows(private, label) for label in ('baseline','always-refuse')})
    passed = (completed and controls_passed
              and candidate['observed_total'] == COUNTS['total']
              and candidate['useful_assessment']['passed'] == COUNTS['usable']
              and candidate['input_guards']['passed'] == COUNTS['guards'] and candidate['unexpected_guard_advisories'] == 0)
    secondary = (completed and controls_passed and candidate['required_reads']['passed'] == COUNTS['usable']
                 and all(c['exact_sets'] == COUNTS['usable'] and c['unsupported_released'] == 0 for c in candidate['identifiers'].values())
                 and candidate['released_evidence_fidelity']['fraction'] == 1.0)
    summary = {'schema': 'moa-sealed-holdout-aggregate-v1', 'started_at': started_at, 'finished_at': stamp(), 'completed': completed,
               'status': 'completed' if completed else 'incomplete', 'interruption': failure,
               'interrupted_phase': phase if failure else None, 'controls_passed': controls_passed,
               'source_unchanged': source_unchanged, 'freeze_unchanged': freeze_unchanged,
               'primary_passed': passed, 'secondary_passed': secondary, 'promotion': 'not_authorized', 'scope': 'synthetic-policy-contract-only',
               'preregistration_sha256': expected_sha256, 'reviewed_manifest_sha256': REVIEWED_SHA256,
               'candidate_prompt_sha256': PROMPT_SHA256, 'reports': summaries,
               'completion_calls_including_warmup': provider.calls if provider is not None else 0,
               'limits': design()['limits']}
    _new_json(private / 'aggregate.json', summary)
    inventory = {str(p.relative_to(private)): file_sha(p) for p in sorted(private.rglob('*')) if p.is_file()}
    _new_json(private / 'artifact-manifest.json', {'files': inventory})
    summary['private_artifact_manifest_sha256'] = file_sha(private / 'artifact-manifest.json')
    _new_json(public_output, summary, private=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    registration = sub.add_parser('register')
    registration.add_argument('--output', required=True)
    execution = sub.add_parser('run')
    for option in ('package','env-file','private-output','public-output','preregistration','expected-sha256'):
        execution.add_argument('--' + option, required=True)
    execution.add_argument('--allow-cloud-synthetic', action='store_true', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'register':
            result = register(args.output)
        else:
            result = run(args.package, args.env_file, args.private_output, args.public_output,
                         args.preregistration, args.expected_sha256, allow_cloud_synthetic=args.allow_cloud_synthetic)
        print(json.dumps(result, allow_nan=False))
        return 0 if args.command == 'register' or result['primary_passed'] else 1
    except Exception:
        print('Holdout preflight or persistence failed. No passing campaign was reported.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
