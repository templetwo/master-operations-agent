"""Boundary, ordering and release tests for the separate stream contract."""
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from moa import stream_contracts as c
from moa.stream import Stream, load_directory


def fixture():
    pin=json.loads((Path(__file__).parents[1]/'moa/data/stream-v1.json').read_text())
    tags={tag:{'unit':c.UNITS[tag],'lo':0,'hi':200 if tag=='TIC201' else 100,
        'alarms':{},'sp_limits':None,'op_limits':None,'kind':'pid' if tag in c.LOOPS else 'ind',
        'master':None,'slave':None} for tag in c.TAGS}
    config={'model_id':pin['model_id'],'tags':tags,'trips':[
        {'id':i,'tag':t,'comparator':op,'threshold':n,'unit':c.UNITS[t]} for i,t,op,n in (
        ('R201_HITEMP','TIC201','>=',185),('TK101_HIHI','LIC101','>=',98),
        ('P101_TRIP','LIC101','<',2),('P101_PERMISSIVE','LIC101','<',5))]}
    manifest={'schema':'1.2','profile':'ess-u1-stream-v1','adapter':'ess-stream-v1',**pin,
        'step_s':.5,'sample_hz':1,'tags':list(c.TAGS),'alarm_scope':'plant','start_tick':0,
        'config_sha256':c.sha(config),'mode':'replay'}
    return manifest,config


def row(manifest, tick=0, seq=None):
    values={'FI100':60000,'LIC101':50000,'FIC102':60000,'TIC201':150000,'TIC202':40000}
    return {'schema':'1.2','stream_id':c.sha(manifest),'seq':seq if seq is not None else (tick-manifest['start_tick'])//2+1,
        'tick':tick,'sim_time_ms':tick*500,'captured_at':None,
        'points':[{'tag':tag,'value_milli':values[tag],'unit':c.UNITS[tag],'source_quality':'GOOD',
            'sample_tick':tick,'sample_sim_time_ms':tick*500,'mode':'AUTO' if tag in c.LOOPS else None,
            'sp_milli':values[tag] if tag in c.LOOPS else None,'op_milli':50000 if tag in c.LOOPS else None,
            'control_revision':0} for tag in c.TAGS],
        'alarms':[],'alarms_total_matched':0,'alarms_omitted':0}


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.manifest,self.config=fixture()
        self.stream=Stream(self.manifest,self.config)

    def test_unknown_fields_rejected_at_every_layer(self):
        for field in ('faults','env','archFaults','instructor','station','seed','label','schedule'):
            with self.subTest(field=field):
                value=row(self.manifest);value[field]={}
                with self.assertRaises(c.StreamError): self.stream.accept(value)
                value=row(self.manifest);value['points'][0][field]='hidden'
                with self.assertRaises(c.StreamError): self.stream.accept(value)
                m=copy.deepcopy(self.manifest);m[field]=0
                with self.assertRaises(c.StreamError): c.manifest(m)
                cfg=copy.deepcopy(self.config);cfg['tags']['FI100'][field]=0
                m=copy.deepcopy(self.manifest);m['config_sha256']=c.sha(cfg)
                with self.assertRaises(c.StreamError): c.config(cfg,m)

    def test_strict_json_and_milli_units(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(c.StreamError): c.loads(raw)
        for bad in (True,150000.0,float('nan'),'150000'):
            value=row(self.manifest);value['points'][3]['value_milli']=bad
            with self.assertRaises(c.StreamError): self.stream.accept(value)

    def test_bad_value_withheld_without_mutating_source_quality(self):
        value=row(self.manifest);value['points'][2]['source_quality']='BAD'
        with self.assertRaises(c.StreamError): self.stream.accept(value)
        value['points'][2]['value_milli']=None
        self.stream.accept(value)
        result=self.stream.prepare()
        self.assertTrue(any(x['tag']=='FIC102' for x in result['unusable_measurements']))
        self.assertEqual(self.stream.read('read_tag',{'tag':'FIC102'})['source_quality'],'BAD')

    def test_late_result_never_replaces_newer_result(self):
        self.stream.accept(row(self.manifest,0));old=self.stream.prepare()
        self.stream.accept(row(self.manifest,10));new=self.stream.release(self.stream.prepare())
        rejected=self.stream.release(old)
        self.assertTrue(rejected['superseded'])
        self.assertEqual(self.stream.current,new)
        self.stream.accept(row(self.manifest,12))
        self.assertIsNone(self.stream.current)

    def test_tampered_result_bindings_and_findings_cannot_release(self):
        self.stream.accept(row(self.manifest))
        original=self.stream.prepare()
        for field in ('findings','config_sha256','control_revisions','alarm_episodes'):
            forged=copy.deepcopy(original)
            if field=='findings': forged[field]=['unregistered_finding']
            else: forged['bound'][field]='altered'
            with self.assertRaises(c.StreamError): self.stream.release(forged)
        self.assertIsNone(self.stream.current)
        self.stream.release(original)
        with self.assertRaises(c.StreamError): self.stream.release(original)

    def test_epoch_sampling_sequence_is_exact(self):
        with self.assertRaises(c.StreamError): self.stream.accept(row(self.manifest,0,999))

    def test_state_changing_sink_cannot_reenter_release(self):
        stream=self.stream;manifest=self.manifest
        class ReentrantSink:
            def write(self,_): stream.accept(row(manifest,10))
            def flush(self): pass
        stream.accept(row(manifest))
        with self.assertRaises(c.StreamError): stream.release(stream.prepare(),sink=ReentrantSink())
        self.assertIsNone(stream.current)
        self.assertEqual(stream.latest['tick'],0)

    def test_write_failure_cannot_release(self):
        class FailedSink:
            def write(self,_): raise OSError('injected disk failure')
        self.stream.accept(row(self.manifest))
        with self.assertRaises(OSError): self.stream.release(self.stream.prepare(),sink=FailedSink())
        self.assertIsNone(self.stream.current)

    def test_stream_integrity_resync_and_restart(self):
        for tick in range(0,242,2): self.stream.accept(row(self.manifest,tick))
        self.assertTrue(all(self.stream.grid()))
        with self.assertRaises(c.StreamError): self.stream.accept(row(self.manifest,240))
        with self.assertRaises(c.StreamError): self.stream.accept(row(self.manifest,238,122))
        self.stream.accept(row(self.manifest,252))
        self.assertTrue(self.stream.events[-1]['window_reset'])
        self.assertFalse(all(self.stream.grid()))
        for tick in range(254,500,2): self.stream.accept(row(self.manifest,tick))
        self.assertFalse(all(self.stream.grid()))
        self.stream.accept(row(self.manifest,500))
        self.assertTrue(all(self.stream.grid()))
        restarted=Stream(self.manifest,self.config);restarted.accept(row(self.manifest,492))
        self.assertFalse(all(restarted.grid()))
        other=copy.deepcopy(self.manifest);other['start_tick']=510
        with self.assertRaises(c.StreamError): self.stream.accept(row(other,510))
        self.stream.new_epoch(other,self.config);self.stream.accept(row(other,510))
        self.assertEqual(self.stream.events[-1]['kind'],'epoch_changed')
        self.assertFalse(all(self.stream.grid()))

    def test_trends_use_five_second_grid_with_immediate_quality_gating(self):
        for tick in range(0,242,2): self.stream.accept(row(self.manifest,tick))
        for tick in (242,244,246,248):
            changed=row(self.manifest,tick);changed['points'][3]['value_milli']=160000
            self.stream.accept(changed);decision=self.stream.prepare()
            self.assertEqual(decision['bound']['window']['end_tick'],240)
            self.assertNotIn('reactor_warming',decision['findings'])
        changed=row(self.manifest,250);changed['points'][3]['value_milli']=160000
        self.stream.accept(changed)
        self.assertIn('reactor_warming',self.stream.prepare()['findings'])
        bad=row(self.manifest,252);bad['points'][3]['source_quality']='BAD';bad['points'][3]['value_milli']=None
        self.stream.accept(bad)
        self.assertNotIn('reactor_warming',self.stream.prepare()['findings'])

    def test_missing_grid_is_not_interpolated(self):
        for tick in range(0,242,2):
            if tick!=100: self.stream.accept(row(self.manifest,tick))
        grid=self.stream.grid()
        self.assertIsNone(grid[10])
        self.assertEqual(sum(x is None for x in grid),1)
        self.assertFalse(self.stream.events[-1]['window_reset'])

    def test_control_revision_reversal_rejected(self):
        a=row(self.manifest);a['points'][1]['control_revision']=2;self.stream.accept(a)
        with self.assertRaises(c.StreamError): self.stream.accept(row(self.manifest,2))

    def test_replay_clock_does_not_use_wall_freshness(self):
        self.stream.accept(row(self.manifest,100000000))
        self.assertFalse(self.stream.release(self.stream.prepare())['superseded'])
        bad=row(self.manifest);bad['captured_at']='2020-01-01T00:00:00Z'
        with self.assertRaises(c.StreamError): Stream(self.manifest,self.config).accept(bad)

    def test_live_expiration_rechecked_on_release(self):
        m=copy.deepcopy(self.manifest);m['mode']='live'
        stream=Stream(m,self.config)
        now=datetime.now(timezone.utc)
        a=row(m);a['captured_at']=now.isoformat().replace('+00:00','Z')
        stream.accept(a,now=now)
        with self.assertRaises(c.StreamError): stream.release(stream.prepare(),now=now+timedelta(seconds=61))
        self.assertIsNone(stream.current)

    def test_over_range_independent_of_source_quality(self):
        a=row(self.manifest);a['points'][4]['value_milli']=170600;self.stream.accept(a)
        result=self.stream.prepare()
        self.assertTrue(result['derived']['TIC202']['over_range'])
        self.assertEqual(self.stream.latest['points'][4]['source_quality'],'GOOD')

    def test_read_surface_cannot_open_any_path_or_mutate_state(self):
        self.stream.accept(row(self.manifest))
        for name in ('read_file','read_truth','read_labels','execute_script'):
            with self.assertRaises(c.StreamError): self.stream.read(name,{})
        for name in ('read_snapshot','read_history','read_policy'):
            with self.assertRaises(c.StreamError): self.stream.read(name,{'path':'../runner/labels.json'})
        copyrow=self.stream.read('read_snapshot');copyrow['points'][0]['value_milli']=0
        self.assertEqual(self.stream.latest['points'][0]['value_milli'],60000)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'runner').mkdir();(root/'runner/run-01').mkdir()
            with self.assertRaises(c.StreamError): load_directory(root/'runner/run-01')

    def test_canonical_clocks_excluded_but_binding_retained(self):
        x={'captured_at':'a','processing_ms':1,'stream_id':'a','nested':{'n':1.0}}
        y={'captured_at':'b','processing_ms':2,'stream_id':'a','nested':{'n':1}}
        self.assertEqual(c.sha(x),c.sha(y))
        y['stream_id']='b';self.assertNotEqual(c.sha(x),c.sha(y))

if __name__=='__main__': unittest.main()
