"""Provider-free schema 1.2 stream. Only the observation tree is opened.

An OS sandbox is still needed against a hostile process with this user's access.
The module has no general file/tool interface and never imports a provider.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time

from . import stream_contracts as c
from .stream_policy import assess, read_policy

class Stream:
    def __init__(self, observation, configuration, *, pin=None, scoped_degradation=True):
        self.pin=pin
        self.observation=c.manifest(observation,pin)
        self.configuration=c.config(configuration,self.observation)
        self.stream_id=c.sha(self.observation)
        self.scoped_degradation=scoped_degradation
        self.history=[]
        self.latest=None
        self.result_seq=0
        self._current=None
        self.events=[]
        self._prepared={}
        self._releasing=False
        self.lock=threading.RLock()

    def new_epoch(self, observation, configuration):
        """Explicit operator resync, never inferred from an untrusted sample."""
        new=c.manifest(observation,self.pin)
        cfg=c.config(configuration,new)
        with self.lock:
            if self._releasing: raise c.StreamError('state change during release')
            if (c.sha(new),new['start_tick'])==(self.stream_id,self.observation['start_tick']):
                raise c.StreamError('epoch did not change')
            self.observation,self.configuration=new,cfg
            self.stream_id=c.sha(new)
            self.history=[]; self.latest=None; self._current=None
            self.events.append({'kind':'epoch_changed','start_tick':new['start_tick']})

    def accept(self, row, *, now=None):
        with self.lock:
            if self._releasing: raise c.StreamError('state change during release')
            row=c.sample(row,self.observation,self.configuration,now)
            if self.latest:
                prev=self.latest
                if row['seq']<=prev['seq']: raise c.StreamError('duplicate or reversed sequence')
                if row['tick']<=prev['tick']: raise c.StreamError('duplicate or reversed tick')
                before={p['tag']:p['control_revision'] for p in prev['points']}
                if any(p['control_revision']<before[p['tag']] for p in row['points']):
                    raise c.StreamError('control revision reversed')
                gap=row['tick']-prev['tick']
                if gap>2 or row['seq']!=prev['seq']+1:
                    reset=gap>10
                    self.events.append({'kind':'gap','from_tick':prev['tick'],'to_tick':row['tick'],'window_reset':reset})
                    if reset: self.history=[]
            self.latest=row
            self.history.append(row)
            # Retain the preceding grid endpoint between five-second assessments.
            floor=(row['tick']//10)*10
            self.history=[r for r in self.history if r['tick']>=floor-240]
            self._current=None
            return copy.deepcopy(row)

    def grid(self):
        if self.latest is None: return [None]*25
        end=(self.latest['tick']//10)*10
        result=[]
        for tick in range(end-240,end+1,10):
            candidates=[row for row in self.history if row['tick']<=tick]
            row=candidates[-1] if candidates else None
            # A 1 Hz sample absent at its grid instant is a missing grid point.
            # Carrying an older sample across a missing second would silently fill it.
            result.append(copy.deepcopy(row) if row and 0<=tick-row['tick']<2 else None)
        return result

    def prepare(self):
        with self.lock:
            if self._releasing: raise c.StreamError('assessment during release')
            if self.latest is None: raise c.StreamError('no accepted observation')
            started=time.monotonic()
            row=copy.deepcopy(self.latest)
            grid=self.grid()
            decision=assess(row,grid,self.configuration,scoped_degradation=self.scoped_degradation)
            end=(row['tick']//10)*10
            self.result_seq+=1
            result={'schema':'1.2','stream_id':self.stream_id,'result_seq':self.result_seq,'mode':self.observation['mode'],
                'bound':{'seq':row['seq'],'tick':row['tick'],
                    'window':{'start_tick':max(self.observation['start_tick'],end-240),'end_tick':end},
                    'control_revisions':{p['tag']:p['control_revision'] for p in row['points'] if p['tag'] in c.LOOPS},
                    'alarm_episodes':sorted(a['episode_id'] for a in row['alarms']),
                    'config_sha256':self.observation['config_sha256']},
                **decision,'superseded':False,'processing_ms':round((time.monotonic()-started)*1000,6)}
            # Retain exact trusted decisions: callers cannot rewrite their bindings.
            self._prepared[self.result_seq]=copy.deepcopy(result)
            if len(self._prepared)>256:
                del self._prepared[min(self._prepared)]
            return result

    def release(self, result, *, sink=None, now=None):
        with self.lock:
            if self._releasing: raise c.StreamError('nested release')
            if not isinstance(result,dict) or self._prepared.get(result.get('result_seq')) != result:
                raise c.StreamError('result is not an unchanged prepared decision')
            result=copy.deepcopy(result)
            result['superseded']=(self.latest is None or result['stream_id']!=self.stream_id
                or result['bound']['seq']!=self.latest['seq'] or result['bound']['tick']!=self.latest['tick'])
            if not result['superseded']: c.fresh(self.latest,self.observation,now)
            self._releasing=True
            try:
                if sink is not None:
                    sink.write(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
                    sink.flush()  # A failed write never makes this a current result.
                if not result['superseded']:
                    c.fresh(self.latest,self.observation,now)
                    self._current=copy.deepcopy(result)
            finally:
                self._releasing=False
            self._prepared.pop(result['result_seq'])
            return result

    @property
    def current(self):
        with self.lock:
            if self._current is None: return None
            c.fresh(self.latest,self.observation)
            return copy.deepcopy(self._current)

    def read(self, name, arguments=None):
        """Explicit read surface over already validated observation memory only."""
        arguments={} if arguments is None else arguments
        with self.lock:
            if self.latest is None: raise c.StreamError('no accepted observation')
            c.fresh(self.latest,self.observation)
            if name=='read_tag':
                c.keys(arguments,('tag',),'read_tag')
                if arguments['tag'] not in c.TAGS: raise c.StreamError('tag outside profile')
                result=next(p for p in self.latest['points'] if p['tag']==arguments['tag'])
            else:
                c.keys(arguments,(),name)
                if name=='read_snapshot': result=self.latest
                elif name=='read_history': result={'grid_step_ms':5000,'samples':self.grid()}
                elif name=='read_policy': result=read_policy()
                else: raise c.StreamError('tool not allowed')
            return copy.deepcopy(result)


def _read_file(path):
    if path.is_symlink() or not path.is_file(): raise c.StreamError('observation file must be a regular non-symlink file')
    with path.open('rb') as handle: raw=handle.read(c.MAX_BYTES+1)
    return c.loads(raw)

def load_directory(directory):
    """Only fixed model-visible filenames. Runner/truth paths cannot be selected."""
    directory=Path(directory).absolute()
    if directory.is_symlink() or directory.parent.is_symlink(): raise c.StreamError('symlink stream path rejected')
    if directory.parent.name!='stream' or not directory.name.startswith('run-'):
        raise c.StreamError('expected stream/run-* observation directory')
    observation=_read_file(directory/'observation.json')
    configuration=_read_file(directory.parent/'config.json')
    pin=_read_file(Path(__file__).parent/'data'/'stream-v1.json')
    return directory,Stream(observation,configuration,pin=pin)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory')
    parser.add_argument('--stdin',action='store_true',help='consume operator rows as the trusted runner emits them')
    parser.add_argument('--no-scoped-degradation',action='store_true')
    args=parser.parse_args(argv)
    try:
        directory,processor=load_directory(args.run_directory)
        processor.scoped_degradation=not args.no_scoped_degradation
        operator=directory/'operator.jsonl'
        if not args.stdin and (operator.is_symlink() or not operator.is_file()): raise c.StreamError('operator stream unavailable')
        source=sys.stdin if args.stdin else operator.open('r',encoding='utf-8')
        try:
            with (directory/'results.jsonl').open('x',encoding='utf-8') as output:
                while True:
                    line=source.readline(c.MAX_BYTES+2)
                    if not line: break
                    if not line.endswith('\n'): raise c.StreamError('unterminated or oversized stream record')
                    processor.accept(c.loads(line))
                    processor.release(processor.prepare(),sink=output)
                if processor.result_seq == 0: raise c.StreamError('empty operator stream')
                os.fsync(output.fileno())
        finally:
            if source is not sys.stdin: source.close()
        print(json.dumps({'schema':'1.2','policy':'lab-v2-deps','accepted':processor.result_seq,'stream_events':processor.events}),file=sys.stderr)
        return 0
    except (c.StreamError,OSError,ValueError) as exc:
        print(f'stream refused: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__': raise SystemExit(main())
