"""Canary: private identifiers and text never reach stdout, stderr or a public object, even on failure."""
import contextlib
import io
import json
import unittest

from explanation_packets import packet
from moa.explanation.evaluate import evaluate
from moa.explanation.preflight import Refused, preflight
from moa.explanation.review import public_report, review_sheet, tally

SENTINEL = "SNTLq7x9"
FREEZE = {"prompt_sha256": "p" * 64, "model_id": "toy", "model_digest": "d" * 64, "decoding_sha256": "s" * 64, "schema_sha256": "o" * 64}
MANIFEST = {"catalog_commit": "68cb08c", "manifest_sha256": "m" * 64, "review_sha256": "r" * 64, "grid_sha256": "g" * 64,
            "validation_clocks": {}, "author_python": "3.10.12"}


class PrivacyCanaryTests(unittest.TestCase):
    def test_sentinel_never_escapes(self):
        excerpt = {"source_id": f"https://example.org/{SENTINEL}", "locator": f"p-{SENTINEL}", "text": f"{SENTINEL} private excerpt text."}
        packets = [packet(task_id=f"t-{SENTINEL}", excerpts=[excerpt])]

        def model(view):
            raise RuntimeError(f"{SENTINEL} boom")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            checked = preflight(packets, MANIFEST)
            run = evaluate(packets, MANIFEST, checked, model=model, model_freeze=FREEZE)
            sheet, key = review_sheet(run, "salt")
            verdicts = {"rows": {row["row_id"]: {**{c: "pass" for c in "123456"}, "abstention": None} for row in sheet["rows"]}, "pairs": {}}
            report = public_report(run, tally(run, key, verdicts))
            try:
                preflight(packets, dict(MANIFEST, review_sha256=None))
            except Refused as exc:
                refusal = str(exc)
        self.assertTrue(checked["public"]["runnable"])
        self.assertEqual([r["failure"] for r in run["private"]["rows"] if r["candidate"] == "model"], ["exception"])
        for public in (out.getvalue(), err.getvalue(), json.dumps(checked["public"]), json.dumps(run["public"]), json.dumps(report), refusal):
            self.assertNotIn(SENTINEL, public)
        self.assertNotIn(SENTINEL, json.dumps([r["failure"] for r in run["private"]["rows"]]))


if __name__ == "__main__":
    unittest.main()
