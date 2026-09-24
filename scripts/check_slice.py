#!/usr/bin/env python3
"""Independent artifact checks for the authored v0.8 slice, not physics approval."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from moa import stream_contracts as c
from moa.stream import Stream, load_directory


def jsonfile(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]
def require(condition,message):
    if not condition: raise AssertionError(message)
def canonical_file(path):
    if path.suffix=='.jsonl': return b''.join(c.canonical(x)+b'\n' for x in lines(path))
    return c.canonical(jsonfile(path))
def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(canonical_file(p)).hexdigest()
            for p in sorted(root.rglob('*')) if p.suffix in ('.json','.jsonl')}
def forbidden(value, names):
    denied={'faults','env','archFaults','instructor','station','seed','scenario','schedule','labels','truth','generation'}
    if isinstance(value,dict):
        require(not (set(value)&denied),'forbidden visible key')
        for item in value.values(): forbidden(item,names)
    elif isinstance(value,list):
        for item in value: forbidden(item,names)
    elif isinstance(value,str):
        require(value not in names and value not in denied,'forbidden visible scalar')
        require(not re.search(r'(?:runner/|truth\.json|labels\.json|generation\.json)',value),'restricted path visible')

def static_boundary(source):
    roles=re.findall(r'\bproject\s*\([^,]+,\s*[\'\"]([^\'\"]+)',source)
    require(roles==['subject'],'observer must have exactly its subject projection call')
    require(not re.search(r'runner_truth|plant-kernel|child_process|evaluator|instructor',source),'observer imports or names restricted surface')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slice',required=True,type=Path)
    parser.add_argument('--replay',required=True,type=Path)
    parser.add_argument('--validation',required=True,type=Path)
    parser.add_argument('--legacy-baseline',default='7ef40fc')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    records={}
    require(args.slice.resolve()!=args.replay.resolve(),'replay must be a separately generated directory')
    manifest=jsonfile(args.slice/'runner/manifest.json')
    runs={x['scenario']:x['run'] for x in manifest['runs']}
    expected={'normal':601,'cooling':361,'degraded-instrument':301,'recovery':601,'invariance-twin':421}
    require(set(runs)==set(expected),'exactly five required scenarios')
    rows={};results={}; observations={}
    for name,run in runs.items():
        directory=args.slice/'stream'/run
        rows[name]=lines(directory/'operator.jsonl');results[name]=lines(directory/'results.jsonl')
        observations[name]=jsonfile(directory/'observation.json')
        require(len(rows[name])==len(results[name])==expected[name],f'{name}: missing observations/results')
        require(all(a['seq']==b['bound']['seq'] and a['tick']==b['bound']['tick'] and not b['superseded']
                    for a,b in zip(rows[name],results[name])),f'{name}: binding mismatch')
    cfg=jsonfile(args.slice/'stream/config.json')
    def check(name,fn):
        try: detail=fn();records[name]={'passed':True,'detail':detail}
        except Exception as exc: records[name]={'passed':False,'error':str(exc),'error_type':type(exc).__name__}
    def t1():
        require(c.canonical(observations['normal'])==c.canonical(observations['invariance-twin']),'manifest invariance')
        engines=[Stream(observations[n],cfg) for n in ('normal','invariance-twin')]
        compared=0
        for a,b,ra,rb in zip(rows['normal'],rows['invariance-twin'],results['normal'],results['invariance-twin']):
            if a['tick']>=600: break
            require(c.canonical(a)==c.canonical(b),'visible sample invariance')
            require(c.canonical(ra)==c.canonical(rb),'result invariance')
            for engine,row in zip(engines,(a,b)): engine.accept(row)
            for tool,params in [('read_snapshot',{}),('read_history',{}),('read_policy',{})]+[('read_tag',{'tag':t}) for t in c.TAGS]:
                require(c.canonical(engines[0].read(tool,params))==c.canonical(engines[1].read(tool,params)),'read response invariance')
            compared+=1
        require(compared==300,'empty or shortened invariance range')
        labels=[args.slice/'runner'/runs[n]/'labels.json' for n in ('normal','cooling')]
        saved=[p.read_bytes() for p in labels]
        try:
            for p,data in zip(labels,reversed(saved)): p.write_bytes(data)
            _,engine=load_directory(args.slice/'stream'/runs['normal'])
            for row,expected_result in zip(rows['normal'],results['normal']):
                engine.accept(row)
                require(c.canonical(engine.release(engine.prepare()))==c.canonical(expected_result),'labels influenced output')
        finally:
            for p,data in zip(labels,saved): p.write_bytes(data)
        return {'prefix_samples':compared,'read_tools_per_sample':8,'label_swap_results':601}
    check('T1',t1)
    def t2():
        count=0
        for p in (args.slice/'stream').rglob('*'):
            if p.suffix not in ('.json','.jsonl'): continue
            for value in lines(p) if p.suffix=='.jsonl' else [jsonfile(p)]: forbidden(value,set(runs));count+=1
        for name in runs:
            engine=Stream(observations[name],cfg)
            for row in rows[name]:
                engine.accept(row)
                for tool in ('read_snapshot','read_history','read_policy'): forbidden(engine.read(tool),set(runs))
                for tag in c.TAGS: forbidden(engine.read('read_tag',{'tag':tag}),set(runs))
        observer=(ROOT/'scripts/lib/observe.cjs').read_text()
        static_boundary(observer)
        try: static_boundary(observer.replace("project(state, 'subject')","project(state, 'operator')"))
        except AssertionError: pass
        else: raise AssertionError('static boundary negative control failed')
        require(not re.search(r'project\s*\(', (ROOT/'scripts/lib/config.cjs').read_text()),'config projection call')
        return {'visible_records_scanned':count,'read_responses_scanned':sum(expected.values())*8,'static_negative_control':'rejected'}
    check('T2',t2)
    def t3():
        engine=Stream(observations['normal'],cfg);engine.accept(rows['normal'][0]);old=engine.prepare()
        engine.accept(rows['normal'][5]);new=engine.release(engine.prepare());late=engine.release(old)
        require(late['superseded'] and engine.current==new,'late result replaced current')
        return {'old_tick':old['bound']['tick'],'new_tick':new['bound']['tick'],'late_superseded':True}
    check('T3',t3)
    def t4():
        warming=next(r['bound']['tick'] for r in results['cooling'] if 'reactor_warming' in r['findings'])
        urgent=next(r['tick'] for r in rows['cooling'] if next(p for p in r['points'] if p['tag']=='TIC201')['value_milli']>=175000)
        labels=jsonfile(args.slice/'runner'/runs['cooling']/'labels.json')
        exact=labels['observable_criteria']['tic201_at_or_above_175c_first_tick']
        require(exact is not None and warming<exact<=urgent,'warming was not before urgent limit')
        return {'warming_tick':warming,'urgent_observable_tick_1hz':urgent,'urgent_kernel_tick':exact,
                'gap_to_kernel_limit_s':(exact-warming)*.5,'trip_tick_scoring_only':labels['reactor_trip_first_tick']}
    check('T4',t4)
    def t5():
        count=0
        for row,result in zip(rows['degraded-instrument'],results['degraded-instrument']):
            if next(p for p in row['points'] if p['tag']=='FIC102')['source_quality']!='BAD': continue
            require(any(n['tag']=='FIC102' and n['finding']=='unusable_measurement' for n in result['unusable_measurements']),'bad point not named')
            withheld={x['finding']:x['reason'] for x in result['withheld']}
            require(all(withheld.get(f) for f in ('feed_flow_increased','no_large_net_change')),'feed dependency not withheld')
            require(not set(withheld)&{'reactor_warming','reactor_cooling','reactor_below_window_peak','tank_level_increased'},'unrelated trend globally withheld')
            require('xmtr' not in json.dumps(result) and 'global_quality_gate' not in json.dumps(result),'hidden reason or global gate')
            count+=1
        first_bad=next(row['tick'] for row in rows['degraded-instrument']
            if next(point for point in row['points'] if point['tag']=='FIC102')['source_quality']=='BAD')
        labels=jsonfile(args.slice/'runner'/runs['degraded-instrument']/'labels.json')
        require(first_bad==labels['observable_criteria']['fic102_bad_source_quality_first_tick'],
                'visible BAD onset differs from recorded observable criterion')
        expected_bad=(rows['degraded-instrument'][-1]['tick']-first_bad)//2+1
        require(count>0 and count==expected_bad,'missing or discontinuous degraded interval')
        return {'bad_samples_with_scoped_findings':count,'first_bad_tick':first_bad,
                'unrelated_trend_dependencies_available':True}
    check('T5',t5)
    def t6():
        recovery=[r for r in results['recovery'] if 'monitor_thermal_recovery' in r['checks']]
        require(recovery,'no recovery check')
        for r in recovery: require(bool({'reactor_cooling','reactor_below_window_peak'}&set(r['findings'])),'unsupported recovery check')
        active=0
        for row,result in zip(rows['recovery'],results['recovery']):
            if any(a['active'] for a in row['alarms']):
                active+=1;require(result['outcome']!='normal_within_scope','normal despite active alarm')
        require(active>0,'no active alarm interval exercised')
        return {'first_recovery_check_tick':recovery[0]['bound']['tick'],'active_alarm_samples':active}
    check('T6',t6)
    def t7():
        full=[r for r in results['normal'] if r['bound']['tick']>=240]
        require(len(full)==481,'missing full normal window interval')
        require(all(r['outcome']=='normal_within_scope' for r in full),'normal window not quiet')
        return {'full_window_normal_results':len(full)}
    check('T7',t7)
    def t8():
        engine=Stream(observations['normal'],cfg)
        for row in rows['normal'][:121]: engine.accept(row)
        require(all(engine.grid()),'initial full window missing')
        for row in (rows['normal'][120],rows['normal'][119]):
            try: engine.accept(row)
            except c.StreamError: pass
            else: raise AssertionError('duplicate/reversal accepted')
        engine.accept(rows['normal'][130]);require(engine.events[-1]['window_reset'] and not all(engine.grid()),'gap did not reset')
        newer=copy.deepcopy(observations['normal']);newer['start_tick']=1000
        newrow=copy.deepcopy(rows['normal'][500]);newrow['stream_id']=c.sha(newer);newrow['seq']=1
        try: engine.accept(newrow)
        except c.StreamError: pass
        else: raise AssertionError('inline epoch silently accepted')
        engine.new_epoch(newer,cfg);engine.accept(newrow)
        require(not all(engine.grid()) and engine.events[-1]['kind']=='epoch_changed','explicit epoch did not refill')
        restarted=Stream(observations['normal'],cfg);restarted.accept(rows['normal'][500])
        require(not all(restarted.grid()),'restart reused a window')
        return {'gap':'reset','duplicate':'rejected','reversal':'rejected','inline_epoch':'rejected','explicit_epoch':'reset','restart':'refill'}
    check('T8',t8)
    def t9():
        first=inventory(args.slice);second=inventory(args.replay)
        require(first and first==second,'canonical replay differs')
        return {'runs':5,'canonical_files':len(first),'sha256':first}
    check('T9',t9)
    def t10():
        require(cfg['tags']['TIC202']['lo']==0 and cfg['tags']['TIC202']['hi']==100,'T10 configured range differs')
        value=copy.deepcopy(rows['normal'][0]);point=next(p for p in value['points'] if p['tag']=='TIC202');point['value_milli']=170600
        original=copy.deepcopy(point);engine=Stream(observations['normal'],cfg);engine.accept(value);result=engine.prepare()
        require(result['derived']['TIC202']['over_range'] and engine.read('read_tag',{'tag':'TIC202'})==original,'range changed source or failed')
        return {'value_milli':170600,'lo':0,'hi':100,'source_quality':point['source_quality'],'over_range':True}
    check('T10',t10)
    def t11():
        validation=jsonfile(args.validation);require(validation['passed'] and validation['source_unchanged'],'full validation did not pass unchanged')
        for name,digest in validation['source_sha256'].items():
            require((ROOT/name).is_file() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'stale validation source: '+name)
        commands=validation['commands']
        unit=next(x for x in commands if x['command'][1:]==['-m','unittest','discover','-s','tests','-v'])
        require(unit['exit_code']==0,'missing full unit discovery')
        log=(args.validation.parent/unit['stderr']).read_text()
        measured=re.search(r'Ran (\d+) tests',log)
        require(measured is not None and int(measured.group(1))>=133 and 'skipped=' not in log,'legacy test coverage missing')
        drill=next(x for x in commands if 'drill-eval' in x['command']);require(drill['exit_code']==0,'legacy drills failed')
        report=jsonfile(args.validation.parent/drill['stdout'])
        # Inspect the legacy report's measured scorecard without calling its oracle.
        require(report['metrics']['useful_assessment']=={'passed':10,'total':10},'legacy usefulness changed')
        require(report['metrics']['input_guards']=={'passed':8,'total':8},'legacy guards changed')
        entries=subprocess.check_output(['git','ls-tree','-r',args.legacy_baseline,'--','receipts'],cwd=ROOT,text=True).splitlines()
        count=0
        for entry in entries:
            meta,name=entry.split('\t',1);expected_blob=meta.split()[2]
            actual=subprocess.check_output(['git','hash-object',name],cwd=ROOT,text=True).strip()
            require(expected_blob==actual,'legacy receipt changed: '+name);count+=1
        require(count>0,'no legacy receipts checked')
        protected=['moa/contracts.py','moa/knowledge.py','moa/engine.py','moa/evidence.py','moa/data/drills-v1.json','scripts/export_sim.cjs','scripts/export_trajectory.cjs']
        for name in protected:
            expected_bytes=subprocess.check_output(['git','show',args.legacy_baseline+':'+name],cwd=ROOT)
            require(expected_bytes==(ROOT/name).read_bytes(),'legacy behavior source changed: '+name)
        return {'legacy_receipts_byte_identical':count,'legacy_useful':'10/10','legacy_guards':'8/8','validation_sha256':hashlib.sha256(args.validation.read_bytes()).hexdigest()}
    check('T11',t11)
    document={'schema':'moa-v08-slice-acceptance','command':[sys.executable,*sys.argv],
        'passed':len(records)==11 and all(x['passed'] for x in records.values()),'tests':records,
        'scope':'Authored synthetic interface checks. No model calls, controls approval or physics commissioning.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as handle: json.dump(document,handle,indent=2);handle.write('\n')
    print(json.dumps({name:record['passed'] for name,record in records.items()}))
    return 0 if document['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
