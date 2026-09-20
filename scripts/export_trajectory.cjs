#!/usr/bin/env node
'use strict';
// Trusted, operator-run fixture generation. Never registered as an agent tool.
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {randomUUID, createHash} = require('node:crypto');

const [repo, scenario = 'normal', seedText = '20260920'] = process.argv.slice(2);
const recipes = {
  normal: {end:180},
  'cooling-loss': {end:180, fault:'cool', start:60},
  'feed-surge': {end:180, fault:'surge', start:60},
  'bad-quality': {end:180, fault:'xmtr', start:120},
  'restoration-lag': {end:300, fault:'cool', start:60, clear:160},
  recovery: {end:480, fault:'cool', start:60, clear:160},
};
if (!repo || !Object.hasOwn(recipes, scenario) || !/^\d{1,10}$/.test(seedText) || Number(seedText) < 1 || Number(seedText) > 4294967295) {
  console.error('Usage: node scripts/export_trajectory.cjs /trusted/sim [normal|cooling-loss|feed-surge|bad-quality|restoration-lag|recovery] [seed 1..4294967295]');
  process.exit(2);
}
const root = path.resolve(repo);
const git = args => execFileSync('git', ['-C', root, ...args], {encoding:'utf8'}).trim();
const revision = git(['rev-parse', 'HEAD']);
if (git(['status', '--porcelain', '--untracked-files=no'])) throw new Error('Use a clean tracked simulator checkout.');
const {Component} = require(path.join(root, 'tools/logic-harness.js')).load();
const sim = new Component({});
sim.initSim(1700000000000);
sim.applyPreset('U1_SS', {baseTime:1700000000000});
sim.setSeed(seedText);
const recipe = recipes[scenario];
const sampleTags = ['TIC201', 'TIC202', 'FIC102', 'LIC101', 'TIC202.OP'];
const samples = [];
let projection;
for (let step = 0; step <= recipe.end * 2; step++) {
  const elapsed = step / 2;
  if (elapsed === recipe.start) sim.setUpset(recipe.fault, true);
  if (elapsed === recipe.clear) sim.setUpset(recipe.fault, false);
  if (step % 20 === 0) {
    projection = sim.coachProjection();
    const catalog = Object.fromEntries(projection.catalog.map(row => [row.tag, row]));
    const values = {}, quality = {};
    for (const id of sampleTags) {
      const row = catalog[id === 'TIC202.OP' ? 'TIC202' : id];
      values[id] = id === 'TIC202.OP' ? row.op : row.pv;
      quality[id] = row.badPv || values[id] === null ? 'bad' : 'good';
    }
    samples.push({sequence:step / 20, elapsed_s:elapsed, values, quality});
  }
  if (step < recipe.end * 2) sim.step(0.5);
}
const window = samples.slice(-13);
const latest = window.at(-1);
const captured = new Date().toISOString();
const units = {TIC201:'DEG C', TIC202:'DEG C', FIC102:'M3/H', LIC101:'%', 'TIC202.OP':'%'};
const epoch = randomUUID();
const observation = {
  schema_version:'1.1', snapshot_id:randomUUID(), captured_at:captured, profile:'ess-u1-window-v1',
  source:{kind:'synthetic', adapter:'ess-window-v1', revision, model_id:require(path.join(root, 'src/model-id.js'))},
  tags:sampleTags.map(id => ({id, value:latest.values[id], unit:units[id], quality:latest.quality[id], observed_at:captured})),
  alarms:projection.alarms.map((row, i) => ({id:'alarm-' + i, tag:row.tag, condition:row.cond, priority:row.priority, state:row.state})),
  alarm_coverage:sim.alarmEngine.list().length === projection.alarms.length ? 'complete' : 'partial',
  history:{clock:'simulation_seconds', epoch_id:epoch, sequence:latest.sequence, sample_period_s:10, samples:window},
};
if (git(['rev-parse','HEAD']) !== revision || git(['status','--porcelain','--untracked-files=no'])) throw new Error('Simulator source changed during export.');
const trajectoryDigest = createHash('sha256').update(JSON.stringify({samples:window, alarms:observation.alarms})).digest('hex');
// Scenario and seed are evaluator-side metadata only. Neither enters stdout.
console.error(JSON.stringify({scenario, seed:Number(seedText), revision, model_id:observation.source.model_id, trajectory_sha256:trajectoryDigest}));
process.stdout.write(JSON.stringify(observation, null, 2) + '\n');
