import sqlite3, os, json, datetime
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS project(
 id INTEGER PRIMARY KEY, name TEXT, location TEXT, capacity_mw REAL, cooling TEXT,
 grid_demand_mw REAL, residential_m REAL, context TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS review(
 id INTEGER PRIMARY KEY, project_id INTEGER, created_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS evidence(
 id INTEGER PRIMARY KEY, review_id INTEGER, concern TEXT, title TEXT, publisher TEXT,
 resolved_url TEXT, redirect_url TEXT, published_date TEXT, retrieved_at TEXT,
 source_type TEXT, stance TEXT, relevance TEXT, claim_type TEXT,
 outcome TEXT, outcome_confirmed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS assessment(
 id INTEGER PRIMARY KEY, review_id INTEGER, concern TEXT, impact_band TEXT, likelihood_band TEXT,
 impact_basis TEXT, likelihood_basis TEXT, insufficient INTEGER, decisions_found INTEGER, leads_found INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS risk(
 id INTEGER PRIMARY KEY, project_id INTEGER, category TEXT, title TEXT, likelihood_band TEXT,
 impact_band TEXT, mitigation TEXT, notes TEXT, origin TEXT, accepted INTEGER, created_at TEXT);
"""

def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.exists(DB):
        seed = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed", "demo.db")
        if os.path.exists(seed):
            import shutil; shutil.copy(seed, DB)   # hosted demo opens on the real 30 Sep review
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.executescript(SCHEMA); return c

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def rows(cur): return [dict(r) for r in cur.fetchall()]

def save_project(p):
    c = conn()
    if p.get("id"):
        c.execute("""UPDATE project SET name=?,location=?,capacity_mw=?,cooling=?,grid_demand_mw=?,
                     residential_m=?,context=? WHERE id=?""",
                  (p["name"],p["location"],p["capacity_mw"],p["cooling"],p["grid_demand_mw"],
                   p["residential_m"],p["context"],p["id"]))
        pid = p["id"]
    else:
        cur = c.execute("""INSERT INTO project(name,location,capacity_mw,cooling,grid_demand_mw,
                          residential_m,context,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                  (p["name"],p["location"],p["capacity_mw"],p["cooling"],p["grid_demand_mw"],
                   p["residential_m"],p["context"],now()))
        pid = cur.lastrowid
    c.commit(); c.close(); return pid

def get_project(pid):
    c = conn(); r = c.execute("SELECT * FROM project WHERE id=?", (pid,)).fetchone(); c.close()
    return dict(r) if r else None

def list_projects():
    c = conn(); out = rows(c.execute("SELECT * FROM project ORDER BY id DESC")); c.close(); return out

def new_review(pid, note=""):
    c = conn(); cur = c.execute("INSERT INTO review(project_id,created_at,note) VALUES(?,?,?)",(pid,now(),note))
    rid = cur.lastrowid; c.commit(); c.close(); return rid

def prior_review(pid, before_id):
    c = conn(); r = c.execute("SELECT * FROM review WHERE project_id=? AND id<? ORDER BY id DESC LIMIT 1",
                              (pid, before_id)).fetchone(); c.close()
    return dict(r) if r else None

def add_evidence(rid, e):
    c = conn()
    c.execute("""INSERT INTO evidence(review_id,concern,title,publisher,resolved_url,redirect_url,
                 published_date,retrieved_at,source_type,stance,relevance,claim_type,outcome,outcome_confirmed)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (rid,e["concern"],e["title"],e["publisher"],e["resolved_url"],e["redirect_url"],
               e.get("published_date"),e["retrieved_at"],e["source_type"],e["stance"],
               e.get("relevance"),e.get("claim_type"),e.get("outcome"),0))
    c.commit(); c.close()

def evidence_for(rid, concern=None):
    c = conn()
    q = "SELECT * FROM evidence WHERE review_id=?"; a=[rid]
    if concern: q += " AND concern=?"; a.append(concern)
    out = rows(c.execute(q+" ORDER BY id", a)); c.close(); return out

def save_assessment(rid, a):
    c = conn()
    c.execute("""INSERT INTO assessment(review_id,concern,impact_band,likelihood_band,impact_basis,
                 likelihood_basis,insufficient,decisions_found,leads_found) VALUES(?,?,?,?,?,?,?,?,?)""",
              (rid,a["concern"],a["impact_band"],a["likelihood_band"],json.dumps(a["impact_basis"]),
               json.dumps(a["likelihood_basis"]),1 if a["insufficient"] else 0,a["decisions_found"],a.get("leads_found",0)))
    c.commit(); c.close()

def assessments_for(rid):
    c = conn(); out = rows(c.execute("SELECT * FROM assessment WHERE review_id=?", (rid,))); c.close()
    for a in out:
        a["impact_basis"]=json.loads(a["impact_basis"]); a["likelihood_basis"]=json.loads(a["likelihood_basis"])
    return out

def latest_review(pid):
    c = conn(); r = c.execute("SELECT * FROM review WHERE project_id=? ORDER BY id DESC LIMIT 1",(pid,)).fetchone()
    c.close(); return dict(r) if r else None

def add_risk(r):
    c = conn()
    cur = c.execute("""INSERT INTO risk(project_id,category,title,likelihood_band,impact_band,
                       mitigation,notes,origin,accepted,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (r["project_id"],r.get("category",""),r["title"],r.get("likelihood_band",""),
               r.get("impact_band",""),r.get("mitigation",""),r.get("notes",""),
               r.get("origin","manual"),1 if r.get("accepted",True) else 0,now()))
    rid=cur.lastrowid; c.commit(); c.close(); return rid

def list_risks(pid, accepted=None):
    c = conn(); q="SELECT * FROM risk WHERE project_id=?"; a=[pid]
    if accepted is not None: q+=" AND accepted=?"; a.append(1 if accepted else 0)
    out = rows(c.execute(q+" ORDER BY id", a)); c.close(); return out

def accept_risk(rid):
    c = conn(); c.execute("UPDATE risk SET accepted=1 WHERE id=?", (rid,)); c.commit(); c.close()

def delete_risk(rid):
    c = conn(); c.execute("DELETE FROM risk WHERE id=?", (rid,)); c.commit(); c.close()

def set_outcome(eid, outcome):
    """A human confirms a planning outcome against the authority's own page."""
    c = conn(); c.execute("UPDATE evidence SET outcome=?, outcome_confirmed=1 WHERE id=?", (outcome, eid))
    c.commit(); c.close()

def evidence_by_id(eid):
    c = conn(); r = c.execute("SELECT * FROM evidence WHERE id=?", (eid,)).fetchone(); c.close()
    return dict(r) if r else None
