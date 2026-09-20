"""Strict input contracts. Freshness is checked again before releasing advice."""

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone

MAX_BYTES = 262144
MAX_AGE_SECONDS = 60
FUTURE_SKEW_SECONDS = 2
PROFILES = {
    "demo-cooling-v1": {"TT101": "degC", "FT102": "L/min"},
    "ess-u1-v1": {"TIC201": "DEG C", "TIC202": "DEG C", "FIC102": "M3/H"},
    "ess-u1-window-v1": {"TIC201": "DEG C", "TIC202": "DEG C", "FIC102": "M3/H", "LIC101": "%", "TIC202.OP": "%"},
}


class Rejected(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code, self.detail = code, detail


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(text):
    if len(text.encode() if isinstance(text, str) else text) > MAX_BYTES:
        raise Rejected("size_limit", "JSON exceeds the input limit.")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise Rejected("duplicate_key", "Duplicate JSON key.")
            out[key] = value
        return out

    def constant(_):
        raise Rejected("invalid_number", "Non-finite JSON number.")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, Rejected):
            raise
        raise Rejected("invalid_json", "Invalid JSON document.") from exc


def now_utc():
    return datetime.now(timezone.utc)


def stamp(moment=None):
    return (moment or now_utc()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp(value):
    try:
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError()
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, TypeError):
        raise Rejected("timestamp", "A UTC timestamp ending in Z is required.") from None


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise Rejected("schema", f"Unexpected or missing fields in {label}.")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value):
        raise Rejected("identifier", "Invalid identifier.")


def text_field(value, limit=160):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise Rejected("schema", "Invalid text field.")


def validate_snapshot(raw, now=None):
    now = now or now_utc()
    windowed = isinstance(raw, dict) and raw.get("schema_version") == "1.1"
    fields = {"schema_version", "snapshot_id", "captured_at", "profile", "source", "tags", "alarms", "alarm_coverage"}
    keys(raw, fields | ({"history"} if windowed else set()), "snapshot")
    if raw["schema_version"] not in ("1.0", "1.1") or not isinstance(raw["profile"], str) or raw["profile"] not in PROFILES:
        raise Rejected("profile", "Unsupported observation version or profile.")
    if windowed != (raw["profile"] == "ess-u1-window-v1"):
        raise Rejected("profile", "History profile and schema version disagree.")
    identifier(raw["snapshot_id"])
    keys(raw["source"], {"kind", "adapter", "revision", "model_id"}, "source")
    if raw["source"]["kind"] != "synthetic":
        raise Rejected("scope", "Only synthetic research observations are supported.")
    expected_adapter = "ess-window-v1" if windowed else ("fixtures-v1" if raw["profile"] == "demo-cooling-v1" else "ess-v1")
    if raw["source"]["adapter"] != expected_adapter:
        raise Rejected("profile", "Adapter and observation profile disagree.")
    for field in ("revision", "model_id"):
        identifier(raw["source"][field])
    captured = timestamp(raw["captured_at"])
    age = (now - captured).total_seconds()
    if age < -FUTURE_SKEW_SECONDS:
        raise Rejected("future", "Observation timestamp is in the future.")
    if age > MAX_AGE_SECONDS:
        raise Rejected("stale", "Observation is older than the 60-second lab freshness budget.")
    if raw["alarm_coverage"] != "complete":
        raise Rejected("incomplete", "Alarm coverage is not complete.")
    if not isinstance(raw["tags"], list) or not 1 <= len(raw["tags"]) <= 128:
        raise Rejected("schema", "Expected 1 to 128 tags.")
    seen = {}
    for tag in raw["tags"]:
        keys(tag, {"id", "value", "unit", "quality", "observed_at"}, "tag")
        identifier(tag["id"])
        if tag["id"] in seen:
            raise Rejected("conflict", "Duplicate tag observations cannot be reconciled.")
        if tag["quality"] != "good":
            raise Rejected("quality", f"Unusable quality for {tag['id']}.")
        if type(tag["value"]) not in (int, float) or not math.isfinite(tag["value"]):
            raise Rejected("invalid_number", "Tag value must be a finite number.")
        text_field(tag["unit"], 24)
        observed = timestamp(tag["observed_at"])
        if observed > captured or (captured - observed).total_seconds() > 5:
            raise Rejected("incoherent", "Tag times are not coherent with this snapshot.")
        if (now - observed).total_seconds() > MAX_AGE_SECONDS:
            raise Rejected("stale", "A tag is older than the freshness budget.")
        seen[tag["id"]] = tag
    for tag, unit in PROFILES[raw["profile"]].items():
        if tag not in seen:
            raise Rejected("incomplete", f"Required tag {tag} is missing.")
        if seen[tag]["unit"] != unit:
            raise Rejected("units", f"Unexpected engineering unit for {tag}.")
    if not isinstance(raw["alarms"], list) or len(raw["alarms"]) > 128:
        raise Rejected("schema", "Invalid alarm list.")
    alarm_ids = set()
    for alarm in raw["alarms"]:
        keys(alarm, {"id", "tag", "condition", "priority", "state"}, "alarm")
        identifier(alarm["id"])
        identifier(alarm["tag"])
        if alarm["id"] in alarm_ids:
            raise Rejected("conflict", "Duplicate alarm identifiers.")
        alarm_ids.add(alarm["id"])
        for field in ("condition", "priority", "state"):
            text_field(alarm[field], 48)
        # Equipment alarms need not refer to an analog tag. They are reported
        # indications only, never interpreted as measured process values.
    if windowed:
        validate_history(raw["history"], seen)
    return copy.deepcopy(raw)


def validate_history(history, tags):
    keys(history, {"clock", "epoch_id", "sequence", "sample_period_s", "samples"}, "history")
    if history["clock"] != "simulation_seconds":
        raise Rejected("history_clock", "History must declare a simulation clock.")
    identifier(history["epoch_id"])
    if type(history["sequence"]) is not int or not 0 <= history["sequence"] <= 2**53:
        raise Rejected("history_sequence", "Invalid source sequence.")
    period = history["sample_period_s"]
    if type(period) not in (int, float) or not math.isfinite(period) or not 1 <= period <= 60:
        raise Rejected("history_timing", "Invalid sampling interval.")
    samples = history["samples"]
    if not isinstance(samples, list) or not 4 <= len(samples) <= 25:
        raise Rejected("history_incomplete", "A bounded window of 4 to 25 samples is required.")
    required = PROFILES["ess-u1-window-v1"]
    previous = None
    for sample in samples:
        keys(sample, {"sequence", "elapsed_s", "values", "quality"}, "history sample")
        if type(sample["sequence"]) is not int or not 0 <= sample["sequence"] <= 2**53:
            raise Rejected("history_sequence", "Invalid sample sequence.")
        elapsed = sample["elapsed_s"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise Rejected("history_timing", "Invalid simulation time.")
        if previous is not None:
            if sample["sequence"] != previous["sequence"] + 1:
                raise Rejected("history_sequence", "History contains a sequence gap, duplicate, or reversal.")
            if not math.isclose(elapsed - previous["elapsed_s"], period, rel_tol=0, abs_tol=0.000001):
                raise Rejected("history_timing", "History sample times do not match the declared interval.")
        keys(sample["values"], required, "history values")
        keys(sample["quality"], required, "history quality")
        for tag, value in sample["values"].items():
            quality = sample["quality"][tag]
            if quality not in ("good", "bad", "uncertain"):
                raise Rejected("history_quality", "Unknown historical quality.")
            if value is None and quality != "good":
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                raise Rejected("invalid_number", "Historical values must be finite or explicitly unavailable.")
        previous = sample
    span = samples[-1]["elapsed_s"] - samples[0]["elapsed_s"]
    if not 30 <= span <= 240:
        raise Rejected("history_incomplete", "History must cover 30 to 240 simulation seconds.")
    if samples[-1]["sequence"] != history["sequence"]:
        raise Rejected("history_sequence", "History head sequence disagrees with its last sample.")
    for tag in required:
        if samples[-1]["values"][tag] != tags[tag]["value"] or samples[-1]["quality"][tag] != tags[tag]["quality"]:
            raise Rejected("history_mismatch", "Current observation disagrees with the final history sample.")
