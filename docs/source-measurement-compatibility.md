# Source measurement quality compatibility

The source-map revision 2 observation layer reports a synthetic TIC202 transmitter
at 103.125 °C with `UNCERTAIN` quality when its input exceeds that reporting limit.
The simulator controller and stored process replay remain separate from this
measurement projection.

The schema 1.2 stream accepts the source quality families `GOOD`, `UNCERTAIN`, and
`BAD`. Uncertain integer values remain visible evidence. Only Good values support
the policy's numerical findings; an uncertain measurement produces a distinct
notice and immediately invalidates dependent cached trends. Unrelated alarm and
output indications retain their existing scoped treatment. The Good 170600
milli-unit over-range test remains applicable to older projections; uncertainty
does not get recast as that trusted-value range assessment.

The stream's strict point-field allowlist is unchanged. It carries the quality
family, not the source's numeric OPC StatusCode or LimitBits. Full OPC status
transport would require its own contract extension. SP, OP, and MODE already pass
through this stream; they are not new fields in this compatibility change.

Legacy snapshot and trajectory exporters preserve the lowercase `uncertain`
quality. Their existing consumer withholds advice for a non-good current snapshot
and excludes non-good history from trend conclusions. TIC202 OP has its own
finite-value validity; uncertainty of its PV does not fabricate an output fault.

## Snapshot controller context

`scripts/export_sim.cjs` now emits snapshot schema `1.3`. It adds a strict `loops`
array alongside the existing measured tags, using only PID rows from the public
coach catalog. Each row contains `tag`, numeric `sp` and `op`, categorical `mode`,
`sp_unit`, and `op_unit`. SP uses that loop's engineering unit; OP uses percent;
MODE is the simulator's existing `MAN`, `AUTO`, or `CAS` value. In CAS, SP is the
currently exported cascade setpoint. OP is a controller demand, not proof of an
achieved valve position or flow. These values carry no fabricated quality flags.
Missing or invalid required controller context causes an export error.

The updated validator accepts the context only with the existing `ess-u1-v1`
snapshot profile and `ess-v1` adapter. It rejects unknown fields, duplicate or
unobserved loop tags, absent required U1 loops, nonfinite values, wrong units,
and unknown modes. `read_snapshot` exposes the validated context through its
existing allowlisted tool. No new tool, control effect, or advisory rule is added.

Use `node scripts/export_sim.cjs /trusted/simulator normal --legacy` for the old
schema `1.0` shape without `loops`. Existing `1.0` and `1.1` inputs remain valid;
adding `loops` to those older versions is rejected. Old consumers must use the
legacy option until updated. The `1.1` trajectory format and `1.2` live stream
format are unchanged; the stream already includes SP, OP, and MODE.

No simulator pins, golden results, stored campaign results, or acceptance
denominators are changed. A future run against the revised simulator must record
its actual source revision; the earlier evaluation cannot be relabelled as a run
against this observation layer.

## Verification, September 26, 2026

Note, 2026-10-03: the `/private/tmp/experion-source-map-v2` checkout named below no longer exists. To reproduce, clone the simulator at `bfed001`; the counts are as of this date.

- `python3 -m unittest discover -s tests -v`: 178 tests, successful, 6 skipped.
  The initial sandboxed attempt could not bind the local HTTP-server test;
  the permitted rerun outside that sandbox completed. The full suite keeps
  optional source-pinned evaluation tests disabled; their original pins were
  not changed for this compatibility update.
- `MOA_STREAM_SIM_REPO=/private/tmp/experion-source-map-v2 node --test tests/stream-boundary.test.cjs tests/export-quality.test.cjs`:
  14 tests passed, including the live local subject-projection boundary tests
  and rejection of a source revision change during export.
  The legacy CLI conversions use an explicit fake projection in their tests;
  these are adapter tests, not new process-evaluation results.
- After the simulator was committed at
  `5b269fbd8cc687ab87b0d3c32416ae190b5032cd`, the real snapshot and window-export
  integration checks passed, 2/2. Command:
  `PYTHONPATH=tests MOA_SIM_REPO=/private/tmp/experion-source-map-v2 python3 -m unittest test_simulator.SimulatorTests.test_normal_and_bad_quality_operator_projection test_simulator.SimulatorTests.test_window_export_is_reproducible_without_scenario_answers -v`.
  These checks exercised schema 1.3 loop context, Good/Bad measurements, and
  deterministic schema 1.1 trajectory export from the clean source revision.

No model campaign or new stored slice evaluation was run.
