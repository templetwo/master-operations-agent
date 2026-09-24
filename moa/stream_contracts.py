"""Strict, separate schema 1.2 boundary. Legacy snapshot contracts are unchanged."""
from __future__ import annotations
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

TAGS = ('FI100', 'LIC101', 'FIC102', 'TIC201', 'TIC202')
LOOPS = TAGS[1:]
UNITS = dict(zip(TAGS, ('M3/H', '%', 'M3/H', 'DEG C', 'DEG C')))
MAX_BYTES = 131072

class StreamError(ValueError):
    pass

def canonical(value):
    """Match stable JSON for the finite, bounded numbers in this contract."""
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items() if k not in ('captured_at', 'processing_ms')}
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, float):
            if not math.isfinite(v): raise StreamError('non-finite number')
            return int(v) if v.is_integer() else v
        return v
    return json.dumps(clean(value), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')

def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def loads(raw):
    if len(raw.encode('utf-8') if isinstance(raw, str) else raw) > MAX_BYTES:
        raise StreamError('record exceeds byte limit')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise StreamError('duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(StreamError('non-finite number')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise StreamError('invalid JSON record') from exc

def keys(obj, expected, context):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise StreamError(f'{context}: unexpected or missing fields')

def integer(value, context, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**53-1:
        raise StreamError(f'{context}: invalid integer')

def number(value, context):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
        raise StreamError(f'{context}: invalid number')

def hexval(value, size, context):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{%d}' % size, value):
        raise StreamError(f'{context}: invalid digest')

def manifest(value, pin=None):
    keys(value, ('schema','profile','adapter','sim_revision','model_id','node','step_s','sample_hz','tags','alarm_scope','start_tick','config_sha256','mode'), 'observation')
    if (value['schema'], value['profile'], value['adapter']) != ('1.2','ess-u1-stream-v1','ess-stream-v1'):
        raise StreamError('unsupported stream profile')
    if value['tags'] != list(TAGS) or value['alarm_scope'] != 'plant' or value['mode'] not in ('live','replay'):
        raise StreamError('unsupported stream scope')
    if type(value['step_s']) not in (int,float) or value['step_s'] != .5 or type(value['sample_hz']) is not int or value['sample_hz'] != 1:
        raise StreamError('unsupported cadence')
    integer(value['start_tick'], 'start_tick')
    if value['start_tick'] % 2: raise StreamError('start tick must be on sampling grid')
    for field, size in (('sim_revision',40),('model_id',64),('config_sha256',64)):
        hexval(value[field], size, field)
    if not isinstance(value['node'], str) or not re.fullmatch(r'\d+\.\d+',value['node']):
        raise StreamError('invalid Node version')
    if pin is not None and any(value[k] != pin[k] for k in ('sim_revision','model_id','node')):
        raise StreamError('stream source does not match registered pin')
    return loads(json.dumps(value))

def config(value, observation):
    keys(value, ('model_id','tags','trips'), 'config')
    if value['model_id'] != observation['model_id'] or sha(value) != observation['config_sha256']:
        raise StreamError('configuration binding mismatch')
    keys(value['tags'], TAGS, 'config tags')
    for tag, row in value['tags'].items():
        keys(row, ('unit','lo','hi','alarms','sp_limits','op_limits','kind','master','slave'), 'tag configuration')
        if row['unit'] != UNITS[tag]: raise StreamError('configuration unit mismatch')
        for name in ('lo','hi'): number(row[name],name)
        if row['lo'] >= row['hi']: raise StreamError('configuration range reversed')
        if row['kind'] not in ('pid','ind','indicator','flow','level','temp',None):
            raise StreamError('unsupported controller kind')
        for name in ('master','slave'):
            if row[name] is not None and row[name] not in TAGS: raise StreamError('unknown loop relation')
        for name in ('sp_limits','op_limits'):
            pair = row[name]
            if pair is None: continue
            if not isinstance(pair,list) or len(pair)!=2: raise StreamError('invalid limits')
            for x in pair:
                if x is not None: number(x,name)
            if all(x is not None for x in pair) and pair[0]>pair[1]: raise StreamError('reversed limits')
        if not isinstance(row['alarms'],dict) or len(row['alarms'])>10: raise StreamError('invalid alarm config')
        for condition, triple in row['alarms'].items():
            if condition not in ('PVLL','PVLO','PVHI','PVHH','DEVHI','DEVLO','BADPV','OPHI','OPLO'): raise StreamError('unknown alarm condition')
            if not isinstance(triple,list) or len(triple)!=3 or triple[1] not in ('Urgent','High','Low','Journal'): raise StreamError('invalid alarm entry')
            number(triple[0],'alarm limit'); number(triple[2],'opaque alarm metadata')
    expected = {'R201_HITEMP':'TIC201','TK101_HIHI':'LIC101','P101_TRIP':'LIC101','P101_PERMISSIVE':'LIC101'}
    if not isinstance(value['trips'],list) or len(value['trips']) != 4: raise StreamError('invalid declared trips')
    seen = set()
    for row in value['trips']:
        keys(row, ('id','tag','comparator','threshold','unit'), 'trip')
        if row['id'] not in expected or row['id'] in seen or row['tag'] != expected[row['id']]: raise StreamError('unknown trip mapping')
        seen.add(row['id'])
        if row['id']=='P101_TRIP' and row['comparator']=='latched by':
            if row['threshold'] != 'CAVITATION (P.tankL < 2) or the pump fault (UNCOMMANDED STOP)' or row['unit'] != '':
                raise StreamError('unknown declarative latch condition')
        else:
            if row['comparator'] not in ('<','<=','>','>=') or row['unit'] != UNITS[row['tag']]: raise StreamError('invalid declared comparator')
            number(row['threshold'],'trip threshold')
    return loads(json.dumps(value))

def fresh(row, observation, now=None):
    captured = row['captured_at']
    if observation['mode']=='replay':
        if captured is not None: raise StreamError('replay capture clock must be null')
        return
    if not isinstance(captured,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',captured): raise StreamError('live capture clock requires UTC')
    try: when = datetime.fromisoformat(captured[:-1]+'+00:00')
    except ValueError as exc: raise StreamError('invalid capture time') from exc
    age = ((now or datetime.now(timezone.utc))-when).total_seconds()
    if not -2 <= age <= 60: raise StreamError('live observation outside freshness limit')

def sample(value, observation, configuration, now=None):
    keys(value, ('schema','stream_id','seq','tick','sim_time_ms','captured_at','points','alarms','alarms_total_matched','alarms_omitted'), 'sample')
    if value['schema']!='1.2' or value['stream_id']!=sha(observation): raise StreamError('sample epoch mismatch')
    for name in ('seq','tick','sim_time_ms','alarms_total_matched','alarms_omitted'): integer(value[name],name)
    if value['seq'] < 1 or value['tick'] < observation['start_tick'] or value['tick']%2 or value['sim_time_ms']!=value['tick']*500:
        raise StreamError('inconsistent sample clocks')
    if value['seq'] != (value['tick']-observation['start_tick'])//2+1:
        raise StreamError('sequence does not match the epoch sampling clock')
    fresh(value,observation,now)
    if not isinstance(value['points'],list) or len(value['points'])!=len(TAGS): raise StreamError('incomplete point set')
    seen=[]
    for point in value['points']:
        keys(point, ('tag','value_milli','unit','source_quality','sample_tick','sample_sim_time_ms','mode','sp_milli','op_milli','control_revision'), 'point')
        tag=point['tag']
        if tag not in TAGS or tag in seen: raise StreamError('duplicate or unknown tag')
        seen.append(tag)
        if point['unit']!=UNITS[tag] or point['source_quality'] not in ('GOOD','BAD'): raise StreamError('point unit or quality mismatch')
        if point['source_quality']=='BAD':
            if point['value_milli'] is not None: raise StreamError('BAD value must be withheld')
        else: integer(point['value_milli'],'value_milli',-(2**53-1))
        for name in ('sample_tick','sample_sim_time_ms','control_revision'): integer(point[name],name)
        if point['sample_tick']!=value['tick'] or point['sample_sim_time_ms']!=value['sim_time_ms']: raise StreamError('point clock mismatch')
        if point['mode'] not in ('AUTO','CAS','MAN',None): raise StreamError('unknown mode')
        for name in ('sp_milli','op_milli'):
            if point[name] is not None: integer(point[name],name,-(2**53-1))
        if tag in LOOPS and point['mode'] is None: raise StreamError('loop mode absent')
    if seen != list(TAGS): raise StreamError('noncanonical tag order')
    if not isinstance(value['alarms'],list) or len(value['alarms'])>64: raise StreamError('alarm list exceeds limit')
    if value['alarms_total_matched'] != len(value['alarms'])+value['alarms_omitted']: raise StreamError('alarm counts do not reconcile')
    ids=set()
    for alarm in value['alarms']:
        keys(alarm, ('episode_id','target','condition','priority','active','acknowledged','first_observed_sim_ms'), 'alarm')
        if not isinstance(alarm['episode_id'],str) or not re.fullmatch(r'alarm\.\d+\.\d+',alarm['episode_id']) or alarm['episode_id'] in ids: raise StreamError('invalid alarm identity')
        ids.add(alarm['episode_id'])
        for name in ('target','condition'):
            if not isinstance(alarm[name],str) or not re.fullmatch(r'[A-Z0-9_ .-]{1,64}',alarm[name]): raise StreamError('invalid alarm identifier')
        if alarm['priority'] not in ('Urgent','High','Low','Journal') or type(alarm['active']) is not bool or type(alarm['acknowledged']) is not bool: raise StreamError('invalid alarm state')
        integer(alarm['first_observed_sim_ms'],'alarm time')
        if alarm['first_observed_sim_ms']>value['sim_time_ms']: raise StreamError('future alarm')
    return loads(json.dumps(value))
