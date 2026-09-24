'use strict';
// Separate declared-configuration extraction, never an observation/truth tool.
const {TAGS} = require('./observe.cjs');
const TRIP_TAGS = Object.freeze({R201_HITEMP: 'TIC201', TK101_HIHI: 'LIC101', P101_TRIP: 'LIC101', P101_PERMISSIVE: 'LIC101'});
const copy = value => value === undefined ? null : JSON.parse(JSON.stringify(value));
function extractConfig(initialState, modelId, matrix) {
  const tags = {};
  for (const tag of TAGS) {
    const point = initialState.fields.L[tag];
    if (!point) throw new Error('Missing configuration point');
    const limits = (lo, hi) => point[lo] === undefined || point[hi] === undefined ? null : [point[lo], point[hi]];
    tags[tag] = {
      unit: copy(point.eu), lo: copy(point.lo), hi: copy(point.hi), alarms: copy(point.alm),
      sp_limits: limits('splolm', 'sphilm'), op_limits: limits('oplolm', 'ophilm'),
      kind: copy(point.kind), master: copy(point.master), slave: copy(point.slave),
    };
  }
  const trips = Object.entries(TRIP_TAGS).map(([id, tag]) => {
    const rows = matrix.causes.filter(cause => cause.id === id);
    if (rows.length !== 1) throw new Error('Missing named trip declaration');
    const row = rows[0];
    return {id, tag, comparator: copy(row.comparator), threshold: copy(row.threshold), unit: copy(row.eu)};
  });
  return {model_id: modelId, tags, trips};
}
function declarationDiscrepancies(config) {
  const expected = {R201_HITEMP: ['>=', 185], TK101_HIHI: ['>=', 98], P101_TRIP: ['<', 2], P101_PERMISSIVE: ['<', 5]};
  return config.trips.filter(row => row.comparator !== expected[row.id][0] || row.threshold !== expected[row.id][1])
    .map(row => ({id: row.id, expected_numeric_declaration: expected[row.id], declared_comparator: row.comparator,
      declared_threshold: row.threshold, disposition: 'Preserved the named MATRIX declaration without numeric reinterpretation.'}));
}
module.exports = {extractConfig, declarationDiscrepancies, TRIP_TAGS};
