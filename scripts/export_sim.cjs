#!/usr/bin/env node
'use strict';
// Operator-run export from a trusted local simulator checkout. NOT an agent tool.
// Only coachProjection() crosses the boundary; no instructor truth is exported.
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const repo = process.argv[2];
const scenario = process.argv[3] || 'normal';
if (!repo || !['normal', 'bad-quality'].includes(scenario)) {
  console.error('Usage: node scripts/export_sim.cjs /trusted/experion-station-sim [normal|bad-quality]');
  process.exit(2);
}
const root = path.resolve(repo);
const revision = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim();
// The harness supports Node file execution. It must not be evaluated via node -e.
const {Component} = require(path.join(root, 'tools/logic-harness.js')).load();
const sim = new Component({});
sim.initSim(1700000000000);
sim.applyPreset('U1_SS');
if (scenario === 'bad-quality') sim.setUpset('xmtr', true);
for (let step = 0; step < 40; step++) sim.step(0.5);
const projection = sim.coachProjection();
const captured = new Date().toISOString();
// Treat unknown/null values as unusable instead of silently deleting evidence.
const observation = {
  schema_version:'1.0', snapshot_id:'ess-' + scenario + '-' + Date.now(), captured_at:captured,
  profile:'ess-u1-v1',
  source:{kind:'synthetic', adapter:'ess-v1', revision, model_id:require(path.join(root, 'src/model-id.js'))},
  tags:projection.catalog.map(row => ({id:row.tag, value:row.pv, unit:row.eu,
    quality:row.badPv || row.pv === null ? 'bad' : 'good', observed_at:captured})),
  alarms:projection.alarms.map((row, i) => ({id:'alarm-' + i, tag:row.tag, condition:row.cond,
    priority:row.priority, state:row.state})),
  // coachProjection truncates to twelve alarm rows. Require complete coverage.
  alarm_coverage:sim.alarmEngine.list().length === projection.alarms.length ? 'complete' : 'partial',
};
const status = execFileSync('git', ['-C', root, 'status', '--porcelain', '--untracked-files=no'], {encoding:'utf8'}).trim();
if (status) {
  console.error('Refusing provenance claim from a modified tracked simulator checkout. Commit or use a clean checkout.');
  process.exit(2);
}
// Digest to stderr is an operator receipt and does not alter the JSON contract.
console.error('Synthetic export from ' + revision + '; sha256=' + createHash('sha256').update(JSON.stringify(observation)).digest('hex'));
process.stdout.write(JSON.stringify(observation, null, 2) + '\n');
