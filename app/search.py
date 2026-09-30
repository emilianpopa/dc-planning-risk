"""Grounded retrieval via the Gemini API's google_search tool.

Verified working 30 Sep 2026 with gemini-2.5-flash. Grounding returns redirect URLs that expire,
so each one is resolved to the publisher URL at retrieval time and the resolved URL is stored.
Nothing is stored that has no resolved URL and no retrieval timestamp.
"""
import os, json, datetime, urllib.request, urllib.error, re

MODEL = "gemini-2.5-flash"
CONCERNS = ["grid capacity", "water use", "environmental impact",
            "community opposition", "planning policy"]

class SearchUnavailable(Exception):
    pass

def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise SearchUnavailable(
            "GEMINI_API_KEY is not set. Export it (see .env.example) and restart. "
            "No fallback data is shown, because fabricated findings are worse than none.")
    return k

def _call(prompt, timeout=90):
    body = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={_key()}",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        raise SearchUnavailable(f"Gemini returned HTTP {e.code}: {e.read()[:300].decode('utf8','ignore')}")
    except Exception as e:
        raise SearchUnavailable(f"Search call failed: {type(e).__name__}: {e}")

def resolve(url, timeout=15):
    """Follow the grounding redirect to the real publisher URL. Returns None if it cannot be resolved."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise _Found(newurl)
        op = urllib.request.build_opener(NoRedirect)
        op.open(req, timeout=timeout)
        return None
    except _Found as f:
        return f.url
    except Exception:
        return None

class _Found(Exception):
    def __init__(self, url): self.url = url

def _classify(publisher, title, url):
    """Classify from the RESOLVED URL, which is factual, not from the grounding 'title', which is
    only the domain. Order matters: a decision is recognised before the generic authority bucket,
    because 'council-approves-...' contains 'council'.

    planning_decision   an authority's own application record, or a published appeal decision
    reported_decision   someone reporting a decision. A LEAD. Never counts until a human confirms it
    authority_publication  government or council material that is not itself a decision
    community_signal    petitions and local forums. Real opposition signal, never a decision
    news / unknown      context only
    """
    u = (url or "").lower()
    if re.search(r"(planningdetails|publicaccess|planapp|/planning/app|planning\.[a-z-]+\.gov\.uk"
                 r"|appeal-decision|recovered-appeal)", u):
        return "planning_decision"
    if re.search(r"(approves?|rejects?|refused|refuses|granted|greenlight|green-light|turned-down"
                 r"|planning-app|/news/planning/|backs-)", u):
        return "reported_decision"
    if re.search(r"(petition|38degrees|change\.org|reddit\.com|facebook\.com|nextdoor|mgepetition)", u):
        return "community_signal"
    if ".gov.uk" in u or "parliament.uk" in u or "council" in u:
        return "authority_publication"
    if re.search(r"(bbc\.co|theguardian|thetimes|telegraph|reuters|ft\.com|cityam|techradar|/news/)", u):
        return "news"
    return "unknown"

def search_concern(project, concern):
    """Return (evidence_items, model_summary). Raises SearchUnavailable rather than faking."""
    q = (f"UK data centre planning permission and {concern}. "
         f"Proposed site: {project['location']}. Capacity about {project['capacity_mw']} MW, "
         f"{project['cooling']} cooling, grid demand about {project['grid_demand_mw']} MW, "
         f"nearest homes about {project['residential_m']} m away. "
         f"Find real planning applications and decisions by UK local planning authorities involving "
         f"data centres where {concern} was raised. Prefer the planning authority's own documents and "
         f"published decisions over news. For each, state the authority, the decision if one was made "
         f"(approved, refused, or still pending), and the date. If you cannot confirm a decision, say "
         f"it is unconfirmed. Do not invent applications, outcomes or quotations.")
    r = _call(q)
    cand = r.get("candidates", [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    gm = cand.get("groundingMetadata", {}) or {}
    chunks = gm.get("groundingChunks", []) or []
    retrieved = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    items, seen = [], set()
    for ch in chunks:
        w = ch.get("web") or {}
        redirect = w.get("uri"); publisher = w.get("title")
        if not redirect:
            continue
        resolved = resolve(redirect)
        if not resolved:
            continue                      # no verifiable link, so it is not stored
        if resolved in seen:
            continue                      # dedupe on the resolved URL
        seen.add(resolved)
        items.append({
            "concern": concern,
            "title": w.get("title") or resolved,
            "publisher": publisher,
            "resolved_url": resolved,
            "redirect_url": redirect,
            "published_date": None,       # grounding does not supply one; shown as not available
            "retrieved_at": retrieved,
            "source_type": _classify(publisher, w.get("title"), resolved),
            "stance": "context",
            "outcome": None,          # a planning outcome is never inferred; a human confirms it
            "outcome_confirmed": 0,
            "relevance": None,
            "claim_type": "reported_claim",
        })
    return items, text, gm.get("webSearchQueries", [])

def health():
    try:
        _key()
    except SearchUnavailable as e:
        return {"ok": False, "reason": str(e)}
    try:
        r = _call("Reply with the single word: ready", timeout=30)
        return {"ok": True, "model": MODEL,
                "detail": "Gemini google_search grounding reachable"}
    except SearchUnavailable as e:
        return {"ok": False, "reason": str(e)}
