import os, io, csv, json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from . import store, search, assess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = FastAPI(title="Planning Risk Radar")

@app.get("/api/health")
def health():
    return search.health()

@app.get("/api/projects")
def projects():
    return store.list_projects()

@app.post("/api/projects")
async def upsert_project(req: Request):
    p = await req.json()
    pid = store.save_project(p)
    return {"id": pid, "project": store.get_project(pid)}

@app.get("/api/projects/{pid}")
def project(pid: int):
    p = store.get_project(pid)
    if not p: return JSONResponse({"error": "not found"}, 404)
    r = store.latest_review(pid)
    out = {"project": p, "review": r}
    if r:
        out["assessments"] = assess.attention_order(store.assessments_for(r["id"]))
        out["evidence"] = store.evidence_for(r["id"])
        prev = store.prior_review(pid, r["id"])
        out["changed"] = assess.diff(out["evidence"],
                                     store.evidence_for(prev["id"]) if prev else None)
    return out

@app.post("/api/projects/{pid}/review")
def run_review(pid: int):
    p = store.get_project(pid)
    if not p: return JSONResponse({"error": "not found"}, 404)
    try:
        rid = store.new_review(pid)
        all_ev, queries, notes = [], [], {}
        for concern in search.CONCERNS:
            items, summary, q = search.search_concern(p, concern)
            queries += q or []
            notes[concern] = summary
            for it in items:
                store.add_evidence(rid, it)
            ev = store.evidence_for(rid, concern)
            store.save_assessment(rid, assess.assess(p, concern, ev))
            all_ev += ev
        prev = store.prior_review(pid, rid)
        return {"review_id": rid, "queries": sorted(set(queries)), "notes": notes,
                "assessments": assess.attention_order(store.assessments_for(rid)),
                "evidence": all_ev,
                "changed": assess.diff(all_ev, store.evidence_for(prev["id"]) if prev else None)}
    except search.SearchUnavailable as e:
        return JSONResponse({"error": "search_unavailable", "detail": str(e)}, 503)

@app.post("/api/evidence/{eid}/outcome")
async def confirm_outcome(eid: int, req: Request):
    """Confirming an outcome is a human act. It then re-runs the assessment for that concern."""
    b = await req.json()
    o = b.get("outcome")
    if o not in ("approved", "refused", "pending", "withdrawn"):
        return JSONResponse({"error": "outcome must be approved, refused, pending or withdrawn"}, 400)
    e = store.evidence_by_id(eid)
    if not e: return JSONResponse({"error": "not found"}, 404)
    store.set_outcome(eid, o)
    rev = e["review_id"]
    c = store.conn(); r = c.execute("SELECT project_id FROM review WHERE id=?", (rev,)).fetchone(); c.close()
    p = store.get_project(r["project_id"])
    ev = store.evidence_for(rev, e["concern"])
    a = assess.assess(p, e["concern"], ev)
    c = store.conn(); c.execute("DELETE FROM assessment WHERE review_id=? AND concern=?", (rev, e["concern"])); c.commit(); c.close()
    store.save_assessment(rev, a)
    return {"ok": True, "assessment": a}

@app.get("/api/projects/{pid}/risks")
def risks(pid: int):
    return {"register": store.list_risks(pid, accepted=True),
            "suggested": store.list_risks(pid, accepted=False)}

@app.post("/api/projects/{pid}/risks")
async def add_risk(pid: int, req: Request):
    r = await req.json(); r["project_id"] = pid
    return {"id": store.add_risk(r)}

@app.post("/api/risks/{rid}/accept")
def accept(rid: int):
    store.accept_risk(rid); return {"ok": True}

@app.delete("/api/risks/{rid}")
def remove(rid: int):
    store.delete_risk(rid); return {"ok": True}

@app.post("/api/projects/{pid}/suggest")
def suggest(pid: int):
    """Turn assessed concerns into SUGGESTED register rows. They are not accepted until the user says so."""
    p = store.get_project(pid); r = store.latest_review(pid)
    if not r: return JSONResponse({"error": "run a review first"}, 400)
    made = []
    existing = {x["title"].lower() for x in store.list_risks(pid)}
    for a in store.assessments_for(r["id"]):
        title = f"Planning permission refused on {a['concern']}"
        if title.lower() in existing: continue
        made.append(store.add_risk({"project_id": pid, "category": "Planning", "title": title,
                                    "likelihood_band": a["likelihood_band"], "impact_band": a["impact_band"],
                                    "mitigation": "", "notes": "Derived from search evidence, review before accepting.",
                                    "origin": "suggested", "accepted": False}))
    return {"created": len(made)}

@app.post("/api/projects/{pid}/import")
async def import_csv(pid: int, req: Request):
    """Two phase: preview returns detected columns, commit writes rows with the user's mapping."""
    body = await req.json()
    text = body.get("csv", "")
    rdr = csv.DictReader(io.StringIO(text))
    cols = rdr.fieldnames or []
    rows = list(rdr)
    if not body.get("mapping"):
        return {"phase": "preview", "columns": cols, "row_count": len(rows), "sample": rows[:5]}
    m = body["mapping"]; n = 0
    for row in rows:
        title = (row.get(m.get("title","")) or "").strip()
        if not title: continue
        store.add_risk({"project_id": pid, "category": row.get(m.get("category",""), ""),
                        "title": title, "likelihood_band": row.get(m.get("likelihood",""), ""),
                        "impact_band": row.get(m.get("impact",""), ""),
                        "mitigation": row.get(m.get("mitigation",""), ""),
                        "notes": row.get(m.get("notes",""), ""), "origin": "csv", "accepted": True})
        n += 1
    return {"phase": "committed", "imported": n}

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "static"), html=True), name="static")
