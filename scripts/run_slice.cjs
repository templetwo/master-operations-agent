#!/usr/bin/env node
'use strict';
// Operator-run, synthetic generation harness. Never registered as an MOA tool.
const fs = require('node:fs');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {once} = require('node:events');
const crypto = require('node:crypto');
const {createObserver, withoutWallClocks, PROFILE, TAGS} = require('./lib/observe.cjs');
const {extractConfig, declarationDiscrepancies} = require('./lib/config.cjs');
const {createTruthRecorder} = require('./lib/runner_truth.cjs');
const ROOT = path.resolve(__dirname, '..');
const PIN = require('../moa/data/stream-v1.json');
const SEED = 20260923;
const SCENARIOS = Object.freeze([
  {name: 'normal', seconds: 600, schedule: []},
  {name: 'cooling', seconds: 360, schedule: [{tick: 120, target: 'cool', on: true}]},
  {name: 'degraded-instrument', seconds: 300, schedule: [{tick: 240, target: 'xmtr', on: true}]},
  {name: 'recovery', seconds: 600, schedule: [{tick: 120, target: 'cool', on: true}, {tick: 320, target: 'cool', on: false}]},
  {name: 'invariance-twin', seconds: 420, schedule: [{tick: 600, target: 'cool', on: true}]},
]);
function options(argv) {
  const out = {consumer: true};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--no-consumer') out.consumer = false;
    else if (['--sim-repo', '--output'].includes(argv[i]) && argv[i + 1]) out[argv[i++].slice(2)] = argv[i];
    else throw new Error('Usage: node scripts/run_slice.cjs --sim-repo PATH --output NEWDIR [--no-consumer]');
  }
  if (!out['sim-repo'] || !out.output) throw new Error('Both --sim-repo and --output are required');
  return out;
}
function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', {flag: 'wx', mode: 0o600});
}
function shuffle(values) {
  // Runner-only ordering, independent from the simulator random source.
  let state = SEED >>> 0;
  const random = () => {state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296;};
  const result = values.slice();
  for (let i = result.length - 1; i > 0; i--) {const j = Math.floor(random() * (i + 1)); [result[i], result[j]] = [result[j], result[i]];}
  return result;
}
function cleanRevision(repo) {
  const revision = execFileSync('git', ['-C', repo, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
  const dirty = execFileSync('git', ['-C', repo, 'status', '--porcelain', '--untracked-files=all'], {encoding: 'utf8'}).trim();
  if (revision !== PIN.sim_revision || dirty) throw new Error('A clean pinned simulator checkout is required');
  return revision;
}
async function generate(args) {
  const repo = path.resolve(args['sim-repo']);
  const output = path.resolve(args.output);
  cleanRevision(repo);
  if (process.versions.node.split('.').slice(0, 2).join('.') !== PIN.node) throw new Error('Pinned Node major.minor is required');
  const modelId = require(path.join(repo, 'src/model-id.js'));
  if (modelId !== PIN.model_id) throw new Error('Model ID differs from stream pin');
  const kernel = require(path.join(repo, 'src/plant-kernel.js'));
  const stable = value => kernel.stable(withoutWallClocks(value));
  const simHash = value => crypto.createHash('sha256').update(stable(value), 'utf8').digest('hex');
  const matrix = require(path.join(repo, 'src/cause-effect.js')).MATRIX;
  const observe = createObserver(repo);
  const initial = kernel.create({seed: SEED, sim_time_ms: 0});
  const config = extractConfig(initial, modelId, matrix);
  fs.mkdirSync(output, {mode: 0o700}); // Refuse replacement of any existing output.
  const runnerRoot = path.join(output, 'runner'), streamRoot = path.join(output, 'stream');
  fs.mkdirSync(runnerRoot, {mode: 0o700}); fs.mkdirSync(streamRoot, {mode: 0o700});
  writeJson(path.join(streamRoot, 'config.json'), config);
  const ordered = shuffle(SCENARIOS);
  writeJson(path.join(runnerRoot, 'manifest.json'), {
    schema: 'moa-synthetic-slice-generation-v1', seed: SEED, sim_revision: PIN.sim_revision, model_id: modelId,
    runs: ordered.map((scenario, i) => ({run: 'run-' + String(i + 1).padStart(2, '0'), scenario: scenario.name,
      duration_s: scenario.seconds, schedule: scenario.schedule})),
    limits: 'Development slice only. Provisional labels; deterministic replay is not physical commissioning.',
  });
  const summaries = [];
  for (let i = 0; i < ordered.length; i++) {
    const scenario = ordered[i], name = 'run-' + String(i + 1).padStart(2, '0');
    const visible = path.join(streamRoot, name), restricted = path.join(runnerRoot, name);
    fs.mkdirSync(visible, {mode: 0o700}); fs.mkdirSync(restricted, {mode: 0o700});
    let state = kernel.clone(initial);
    const observation = {schema: '1.2', profile: PROFILE, adapter: 'ess-stream-v1', sim_revision: PIN.sim_revision,
      model_id: modelId, node: PIN.node, step_s: 0.5, sample_hz: 1, tags: [...TAGS], alarm_scope: 'plant',
      start_tick: 0, config_sha256: simHash(config), mode: 'replay'};
    writeJson(path.join(visible, 'observation.json'), observation);
    writeJson(path.join(restricted, 'generation.json'), {seed: SEED, ordered_schedule: scenario.schedule,
      sim_revision: PIN.sim_revision, model_id: modelId, node: process.versions.node,
      starting_checkpoint_sha256: simHash(state), config_declaration_discrepancies: declarationDiscrepancies(config)});
    const descriptors = {};
    for (const [key, dir, filename] of [['operator', visible, 'operator.jsonl'], ['truth', restricted, 'truth.jsonl'], ['actions', restricted, 'actions.jsonl']])
      descriptors[key] = fs.openSync(path.join(dir, filename), 'wx', 0o600);
    const truth = createTruthRecorder(repo, scenario);
    let child, done, childFailure;
    if (args.consumer) {
      child = spawn('python3', ['-m', 'moa.stream', visible, '--stdin'], {cwd: ROOT, stdio: ['pipe', 'ignore', 'pipe']});
      let errorText = '';
      child.stderr.on('data', data => {if (errorText.length < 8192) errorText += data.toString();});
      child.stdin.on('error', error => {childFailure = error;});
      done = new Promise(resolve => {
        child.once('error', error => {childFailure = error; resolve({code: null, errorText});});
        child.once('close', code => resolve({code, errorText}));
      });
    }
    const rowHash = crypto.createHash('sha256');
    let sequence = 0;
    async function sample() {
      const projected = observe(state, PROFILE);
      const row = {schema: '1.2', stream_id: simHash(observation), seq: ++sequence, tick: projected.tick,
        sim_time_ms: projected.sim_time_ms, captured_at: null, points: projected.points, alarms: projected.alarms,
        alarms_total_matched: projected.alarms_total_matched, alarms_omitted: projected.alarms_omitted};
      const line = JSON.stringify(row) + '\n';
      fs.writeSync(descriptors.operator, line);
      rowHash.update(stable(row) + '\n');
      if (child) {
        if (childFailure || child.exitCode !== null) throw new Error('Stream consumer failed before input completion');
        if (!child.stdin.write(line)) await once(child.stdin, 'drain');
      }
    }
    try {
      fs.writeSync(descriptors.truth, JSON.stringify(truth.record(state)) + '\n');
      await sample();
      for (let tick = 1; tick <= scenario.seconds * 2; tick++) {
        const commands = scenario.schedule.filter(event => event.tick === tick).map((event, index) => ({
          command_id: 'event-' + tick + '-' + index,
          call: {operation: 'instructor.upset', arguments: {target: event.target, on: event.on}},
          principal: {id: 'slice-generator', role: 'instructor'},
        }));
        const next = kernel.advance(state, 0.5, commands);
        if (next.outcomes.some(outcome => !['applied', 'no_effect'].includes(outcome.status))) throw new Error('Scheduled generation command rejected');
        state = next.state;
        fs.writeSync(descriptors.truth, JSON.stringify(truth.record(state)) + '\n');
        if (commands.length) fs.writeSync(descriptors.actions, JSON.stringify({tick, commands, outcomes: next.outcomes}) + '\n');
        if (tick % 2 === 0) await sample();
      }
      if (child) {
        child.stdin.end();
        const result = await done;
        if (result.code !== 0 || childFailure) throw new Error('Stream consumer failed: ' + result.errorText);
      }
      writeJson(path.join(restricted, 'labels.json'), truth.labels);
      summaries.push({run: name, samples: sequence, operator_canonical_sha256: rowHash.digest('hex')});
    } finally {
      for (const fd of Object.values(descriptors)) fs.closeSync(fd);
      if (child && child.exitCode === null) child.kill('SIGTERM');
    }
  }
  cleanRevision(repo);
  writeJson(path.join(runnerRoot, 'completion.json'), {completed: true, consumer: args.consumer, runs: summaries});
  return {completed: true, consumer: args.consumer, run_count: summaries.length, samples: summaries.reduce((sum, run) => sum + run.samples, 0)};
}
if (require.main === module) generate(options(process.argv.slice(2))).then(result => process.stdout.write(JSON.stringify(result) + '\n')).catch(error => {console.error(error.message); process.exitCode = 1;});
module.exports = {generate, options, SCENARIOS, SEED, shuffle, cleanRevision};
