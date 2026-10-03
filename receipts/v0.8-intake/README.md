# v0.8 intake probe

[`projection-probe.json`](projection-probe.json) was produced by [`projection-probe.cjs`](projection-probe.cjs) on 2026-09-24 against simulator `edd9dbcbb2b175fbf57121f3265794f8a082c146`. The intake ([docs/v0.8-intake.md](../../docs/v0.8-intake.md)) did not record the command.

The probe takes the simulator checkout as its only argument and refuses any other revision. Added 2026-10-03 by the MacBook seat (claude-opus-5-5): this command, run against a clean clone at `edd9dbc`, exited 0 and reproduced every field of the recorded JSON except `checked_at`.

```sh
node receipts/v0.8-intake/projection-probe.cjs /tmp/sim-edd9dbc > /tmp/projection-probe.json
```

Paths are shown as `/tmp`; the recorded run used throwaway clones of the same revision in a job scratch directory.

The probe is one public sentinel example, as its own `limitations` field says. It is not acceptance test T1 to T11.
