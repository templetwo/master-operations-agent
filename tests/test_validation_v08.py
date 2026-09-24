"""Public toy subprocess checks for receipt hygiene. No provider or simulator."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

from scripts.validation_v08 import DEFAULT_TIMEOUT_SECONDS, run_validation, source_hashes


class ValidationV08Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="moa-validation-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def command(self, code):
        return [sys.executable, "-c", code]

    def test_default_timeout_and_recursive_sources(self):
        source = self.root / "scripts/lib/observer.cjs"
        source.parent.mkdir(parents=True)
        source.write_text("// public toy source\n")
        receipt = run_validation([self.command("print('ok')")], root=self.root)
        self.assertEqual(DEFAULT_TIMEOUT_SECONDS, 600)
        self.assertEqual(receipt["timeout_seconds"], 600)
        self.assertTrue(receipt["passed"])
        self.assertTrue(receipt["source_unchanged"])
        self.assertGreater(receipt["commands"][0]["elapsed_seconds"], 0)
        self.assertEqual(receipt["source_sha256"]["scripts/lib/observer.cjs"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(receipt["source_sha256"], source_hashes(self.root))

    def test_timeout_preserves_partial_output_and_final_failure(self):
        output = self.root / "run"
        pointer = self.root / "current.json"
        receipt = run_validation([
            self.command("import sys,time; print('partial stdout', flush=True); print('partial stderr', file=sys.stderr, flush=True); time.sleep(10)"),
            self.command("raise AssertionError('must not run')")],
            root=self.root, output=output, timeout=0.15, current_pointer=pointer)
        self.assertFalse(receipt["passed"])
        self.assertFalse(receipt["completed"])
        self.assertEqual(receipt["unattempted_commands"], 1)
        step = receipt["commands"][0]
        self.assertEqual(step["status"], "timeout")
        self.assertTrue(step["timed_out"])
        self.assertGreaterEqual(step["elapsed_seconds"], 0.15)
        self.assertIn("partial stdout", (output / step["stdout"]).read_text())
        self.assertIn("partial stderr", (output / step["stderr"]).read_text())
        self.assertEqual(json.loads((output / "validation.json").read_text()), receipt)
        self.assertEqual(json.loads((output / "check-1.json").read_text()), step)
        self.assertFalse(json.loads(pointer.read_text())["passed"])
        self.assertFalse((output / "check-2.stdout").exists())

    def test_nonzero_exit_is_failure_but_independent_check_runs(self):
        receipt = run_validation([self.command("raise SystemExit(7)"), self.command("print('next')")],
                                 root=self.root, output=self.root / "run")
        self.assertTrue(receipt["completed"])
        self.assertFalse(receipt["passed"])
        self.assertEqual([r["status"] for r in receipt["commands"]], ["failed", "passed"])
        self.assertEqual(receipt["commands"][0]["exit_code"], 7)

    def test_missing_executable_writes_failure_receipt(self):
        output = self.root / "run"
        receipt = run_validation([[str(self.root / "does-not-exist")]], root=self.root, output=output)
        self.assertFalse(receipt["passed"])
        self.assertFalse(receipt["completed"])
        self.assertEqual(receipt["commands"][0]["status"], "launch_error")
        self.assertTrue((output / "validation.json").exists())

    def test_existing_output_refused_and_pointer_rotates_only_index(self):
        pointer = self.root / "current.json"
        first = self.root / "first"
        run_validation([self.command("print('first')")], root=self.root, output=first, current_pointer=pointer)
        saved = {p.name: p.read_bytes() for p in first.iterdir()}
        with self.assertRaises(FileExistsError):
            run_validation([self.command("print('overwrite')")], root=self.root, output=first)
        second = self.root / "second"
        run_validation([self.command("print('second')")], root=self.root, output=second, current_pointer=pointer)
        self.assertEqual(saved, {p.name: p.read_bytes() for p in first.iterdir()})
        pointed = json.loads(pointer.read_text())
        self.assertEqual(pointed["receipt"], "second/validation.json")
        self.assertEqual(pointed["sha256"], hashlib.sha256((second / "validation.json").read_bytes()).hexdigest())
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(FileExistsError):
            run_validation([self.command("pass")], root=self.root, output=empty)

    def test_invalid_timeout_or_pointer_never_starts_run(self):
        for index, timeout in enumerate((True, 0, -1, float("inf"), float("nan"), "600")):
            output = self.root / f"bad-{index}"
            with self.assertRaises(ValueError):
                run_validation([self.command("pass")], root=self.root, output=output, timeout=timeout)
            self.assertFalse(output.exists())
        pointer = self.root / "existing.json"
        pointer.write_text('{"historical":"receipt"}\n')
        saved = pointer.read_bytes()
        with self.assertRaises(ValueError):
            run_validation([self.command("pass")], root=self.root, output=self.root / "bad-pointer", current_pointer=pointer)
        self.assertEqual(pointer.read_bytes(), saved)
        link = self.root / "link.json"
        link.symlink_to(pointer)
        with self.assertRaises(ValueError):
            run_validation([self.command("pass")], root=self.root, output=self.root / "bad-link", current_pointer=link)

    def test_source_drift_invalidates_successful_command(self):
        source = self.root / "scripts/new.py"
        source.parent.mkdir()
        source.write_text("original\n")
        receipt = run_validation([self.command("from pathlib import Path; Path('scripts/new.py').write_text('changed\\n')")],
                                 root=self.root, output=self.root / "run")
        self.assertTrue(receipt["completed"])
        self.assertFalse(receipt["source_unchanged"])
        self.assertFalse(receipt["passed"])

    def test_profile_records_every_actual_append_and_refuses_overwrite(self):
        root = Path(__file__).resolve().parents[1]
        output = self.root / "profile.json"
        command = [sys.executable, str(root / "scripts/profile_evidence.py"), "--count", "3", "--output", str(output)]
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = json.loads(output.read_text())
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["completed_appends"], 3)
        self.assertEqual(receipt["anchor"]["events"], 3)
        self.assertEqual([row["append"] for row in receipt["measurements"]], [1, 2, 3])
        self.assertTrue(all(row["elapsed_seconds"] > 0 for row in receipt["measurements"]))
        self.assertEqual(receipt["command"], command)
        self.assertEqual(receipt["source_sha256"]["moa/evidence.py"], hashlib.sha256((root / "moa/evidence.py").read_bytes()).hexdigest())
        original = output.read_bytes()
        repeated = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
