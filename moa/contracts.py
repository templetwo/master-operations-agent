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
    keys(raw, {"schema_version", "snapshot_id", "captured_at", "profile", "source", "tags", "alarms", "alarm_coverage"}, "snapshot")
    if raw["schema_version"] != "1.0" or raw["profile"] not in PROFILES:
        raise Rejected("profile", "Unsupported observation version or profile.")
    identifier(raw["snapshot_id"])
    keys(raw["source"], {"kind", "adapter", "revision", "model_id"}, "source")
    if raw["source"]["kind"] != "synthetic":
        raise Rejected("scope", "Only synthetic research observations are supported.")
    expected_adapter = "fixtures-v1" if raw["profile"] == "demo-cooling-v1" else "ess-v1"
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
    return copy.deepcopy(raw)
