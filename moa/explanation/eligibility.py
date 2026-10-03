"""Section 1 and section 2 packet gates: parse, profile, reason, timestamps, leak words, excerpts, supplement."""

import json
import math
import re
from pathlib import Path

from ..contracts import Rejected, canonical, strict_json
from ..knowledge import CHECKS, FINDINGS
from .contract import (ELIGIBLE_ABSTAIN_REASONS, EXCERPT_KEYS, KERNEL_KEYS, LABELS, MAX_EXCERPT_CHARS, MAX_EXCERPTS,
                       PACKET_KEYS, PACKET_PROFILES, SUPPLEMENT_MAX_EXCERPTS, SUPPLEMENT_MAX_WORDS)

LEAK_WORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "explanation-leak-words.json"
SENTENCES = frozenset(FINDINGS.values()) | frozenset(CHECKS.values())
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T([0-9]{2}):[0-9]{2}:[0-9]{2}(\.[0-9]{3}|\.[0-9]{6})?Z")


def load_leak_words(path=LEAK_WORDS_PATH):
    return tuple(json.loads(Path(path).read_text())["words"])


def _finite(value):
    if value is None or isinstance(value, (bool, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, int):
        try:
            float(value)
        except OverflowError:
            return False
        return True
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite(item) for key, item in value.items())
    return False


def parse_gate(packet):
    """None when the packet has exactly the v1 fields and a finite JSON observation, else a category."""
    if not isinstance(packet, dict) or set(packet) != PACKET_KEYS:
        return "parse"
    if not isinstance(packet["task_id"], str) or not isinstance(packet["label"], str) or packet["label"] not in LABELS:
        return "parse"
    kernel, excerpts, observation = packet["kernel"], packet["excerpts"], packet["observation"]
    if (not isinstance(kernel, dict) or set(kernel) != KERNEL_KEYS or not isinstance(kernel["status"], str)
            or not isinstance(kernel["reason"], str) or not all(isinstance(kernel[key], list) for key in ("findings", "checks", "evidence"))):
        return "parse"
    if any(isinstance(item, dict) or (isinstance(item, str) and (item in SENTENCES or " " in item))
           for key in ("findings", "checks") for item in kernel[key]):
        return "kernel_sentences"
    if not all(isinstance(item, str) for key in ("findings", "checks", "evidence") for item in kernel[key]):
        return "parse"
    if not isinstance(excerpts, list) or len(excerpts) > MAX_EXCERPTS:
        return "parse"
    for excerpt in excerpts:
        if (not isinstance(excerpt, dict) or set(excerpt) != EXCERPT_KEYS
                or not all(isinstance(excerpt[key], str) for key in EXCERPT_KEYS) or len(excerpt["text"]) > MAX_EXCERPT_CHARS):
            return "parse"
    if not isinstance(observation, dict) or not _finite(observation):
        return "parse"
    try:
        strict_json(canonical(observation))
    except (Rejected, ValueError, TypeError, OverflowError, RecursionError):
        return "parse"
    return None


def timestamps_ok(observation):
    tags = observation.get("tags") if isinstance(observation.get("tags"), list) else []
    values = [observation.get("captured_at")] + [tag.get("observed_at") for tag in tags if isinstance(tag, dict)]
    for value in values:
        match = TIMESTAMP.fullmatch(value) if isinstance(value, str) else None
        if match is None or int(match.group(1)) > 23:
            return False
    return True


def _tokens(value):
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def _identifier_leaks(value, words):
    tokens = _tokens(value)
    for word in words:
        target = _tokens(word)
        if any(tokens[i:i + len(target)] == target for i in range(len(tokens) - len(target) + 1)):
            return True
    return False


def _text_leaks(value, words):
    lowered = value.lower()
    return any(word in lowered for word in words if "-" in word or "_" in word)


def _leak_fields(packet):
    observation = packet["observation"]
    source = observation.get("source") if isinstance(observation.get("source"), dict) else {}
    history = observation.get("history") if isinstance(observation.get("history"), dict) else {}
    identifiers = [packet["task_id"], observation.get("snapshot_id"), history.get("epoch_id"), source.get("model_id"), source.get("revision")]
    texts = []
    for alarm in observation.get("alarms") if isinstance(observation.get("alarms"), list) else []:
        if isinstance(alarm, dict):
            identifiers.append(alarm.get("id"))
            texts.extend(alarm.get(key) for key in ("condition", "priority", "state"))
    for excerpt in packet["excerpts"]:
        identifiers.extend((excerpt["source_id"], excerpt["locator"]))
        texts.append(excerpt["text"])
    return [v for v in identifiers if isinstance(v, str)], [v for v in texts if isinstance(v, str)]


def leaks(packet, words):
    identifiers, texts = _leak_fields(packet)
    return any(_identifier_leaks(value, words) for value in identifiers) or any(_text_leaks(value, words) for value in texts)


def eligibility_problem(packet, words):
    """None when a parsed packet is eligible under section 1, else a category."""
    observation, kernel = packet["observation"], packet["kernel"]
    profile = observation.get("profile")
    versions = PACKET_PROFILES.get(profile) if isinstance(profile, str) else None
    version = observation.get("schema_version")
    if versions is None or not isinstance(version, str) or version not in versions:
        return "profile"
    if kernel["status"] != "advisory" and (kernel["status"] != "abstain" or kernel["reason"] not in ELIGIBLE_ABSTAIN_REASONS):
        return "reason"
    if not timestamps_ok(observation):
        return "timestamp"
    if leaks(packet, words):
        return "leak"
    pairs = [(excerpt["source_id"], excerpt["locator"]) for excerpt in packet["excerpts"]]
    if len(set(pairs)) != len(pairs):
        return "duplicate_excerpt"
    return None


def supplement_problems(packets):
    """Package-level sizing ruling: at most 12 distinct excerpts, each at most 200 words."""
    distinct = {(excerpt["source_id"], excerpt["locator"], excerpt["text"]) for packet in packets for excerpt in packet["excerpts"]}
    problems = []
    if len(distinct) > SUPPLEMENT_MAX_EXCERPTS:
        problems.append("supplement_count")
    if any(len(text.split()) > SUPPLEMENT_MAX_WORDS for _, _, text in distinct):
        problems.append("supplement_words")
    return problems
