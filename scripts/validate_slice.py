#!/usr/bin/env python3
"""Record legacy plus stream-specific checks without inference or downloads."""
import argparse
import os
from pathlib import Path
import sys
from validation_v08 import run_validation

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim-repo',required=True,type=Path,help='Trusted legacy simulator at the unchanged drill pin')
    parser.add_argument('--stream-sim-repo',required=True,type=Path,help='Trusted clean simulator at stream pin')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--timeout',type=float,default=600)
    parser.add_argument('--current-pointer',type=Path,default=Path('receipts/current.json'))
    args=parser.parse_args()
    env=dict(os.environ,MOA_SIM_REPO=str(args.sim_repo.resolve()),MOA_STREAM_SIM_REPO=str(args.stream_sim_repo.resolve()))
    commands=[
        [sys.executable,'-m','unittest','discover','-s','tests','-v'],
        [sys.executable,'-m','moa','eval'],
        [sys.executable,'-m','moa','drill-eval','--sim-repo',str(args.sim_repo.resolve())],
        ['node','--test','tests/stream-boundary.test.cjs'],
        ['node','--check','scripts/run_slice.cjs'],
        ['node','--check','moa/web/app.js'],
        ['node','--check','scripts/export_sim.cjs'],
        ['node','--check','scripts/export_trajectory.cjs'],
    ]
    receipt=run_validation(commands,root=ROOT,output=args.output,env=env,timeout=args.timeout,
        current_pointer=args.current_pointer,metadata={'legacy_simulator':str(args.sim_repo.resolve()),
        'stream_simulator':str(args.stream_sim_repo.resolve()),'models_called':0})
    return 0 if receipt['passed'] else 1
if __name__=='__main__': raise SystemExit(main())
