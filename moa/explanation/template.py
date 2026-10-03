"""Section 6 template and the section 7 always-abstain control.

The template reads the view's kernel and catalog only. It ignores excerpts
and writes no text of its own except the one fixed abstention sentence.
"""

COOLING_CAUSE_MISSING = ("compare_independent_measurement", "review_cooling_evidence")


def template(view):
    kernel = view["kernel"]
    if kernel["status"] == "abstain":
        return {"kind": "abstain", "reason": "kernel_withheld",
                "missing_evidence": [f"An observation that passes the validator check named by kernel reason {kernel['reason']}."]}
    findings, checks = view["catalog"]["findings"], view["catalog"]["checks"]
    claims = [{"statement": findings[key], "support": ["kernel:" + key]} for key in kernel["findings"]]
    causes = [{"statement": findings[key], "status": "unconfirmed", "support": ["kernel:" + key],
               "missing": list(COOLING_CAUSE_MISSING)} for key in kernel["findings"] if key == "cooling_path_unconfirmed"]
    return {"kind": "explain", "claims": claims, "causes": causes,
            "missing_evidence": [checks[key] for key in kernel["checks"]]}


def always_abstain(view):
    return {"kind": "abstain", "reason": "insufficient_observation", "missing_evidence": ["Not assessed."]}
