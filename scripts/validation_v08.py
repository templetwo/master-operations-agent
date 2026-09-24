"""Validation receipt hygiene. Commands and product behavior belong to the caller."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time
import uuid

DEFAULT_TIMEOUT_SECONDS = 600
SOURCE_PATTERNS = ("moa/**/*.py", "moa/web/*", "moa/data/*.json", "tests/**/*.py",
                   "scripts/**/*", "pyproject.toml")
POINTER_SCHEMA = "moa-validation-pointer-v1"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def fresh_output(root):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(root) / "receipts" / ("validation-" + stamp + "-" + uuid.uuid4().hex[:12])


def source_hashes(root):
    root = Path(root)
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for pattern in SOURCE_PATTERNS for path in sorted(root.glob(pattern))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
        file.write("\n")


def check_pointer(path):
    if path.is_symlink():
        raise ValueError("current pointer must not be a symlink")
    if path.exists():
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {"schema", "receipt", "sha256", "passed", "recorded_at"} or data["schema"] != POINTER_SCHEMA:
            raise ValueError("refusing to replace a file that is not a validation pointer")


def publish_pointer(path, receipt_path, receipt):
    check_pointer(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"schema": POINTER_SCHEMA, "receipt": os.path.relpath(receipt_path, path.parent),
             "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
             "passed": receipt["passed"], "recorded_at": receipt["recorded_at"]}
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".validation-pointer-", delete=False) as temporary:
        json.dump(value, temporary, indent=2)
        temporary.write("\n")
        name = temporary.name
    try:
        check_pointer(path)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _stop(process):
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()
    process.wait()


def run_validation(commands, *, root, output=None, timeout=DEFAULT_TIMEOUT_SECONDS,
                   current_pointer=None, env=None, metadata=None):
    """Run each command once. Timeouts stop the run and retain partial byte logs.

    Nonzero command exits remain failures and the other independent checks run.
    Logs are direct file handles, so timeout diagnostics are never discarded by
    a capture buffer. Output directories are exclusive, including empty ones.
    The pointer is the sole mutable artifact and must be explicitly supplied.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    commands = [list(command) for command in commands]
    if not commands or any(not command or any(not isinstance(part, str) for part in command) for command in commands):
        raise ValueError("commands must be nonempty argument lists")
    root = Path(root).resolve()
    output = (Path(output) if output is not None else fresh_output(root)).resolve()
    pointer = Path(current_pointer).resolve() if current_pointer is not None else None
    # Check unresolved path first so symlinks are not silently followed.
    if current_pointer is not None:
        check_pointer(Path(current_pointer))
        if pointer == output or output in pointer.parents:
            raise ValueError("current pointer must be outside the immutable run directory")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    receipt = {"schema": "moa-validation-v08", "started_at": utc_now(), "python": sys.version,
               "platform": platform.platform(), "timeout_seconds": timeout, "commands": [],
               "requested_commands": commands, "source_sha256": source_hashes(root),
               "metadata": dict(metadata or {}), "passed": False, "completed": False,
               "scope": "Synthetic baseline and mocked provider validation. No actual model inference or plant connection."}
    write_new(output / "started.json", receipt)
    interrupted = None
    try:
        for index, command in enumerate(commands, start=1):
            before = time.perf_counter()
            record = {"command": command, "started_at": utc_now(), "stdout": f"check-{index}.stdout",
                      "stderr": f"check-{index}.stderr", "exit_code": None, "timed_out": False,
                      "status": "launch_error"}
            process = None
            try:
                with (output / record["stdout"]).open("xb") as stdout, (output / record["stderr"]).open("xb") as stderr:
                    process = subprocess.Popen(command, cwd=root, env=env, stdout=stdout, stderr=stderr,
                                               start_new_session=(os.name == "posix"))
                    try:
                        record["exit_code"] = process.wait(timeout=timeout)
                        record["status"] = "passed" if process.returncode == 0 else "failed"
                    except subprocess.TimeoutExpired:
                        _stop(process)
                        record.update(status="timeout", timed_out=True, exit_code=process.returncode)
                    except BaseException:
                        _stop(process)
                        raise
            except OSError as exc:
                record["error_type"] = type(exc).__name__
            except BaseException as exc:
                record.update(status="interrupted", error_type=type(exc).__name__)
                interrupted = exc
            finally:
                record["elapsed_seconds"] = time.perf_counter() - before
                for name in ("stdout", "stderr"):
                    path = output / record[name]
                    if path.exists():
                        record[name + "_bytes"] = path.stat().st_size
                        record[name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                receipt["commands"].append(record)
                write_new(output / f"check-{index}.json", record)
            print(f"{record['status'].upper()} {' '.join(command)}", flush=True)
            if record["status"] in {"timeout", "launch_error", "interrupted"}:
                break
    finally:
        receipt["recorded_at"] = utc_now()
        receipt["elapsed_seconds"] = time.perf_counter() - started
        receipt["source_sha256_after"] = source_hashes(root)
        receipt["source_unchanged"] = receipt["source_sha256"] == receipt["source_sha256_after"]
        receipt["completed"] = len(receipt["commands"]) == len(commands) and all(r["status"] in {"passed", "failed"} for r in receipt["commands"])
        receipt["passed"] = receipt["completed"] and receipt["source_unchanged"] and all(r["status"] == "passed" for r in receipt["commands"])
        receipt["unattempted_commands"] = len(commands) - len(receipt["commands"])
        receipt_path = output / "validation.json"
        write_new(receipt_path, receipt)
        if pointer is not None:
            publish_pointer(pointer, receipt_path, receipt)
    if interrupted is not None:
        raise interrupted
    return receipt
