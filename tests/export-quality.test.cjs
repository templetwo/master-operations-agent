'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {sourceQuality} = require('../scripts/lib/quality.cjs');

test('legacy quality conversion never upgrades a declared non-good PV', () => {
  assert.equal(sourceQuality({pv: 103.125, quality: 'UNCERTAIN'}), 'uncertain');
  assert.equal(sourceQuality({pv: 45, quality: 'STALE'}), 'uncertain');
  assert.equal(sourceQuality({pv: 45, quality: 'unknown'}), 'uncertain');
  assert.equal(sourceQuality({pv: 45, quality: 'BAD'}), 'bad');
  assert.equal(sourceQuality({pv: 45, quality: 'GOOD', badPv: true}), 'bad');
  assert.equal(sourceQuality({pv: null, quality: 'UNCERTAIN'}), 'bad');
  assert.equal(sourceQuality({pv: 45}), 'good');
});

// Exercise each actual CLI conversion with a declared fake projection. This is
// an adapter boundary test, not a simulated-process or pinned-export result.
function runExporter(file, flags = [], changeRows = () => {}, revisionAfter = 'a'.repeat(40)) {
  let output = '';
  let revisionReads = 0;
  const rows = ['TIC201', 'TIC202', 'FIC102', 'LIC101'].map(tag => ({
    tag, pv: tag === 'TIC202' ? 103.125 : 40, op: 100, eu: tag.startsWith('TIC') ? 'DEG C' : '%',
    quality: tag === 'TIC202' ? 'UNCERTAIN' : 'GOOD', badPv: false,
    kind: 'pid', sp: tag === 'TIC201' ? 150 : 40,
    mode: tag === 'TIC202' ? 'CAS' : tag === 'FIC102' ? 'MAN' : 'AUTO',
    hidden_fault: 'FORBIDDEN'
  }));
  changeRows(rows);
  class Component {
    constructor() { this.alarmEngine = {list: () => []}; }
    initSim() {} applyPreset() {} setSeed() {} step() {} setUpset() {}
    coachProjection() { return {catalog: rows, alarms: []}; }
  }
  const context = {
    require(name) {
      if (name === 'node:child_process') return {execFileSync: (_cmd, args) =>
        args.includes('rev-parse') ? (++revisionReads === 1 ? 'a'.repeat(40) : revisionAfter) : ''};
      if (name.endsWith('logic-harness.js')) return {load: () => ({Component})};
      if (name.endsWith('model-id.js')) return 'b'.repeat(64);
      if (name === './lib/quality.cjs') return {sourceQuality};
      return require(name);
    },
    process: {argv: ['node', file, '/trusted/fake-sim', 'normal', ...flags], stdout: {write: text => {output += text;}}, exit(code) {throw Error('exit ' + code);}},
    console: {error() {}},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'scripts', file), 'utf8'), context, {filename: file});
  return JSON.parse(output);
}

test('both legacy CLI schemas retain uncertain TIC202 and independent output quality', () => {
  for (const file of ['export_sim.cjs', 'export_trajectory.cjs']) {
    const observation = runExporter(file);
    const pv = observation.tags.find(row => row.id === 'TIC202');
    assert.equal(pv.quality, 'uncertain');
    assert.equal(pv.value, 103.125);
    if (observation.history) {
      for (const sample of observation.history.samples) {
        assert.equal(sample.quality.TIC202, 'uncertain');
        assert.equal(sample.values.TIC202, 103.125);
        assert.equal(sample.quality['TIC202.OP'], 'good');
      }
    }
  }
});

test('snapshot 1.3 exports actual PID setpoint, output and categorical mode through an exact allowlist', () => {
  const observation = runExporter('export_sim.cjs');
  assert.equal(observation.schema_version, '1.3');
  assert.deepEqual(observation.loops.find(row => row.tag === 'TIC202'), {
    tag: 'TIC202', sp: 40, op: 100, mode: 'CAS', sp_unit: 'DEG C', op_unit: '%'
  });
  assert.equal(observation.loops.find(row => row.tag === 'FIC102').mode, 'MAN');
  assert.equal(observation.loops.find(row => row.tag === 'TIC201').mode, 'AUTO');
  assert.equal(JSON.stringify(observation).includes('FORBIDDEN'), false);
  const legacy = runExporter('export_sim.cjs', ['--legacy']);
  assert.equal(legacy.schema_version, '1.0');
  assert.equal(Object.hasOwn(legacy, 'loops'), false);
});

test('snapshot export refuses missing or malformed controller evidence instead of inventing context', () => {
  for (const patch of [{sp: null}, {op: NaN}, {mode: 'UNKNOWN'}, {kind: 'ind'}]) {
    assert.throws(() => runExporter('export_sim.cjs', [], rows => Object.assign(rows[1], patch)), /controller context/);
  }
});

test('both exporters refuse a source revision that changes during observation', () => {
  for (const file of ['export_sim.cjs', 'export_trajectory.cjs']) {
    assert.throws(() => runExporter(file, [], () => {}, 'b'.repeat(40)), /Simulator source changed during export/);
  }
});
