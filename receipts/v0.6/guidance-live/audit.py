"""Recompute experiment diagnostic aggregates without modifying any raw receipt."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from moa.diagnostics import diagnose_file


def main():
    directory = Path(__file__).resolve().parent
    output = directory / 'audit.json'
    if output.exists():
        raise SystemExit('Refusing to overwrite audit.')
    experiment = json.loads((directory / 'comparison.json').read_text())
    assert experiment['completed'] and experiment['experiment_valid']
    results = {}
    for arm in ('baseline', 'always-refuse', 'unchanged', 'output-only', 'policy-only', 'both'):
        path = directory / (arm + '.json')
        report = json.loads(path.read_text())
        diagnostic = diagnose_file(path, directory / (arm + '.diagnostic.json'))
        useful = [c for c in report['cases'] if c['expected']['status'] == 'advisory']
        guards = [c for c in report['cases'] if c['expected']['status'] == 'abstain']
        events = report['evidence']['events']
        def run_events(case):
            return [e['payload'] for e in events if e['payload']['run_id'] == case['actual']['run_id']]
        reads = [len({'read_snapshot','read_policy','read_history'} &
                     {e['data']['name'] for e in run_events(c) if e['kind'] == 'tool_read'}) == 3 for c in useful]
        guard_calls = sum(e['kind'] == 'provider_call' for c in guards for e in run_events(c))
        assert guard_calls == 0
        rejected = [c for c in report['cases'] if c['actual']['status'] == 'abstain']
        accounting = report['metrics']['failure_accounting']
        assert accounting['withheld'] == len(rejected) == sum(accounting['by_category'].values())
        candidate_count = sum(c['actual']['failure']['category'] in {'candidate_shape','candidate_content'} for c in rejected)
        assert report['metrics']['candidate_rejections'] == candidate_count
        accepted = [c for c in useful if c['actual']['status'] == 'advisory']
        times = [c['actual']['elapsed_ms'] for c in useful]
        good_times = [c['actual']['elapsed_ms'] for c in accepted]
        fingerprints = sorted({e['payload']['data'].get('reported',{}).get('system_fingerprint')
                               for e in events if e['payload']['kind']=='provider_call'
                               and isinstance(e['payload']['data'].get('reported',{}).get('system_fingerprint'),str)})
        results[arm] = {
            'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'verified_evidence_anchor': diagnostic['evidence_anchor'],
            'required_reads': {'completed':sum(reads),'total':len(useful)},
            'well_formed_final_advice': {'count':sum(r['candidate_state']=='advice' and r['original']['envelope']['valid']
                                                    for r in diagnostic['cases'] if r['expected_status']=='advisory'),
                                         'total':len(useful)},
            'accepted_useful': report['metrics']['useful_assessment'],
            'input_guards': report['metrics']['input_guards'], 'guard_model_calls':guard_calls,
            'candidate_rejections_verified':candidate_count,
            'usable_attempt_latency_ms': {'count':len(times),'median':statistics.median(times),'max':max(times)},
            'released_advisory_latency_ms': {'count':len(good_times),'median':statistics.median(good_times) if good_times else None,
                                           'max':max(good_times) if good_times else None},
            'provider_reported_fingerprints':fingerprints,
            'diagnostics':diagnostic['summary'], 'failure_accounting':accounting}
    audit={'source':str(Path(__file__).relative_to(ROOT)),
           'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'scope':'Offline post-experiment audit, no additional model calls, release or score changes.',
           'arms':results,
           'limits':'Local chain integrity and authored-label comparison, not independent process truth. Fingerprints are provider reports, not deployment attestation. Diagnostics never authorize advice.'}
    with output.open('x') as file: file.write(json.dumps(audit,indent=2)+'\n')
    for arm,result in results.items():
        print(arm,json.dumps({k:result[k] for k in ('required_reads','well_formed_final_advice','accepted_useful','candidate_rejections_verified')}))


if __name__ == '__main__': main()
