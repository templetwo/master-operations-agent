// Public boundary diagnostic, not a stream implementation or private bank case.
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const repo = path.resolve(process.argv[2]);
const revision = execFileSync('git', ['-C', repo, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim();
if (revision !== 'edd9dbcbb2b175fbf57121f3265794f8a082c146') throw Error('Unexpected simulator revision');
const K = require(path.join(repo, 'src/plant-kernel'));
const P = require(path.join(repo, 'src/plant-projection'));
const state = K.create({seed:20260923, sim_time_ms:0});
state.fields.P.faults.probe = 'MOA_BOUNDARY_SENTINEL';
const subject = P.project(state, 'subject'), operator = P.project(state, 'operator');
const report = {
  checked_at: new Date().toISOString(), simulator_revision:revision, node:process.version,
  scope:'Public sentinel diagnostic; no models, private cases, simulator edits or plant connection.',
  subject_has_station:Object.hasOwn(subject, 'station'),
  subject_contains_sentinel:JSON.stringify(subject).includes('MOA_BOUNDARY_SENTINEL'),
  operator_contains_sentinel:JSON.stringify(operator).includes('MOA_BOUNDARY_SENTINEL'),
  subject_keys:Object.keys(subject), point_count:subject.points.length,
  FI100:subject.points.find(x=>x.tag==='FI100'),
  example_controller:subject.points.find(x=>x.tag==='FIC102'),
  trend_tags:subject.trend_windows.map(x=>x.tag),
  limitations:'One sentinel example plus source inspection, not proof against arbitrary leakage or acceptance test T1–T11.'
};
console.log(JSON.stringify(report, null, 2));
if (report.subject_has_station || report.subject_contains_sentinel || !report.operator_contains_sentinel) process.exitCode=1;
