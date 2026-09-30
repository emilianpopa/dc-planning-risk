"""Tests the parts that must not lie. Run: ./venv/bin/python test_journey.py"""
from app import assess
P = {"capacity_mw":120,"grid_demand_mw":110,"residential_m":400,"cooling":"evaporative (water)"}
def ev(t="reported_decision", outcome=None, confirmed=0):
    return {"source_type":t,"outcome":outcome,"outcome_confirmed":confirmed}
fails=[]
def check(name, got, want):
    ok = got==want
    print(("PASS " if ok else "FAIL ")+name+f"  got={got} want={want}")
    if not ok: fails.append(name)

# impact is a pure function of inputs and never moves with evidence
check("impact water/evaporative/120MW", assess.impact(P,"water use")[0], "HIGH")
check("impact water/air cooled", assess.impact({**P,"cooling":"air cooled"},"water use")[0], "LOW")
check("impact grid 110MW", assess.impact(P,"grid capacity")[0], "HIGH")
check("impact grid 20MW", assess.impact({**P,"grid_demand_mw":20},"grid capacity")[0], "LOW")
check("impact community 400m", assess.impact(P,"community opposition")[0], "HIGH")
check("impact community 3000m", assess.impact({**P,"residential_m":3000},"community opposition")[0], "LOW")

# likelihood: unconfirmed never counts, threshold holds, and it CAN move
check("0 leads -> insufficient", assess.likelihood([])[0], "INSUFFICIENT_EVIDENCE")
check("5 UNCONFIRMED leads -> still insufficient", assess.likelihood([ev() for _ in range(5)])[0], "INSUFFICIENT_EVIDENCE")
check("2 confirmed -> still insufficient", assess.likelihood([ev(outcome="refused",confirmed=1)]*2)[0], "INSUFFICIENT_EVIDENCE")
check("3 confirmed refusals -> HIGH", assess.likelihood([ev(outcome="refused",confirmed=1)]*3)[0], "HIGH")
check("3 confirmed approvals -> LOW", assess.likelihood([ev(outcome="approved",confirmed=1)]*3)[0], "LOW")
check("mixed 1r/2a -> MEDIUM", assess.likelihood([ev(outcome="refused",confirmed=1)]+[ev(outcome="approved",confirmed=1)]*2)[0], "MEDIUM")
check("news never counts", assess.likelihood([ev("news",outcome="refused",confirmed=1)]*5)[0], "INSUFFICIENT_EVIDENCE")

# insufficient is never treated as low in ordering: a HIGH impact gap sorts above a HIGH impact LOW
order = assess.attention_order([
    {"concern":"a","impact_band":"HIGH","likelihood_band":"LOW","insufficient":False},
    {"concern":"b","impact_band":"HIGH","likelihood_band":"INSUFFICIENT_EVIDENCE","insufficient":True}])
check("evidence gap outranks a low likelihood at equal impact", order[0]["concern"], "b")

# what changed never invents a trend
check("no prior review says so", assess.diff([], None)["has_prior"], False)
d = assess.diff([{"resolved_url":"u1"},{"resolved_url":"u2"}], [{"resolved_url":"u1"}])
check("diff finds the new source", len(d["new"]), 1)

print("\n"+("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
raise SystemExit(1 if fails else 0)
