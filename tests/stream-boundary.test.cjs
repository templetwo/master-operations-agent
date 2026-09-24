'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {allowlist, TAGS, hash} = require('../scripts/lib/observe.cjs');
const {extractConfig} = require('../scripts/lib/config.cjs');
const {SCENARIOS, shuffle, options} = require('../scripts/run_slice.cjs');
function board() {
  return {tick: 0, sim_time_ms: 0, alarms_total_matched: 1, alarms_omitted: 0,
    points: TAGS.map(tag => ({tag, value_milli: 1000, unit: '%', quality: 'GOOD', sample_tick: 0,
      sample_sim_time_ms: 0, mode: null, sp_milli: null, op_milli: null, control_revision: 0})),
    alarms: [{episode_id: 'alarm.1', target: 'TIC201.PVHI', condition: 'PVHI', priority: 'High', active: true,
      acknowledged: false, first_observed_sim_ms: 0}]};
}
test('observer output ignores forbidden objects and point/alarm extras without aliases', () => {
  const clean = board(), modified = structuredClone(clean);
  for (const key of ['station', 'instructor', 'focus', 'product', 'batch', 'trend_windows', 'public_messages', 'seed', 'schedule']) modified[key] = {secret: 'FORBIDDEN'};
  modified.points.forEach(point => {point.faults = {secret: 'FORBIDDEN'}; point.age_sim_ms = 999;});
  modified.alarms[0].text = 'FORBIDDEN';
  assert.deepEqual(allowlist(modified), allowlist(clean));
  const result = allowlist(modified); result.points[0].unit = 'changed';
  assert.equal(modified.points[0].unit, '%');
});
test('BAD values become null while source quality remains explicit', () => {
  const data = board(); data.points[2].quality = 'BAD';
  const point = allowlist(data).points[2];
  assert.equal(point.source_quality, 'BAD'); assert.equal(point.value_milli, null);
  assert.equal(point.sample_tick, 0); assert.equal(point.sample_sim_time_ms, 0);
});
test('ambiguous, missing or nested point values fail the observation boundary', () => {
  const data = board(); data.points.push(data.points[0]); assert.throws(() => allowlist(data), /exactly once/);
  data.points.pop(); data.points[0].mode = {seed: 1}; assert.throws(() => allowlist(data), /Non-scalar/);
  data.points[0].mode = null; delete data.points[0].sample_tick; assert.throws(() => allowlist(data), /Missing/);
});
test('config extracts only named fields and preserves descriptive trip declarations', () => {
  const state = {fields: {L: Object.fromEntries(TAGS.map(tag => [tag, {eu: '%', lo: 0, hi: 100, alm: {PVHI: [80, 'High']}, kind: 'ind', faults: 'FORBIDDEN'}]))}};
  const matrix = {causes: ['R201_HITEMP', 'TK101_HIHI', 'P101_TRIP', 'P101_PERMISSIVE'].map(id => ({id, comparator: 'latched by', threshold: 'declared text', eu: '', secret: 'FORBIDDEN'}))};
  const result = extractConfig(state, 'a'.repeat(64), matrix);
  assert.equal(JSON.stringify(result).includes('FORBIDDEN'), false);
  assert.equal(result.tags.FI100.sp_limits, null); assert.equal(result.tags.FI100.master, null);
  assert.equal(result.trips.length, 4); assert.equal(result.trips[2].threshold, 'declared text');
});
test('canonical hashes recursively exclude only the two wall clock fields', () => {
  assert.equal(hash({z: -0, a: {captured_at: 'x', processing_ms: 1, tick: 2}}), hash({a: {tick: 2, processing_ms: 20, captured_at: 'y'}, z: 0}));
  assert.notEqual(hash({tick: 2}), hash({tick: 4}));
  assert.throws(() => hash({value: Infinity}));
});
test('fixed scenario schedules use ending tick and deterministic opaque ordering', () => {
  assert.equal(SCENARIOS.find(s => s.name === 'cooling').schedule[0].tick, 120);
  assert.equal(SCENARIOS.find(s => s.name === 'recovery').schedule[1].tick, 320);
  assert.equal(SCENARIOS.find(s => s.name === 'invariance-twin').schedule[0].tick, 600);
  assert.deepEqual(shuffle(SCENARIOS), shuffle(SCENARIOS));
  assert.notDeepEqual(shuffle(SCENARIOS), SCENARIOS);
  assert.deepEqual(options(['--sim-repo', '/sim', '--output', '/new', '--no-consumer']), {consumer: false, 'sim-repo': '/sim', output: '/new'});
});
const simRepo = process.env.MOA_STREAM_SIM_REPO;
test('pinned subject projection ignores changes to hidden checkpoint truth and future schedules', {skip: !simRepo}, () => {
  const path = require('node:path');
  const kernel = require(path.join(simRepo, 'src/plant-kernel.js'));
  const {createObserver} = require('../scripts/lib/observe.cjs');
  const observe = createObserver(simRepo);
  const state = kernel.create({seed: 20260923, sim_time_ms: 0});
  const altered = kernel.clone(state);
  altered.fields.P.faults.hidden_marker = 'FORBIDDEN';
  altered.fields.P.env.hidden_marker = 'FORBIDDEN';
  altered.fields.P.archFaults.hidden_marker = 'FORBIDDEN';
  altered.fields.P.archPending.push({hidden_marker: 'FORBIDDEN'});
  altered.instructor.hidden_marker = 'FORBIDDEN';
  altered.fields.L.FIC102.hidden_marker = 'FORBIDDEN';
  altered.fields.msgs.push({src: 'OPERATOR', txt: 'FORBIDDEN', id: 700});
  altered.focus = {hidden_marker: 'FORBIDDEN'};
  assert.deepEqual(observe(altered), observe(state));
  assert.equal(JSON.stringify(observe(altered)).includes('FORBIDDEN'), false);
});
test('observer canonical form matches kernel stable after wall clock removal', {skip: !simRepo}, () => {
  const path = require('node:path');
  const kernel = require(path.join(simRepo, 'src/plant-kernel.js'));
  const {canonical, withoutWallClocks, createObserver} = require('../scripts/lib/observe.cjs');
  const state = kernel.create({seed: 20260923, sim_time_ms: 0});
  const value = {observation: createObserver(simRepo)(state), captured_at: 'wall', nested: {processing_ms: 5, text: 'é', number: -0}};
  assert.equal(canonical(value), kernel.stable(withoutWallClocks(value)));
  assert.ok(Object.hasOwn(state, 'rand')); assert.ok(Object.hasOwn(state, 'rand4'));
  assert.equal(state.fields.seed, 20260923);
  assert.equal(kernel.stable(kernel.capture(kernel.restore(state))), kernel.stable(state));
});
