'use strict';
// Operator boundary: the only simulator projection consumed here is subject.
const path = require('node:path');
const crypto = require('node:crypto');
const PROFILE = 'ess-u1-stream-v1';
const TAGS = Object.freeze(['FI100', 'LIC101', 'FIC102', 'TIC201', 'TIC202']);
const POINT_FIELDS = Object.freeze(['tag', 'value_milli', 'unit', 'sample_tick', 'sample_sim_time_ms', 'mode', 'sp_milli', 'op_milli', 'control_revision']);
const ALARM_FIELDS = Object.freeze(['episode_id', 'target', 'condition', 'priority', 'active', 'acknowledged', 'first_observed_sim_ms']);
function selected(source, names) {
  const out = {};
  for (const key of names) {
    if (!Object.hasOwn(source, key)) throw new Error('Missing allowed field: ' + key);
    const value = source[key];
    if (value !== null && !['string', 'number', 'boolean'].includes(typeof value)) throw new Error('Non-scalar allowed field: ' + key);
    if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Nonfinite allowed field: ' + key);
    out[key] = value;
  }
  return out;
}
function allowlist(subject, profile = PROFILE) {
  if (profile !== PROFILE) throw new Error('Unknown stream profile');
  const points = TAGS.map(tag => {
    const matches = subject.points.filter(point => point.tag === tag);
    if (matches.length !== 1) throw new Error('Required point must occur exactly once');
    const point = selected(matches[0], POINT_FIELDS);
    if (!['GOOD', 'BAD'].includes(matches[0].quality)) throw new Error('Unknown source quality');
    point.source_quality = matches[0].quality;
    if (point.source_quality === 'BAD') point.value_milli = null;
    return point;
  });
  return {
    ...selected(subject, ['tick', 'sim_time_ms', 'alarms_total_matched', 'alarms_omitted']),
    points,
    alarms: subject.alarms.map(alarm => selected(alarm, ALARM_FIELDS)),
  };
}
function createObserver(simRepo) {
  const {project} = require(path.join(path.resolve(simRepo), 'src/plant-projection.js'));
  return function observe(state, profile = PROFILE) {
    return allowlist(project(state, 'subject'), profile);
  };
}
// Same JSON ordering/finite-number rules as kernel.stable; capture/processing
// wall clocks are excluded recursively from reproducibility hashes only.
function canonical(value) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('Nonfinite canonical number');
    return JSON.stringify(Object.is(value, -0) ? 0 : value);
  }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
    .filter(key => !['captured_at', 'processing_ms'].includes(key) && value[key] !== undefined)
    .map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  throw new Error('Nonserializable canonical value');
}
function withoutWallClocks(value) {
  if (Array.isArray(value)) return value.map(withoutWallClocks);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value)
    .filter(([key]) => !['captured_at', 'processing_ms'].includes(key))
    .map(([key, item]) => [key, withoutWallClocks(item)]));
  return value;
}
const hash = value => crypto.createHash('sha256').update(canonical(value), 'utf8').digest('hex');
module.exports = {createObserver, allowlist, canonical, hash, withoutWallClocks, PROFILE, TAGS, POINT_FIELDS, ALARM_FIELDS};
