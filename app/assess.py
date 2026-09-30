"""The heuristic. Deterministic, documented, and printed to the user.

Two rules the brief insists on and this file enforces:
  1. IMPACT comes only from project inputs. Nothing found online moves it.
  2. LIKELIHOOD comes only from comparable planning DECISIONS found. Article counts and tone are
     never converted into a probability. Below MIN_DECISIONS the band is INSUFFICIENT_EVIDENCE,
     which is NOT the same as LOW and is rendered differently.
They are never multiplied into a single score.
"""
MIN_DECISIONS = 3
BANDS = ["LOW", "MEDIUM", "HIGH"]
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

def impact(project, concern):
    """Returns (band, [rules that fired]). Pure function of the project inputs."""
    cap = float(project.get("capacity_mw") or 0)
    grid = float(project.get("grid_demand_mw") or 0)
    res = float(project.get("residential_m") or 0)
    cooling = (project.get("cooling") or "").lower()
    basis = []

    if concern == "water use":
        evap = "evapor" in cooling or "water" in cooling
        if evap and cap >= 100:
            basis.append(f"cooling is '{project['cooling']}' and capacity {cap:g}MW >= 100MW")
            return "HIGH", basis
        if evap:
            basis.append(f"cooling is '{project['cooling']}' but capacity {cap:g}MW < 100MW")
            return "MEDIUM", basis
        basis.append(f"cooling is '{project['cooling']}', not evaporative, so mains water draw is limited")
        return "LOW", basis

    if concern == "grid capacity":
        if grid >= 100:
            basis.append(f"grid demand {grid:g}MW >= 100MW, connection is a strategic constraint")
            return "HIGH", basis
        if grid >= 40:
            basis.append(f"grid demand {grid:g}MW is between 40 and 100MW")
            return "MEDIUM", basis
        basis.append(f"grid demand {grid:g}MW < 40MW")
        return "LOW", basis

    if concern == "community opposition":
        if res and res <= 500:
            basis.append(f"nearest homes {res:g}m away, within 500m")
            return "HIGH", basis
        if res and res <= 1500:
            basis.append(f"nearest homes {res:g}m away, between 500m and 1500m")
            return "MEDIUM", basis
        basis.append(f"nearest homes {res:g}m away, beyond 1500m" if res else "residential distance not given")
        return ("LOW", basis) if res else (INSUFFICIENT, basis)

    if concern == "environmental impact":
        if cap >= 100 or grid >= 100:
            basis.append(f"capacity {cap:g}MW / grid {grid:g}MW, at a scale that usually triggers EIA screening")
            return "HIGH", basis
        basis.append(f"capacity {cap:g}MW / grid {grid:g}MW, below the scale that usually triggers EIA screening")
        return "MEDIUM", basis

    if concern == "planning policy":
        basis.append("policy exposure is treated as MEDIUM for every scheme until local policy is read")
        return "MEDIUM", basis

    basis.append("no impact rule defined for this concern")
    return INSUFFICIENT, basis

def likelihood(evidence):
    """Only planning decisions with a HUMAN CONFIRMED outcome count.

    A decision whose outcome nobody has confirmed cannot vote, because inferring 'approved' or
    'refused' from a URL or from an article's tone is exactly the fabrication this tool must not do.
    Returns (band, basis, n_confirmed).
    """
    DECISIONISH = ("planning_decision", "reported_decision")
    decisions = [e for e in evidence if e.get("source_type") in DECISIONISH]
    confirmed = [e for e in decisions if e.get("outcome_confirmed") and e.get("outcome")]
    n, nd = len(confirmed), len(decisions)
    basis = [f"{nd} decision record(s) or report(s) retrieved, of which {n} have an outcome you confirmed"]
    if nd and not n:
        basis.append("outcomes are unconfirmed, so they do not count. Open the risk and confirm each "
                     "outcome against the authority's own page before it influences anything.")
    if n < MIN_DECISIONS:
        basis.append(f"fewer than {MIN_DECISIONS} confirmed decisions, so no likelihood band is "
                     f"asserted. This is NOT low risk, it is an evidence gap.")
        return INSUFFICIENT, basis, n
    refused = sum(1 for e in confirmed if e["outcome"] == "refused")
    basis.append(f"{refused} of {n} confirmed decisions were refusals")
    share = refused / n
    if share >= 0.6:
        basis.append("most comparable schemes were refused")
        return "HIGH", basis, n
    if share >= 0.3:
        basis.append("comparable decisions are mixed")
        return "MEDIUM", basis, n
    basis.append("most comparable schemes were approved")
    return "LOW", basis, n

def assess(project, concern, evidence):
    ib, ibasis = impact(project, concern)
    lb, lbasis, n = likelihood(evidence)
    leads = len([e for e in evidence if e.get("source_type") in ("planning_decision", "reported_decision")])
    return {"concern": concern, "impact_band": ib, "likelihood_band": lb,
            "impact_basis": ibasis, "likelihood_basis": lbasis,
            "insufficient": lb == INSUFFICIENT, "decisions_found": n, "leads_found": leads}

def attention_order(assessments):
    """Rank for 'what to look at first' WITHOUT multiplying the two bands into a score.
    Evidence gaps on a high impact concern sort to the top, because an unknown on something that
    matters is the thing a risk officer should chase first."""
    w = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, INSUFFICIENT: 0}
    def key(a):
        gap = 1 if a["likelihood_band"] == INSUFFICIENT else 0
        return (-w[a["impact_band"]], -gap, -w.get(a["likelihood_band"], 0))
    return sorted(assessments, key=key)

def diff(current, previous):
    """URL-level diff between two reviews. Never invents a trend."""
    if previous is None:
        return {"has_prior": False,
                "message": "No prior review saved for this project, so there is nothing to compare. "
                           "Run a second review later to see what changed."}
    cur = {e["resolved_url"]: e for e in current}
    prv = {e["resolved_url"]: e for e in previous}
    return {"has_prior": True,
            "new": [cur[u] for u in cur if u not in prv],
            "gone": [prv[u] for u in prv if u not in cur],
            "unchanged": len([u for u in cur if u in prv])}


# ---------------------------------------------------------------------------
# Forward look. This is a LEADING INDICATOR, not a trained forecast.
#
# Hannah's framing on 30 Sep: "if we're waiting until a problem materialises to start to
# address it, then we're too late." So the question is not what the likelihood is today,
# it is whether the signal that precedes a refusal is building.
#
# What this measures is real: how many community and authority signals each concern is
# returning now, and whether that is more or fewer than the previous review. What it does
# NOT do is predict a decision, because that needs a corpus of historical outcomes we do
# not have. outlook_gaps() states that in the response rather than leaving it implied.
SIGNAL_TYPES = ("community_signal", "authority_publication")

def _count(evidence, concern, types=SIGNAL_TYPES):
    return sum(1 for e in evidence
               if e.get("concern") == concern and e.get("source_type") in types)

def outlook(concern, current, previous):
    """Per concern: signals now, signals last time, direction, and a plain-word outlook."""
    now_n = _count(current, concern)
    has_prior = previous is not None
    prev_n = _count(previous, concern) if has_prior else None
    delta = (now_n - prev_n) if has_prior else None

    if not has_prior:
        direction, note = "no baseline", "First review, so there is nothing to compare against yet."
    elif delta > 0:
        direction, note = "rising", f"{delta} more signal(s) than the previous review."
    elif delta < 0:
        direction, note = "falling", f"{abs(delta)} fewer signal(s) than the previous review."
    else:
        direction, note = "flat", "Same number of signals as the previous review."

    if now_n == 0:
        state, basis = "NO_SIGNAL", "Nothing public is being said about this yet, in what we retrieved."
    elif now_n >= 3 and direction == "rising":
        state, basis = "BUILDING", "Three or more public signals and the count is going up."
    elif now_n >= 3:
        state, basis = "PRESENT", "Three or more public signals, but the count is not growing."
    else:
        state, basis = "THIN", "Fewer than three public signals, too little to read a direction from."

    return {"concern": concern, "signals_now": now_n, "signals_prev": prev_n,
            "delta": delta, "direction": direction, "state": state,
            "basis": basis, "note": note}


def outlook_gaps():
    """What a real forecast would need, stated out loud so a demo never implies we have it."""
    return [
        {"have": True,  "item": "Public signals retrieved live, each link resolved to its publisher."},
        {"have": True,  "item": "Movement in those signals between one review and the next."},
        {"have": False, "item": "Outcomes of comparable schemes, so a signal count can be tied to a refusal rate."},
        {"have": False, "item": "A trained model. Nothing here is trained on anything. These are counted signals and a rule."},
        {"have": False, "item": "Climate and grid projections for the site, which is where Google Earth Engine would come in."},
    ]
