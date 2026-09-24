'use strict';
// Evaluator-side only. Never imported by the observer or Python stream consumer.
const path = require('node:path');
function createTruthRecorder(simRepo, scenario) {
  const {project} = require(path.join(path.resolve(simRepo), 'src/plant-projection.js'));
  const labels = {
    review_status: 'provisional_uncommissioned_synthetic_labels',
    event_onsets: scenario.schedule.map(event => ({tick: event.tick, target: event.target, on: event.on})),
    observable_criteria: {tic201_at_or_above_175c_first_tick: null, fic102_bad_source_quality_first_tick: null},
    reactor_trip_first_tick: null,
    limits: 'Declared event schedule and observed simulator criteria only; not independently established process truth.',
  };
  function record(state) {
    const view = project(state, 'evaluator');
    const reactor = view.points.find(point => point.tag === 'TIC201');
    const flow = view.points.find(point => point.tag === 'FIC102');
    if (reactor.value_milli >= 175000 && labels.observable_criteria.tic201_at_or_above_175c_first_tick === null)
      labels.observable_criteria.tic201_at_or_above_175c_first_tick = view.tick;
    if (flow.quality === 'BAD' && labels.observable_criteria.fic102_bad_source_quality_first_tick === null)
      labels.observable_criteria.fic102_bad_source_quality_first_tick = view.tick;
    if (view.station.P.trips.rx && labels.reactor_trip_first_tick === null) labels.reactor_trip_first_tick = view.tick;
    return {tick: view.tick, sim_time_ms: view.sim_time_ms, instructor: view.instructor, trips: view.station.P.trips};
  }
  return {record, labels};
}
module.exports = {createTruthRecorder};
