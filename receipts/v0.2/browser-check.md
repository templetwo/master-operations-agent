# Time-series browser verification

Observed 2026-09-20 UTC at `http://127.0.0.1:8765/`, using native Computer Use in Comet. A separate browser window was used after the existing window stopped exposing its page content to automation.

Verified against the running `deterministic-baseline-v2` build:

1. The workbench identifies v0.2 and labels authored observations as synthetic demonstrations.
2. The thermal-escalation scenario displays five current tags and a 13-sample, 120-second simulation window.
3. The reactor trend is visibly plotted from 150 to 174 DEG C. Switching the tag selector to TIC202 changes the plotted series and accessible description to 40 through 100 DEG C.
4. Assessment displays Supported, factual warming/output findings, the explicitly unconfirmed cooling-path hypothesis, causal uncertainty, seven evidence references, and a committed receipt.
5. The unreliable-history scenario identifies the missing indication and states that gaps are not interpolated in the chart.
6. Assessing unreliable history displays Limited, withholds trend conclusions, asks for a clean window, and retains current alarm context and causal uncertainty.

Screenshots were visually inspected for the desktop chart, text, and evidence layout. These observations do not certify mobile layout, accessibility conformance, other browsers, or real-model behavior. Actual simulator exports and the eighteen development cases were separately exercised by the automated suite.
