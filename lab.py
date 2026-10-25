"""Consent-based passport access, timed skill challenges, reviewer rubric and documents."""
import base64
import io
import json
import os
import random
import secrets
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

import server as core

router = APIRouter(prefix="/api")
LEVELS = ("private", "applicants", "reviewers")
CRIT = [("correctness", "Analysis & correctness", 30), ("reasoning", "Reasoning & trade-offs", 25),
        ("understanding", "Understanding (follow-ups)", 20), ("debugging", "Debugging & decisions", 15),
        ("communication", "Communication", 10)]
WEIGHT = {i: w for i, _, w in CRIT}
KW = ("because", "trade-off", "tradeoff", "instead", "however", "assum", "alternative", "risk", "edge case", "cost")
MAX_DOC = 3 * 1024 * 1024
MAX_IMG = 600 * 1024
IMG_EXT = {".png", ".jpg", ".jpeg"}


def now():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.isoformat(timespec="seconds")


def ensure():
    for key, default in (("challenges", []), ("consents", {}), ("access_log", [])):
        core.db.setdefault(key, default)
    return core.db


def consent(uid):
    return ensure()["consents"].get(uid, {"level": "private", "documents": False, "challenges": True})


def can_view(viewer, sid):
    if viewer["id"] == sid:
        return True
    if viewer["role"] != "creator":
        return False
    level = consent(sid)["level"]
    if level == "reviewers":
        return True
    if level == "applicants":
        mine = {o["id"] for o in core.db["opportunities"] if o.get("creator") == viewer["id"]}
        return any(a["user"] == sid and a["opp"] in mine for a in core.db["applications"])
    return False


def need_role(user, role):
    if user["role"] != role:
        raise HTTPException(403, "This action is not available for your account type.")


# ---------------------------------------------------------------- challenge generation
def build(skill, rng):
    s = skill.lower()
    if s in {"python", "pandas", "sql", "data analysis", "statistics", "excel", "numpy", "power bi", "tableau", "data science"}:
        weeks = [f"W{i}" for i in range(1, 9)]
        base = rng.randint(180, 260)
        orders = [base + rng.randint(-15, 15) for _ in weeks]
        spike = rng.randint(2, 6)
        orders[spike] *= rng.choice([3, 4])
        miss = rng.choice([i for i in range(8) if i != spike])
        rows = ["week,orders,returns"] + [
            f"{w},{o},{'' if i == miss else round(o * rng.uniform(.04, .08))}"
            for i, (w, o) in enumerate(zip(weeks, orders))]
        return {"title": "Analyze the unknown dataset", "minutes": 45, "dataset": "\n".join(rows),
                "scenario": rng.choice([
                    "A campus store exported weekly order counts. One week looks wrong and one value is missing. Your manager needs a trustworthy return-rate figure.",
                    "A club tracked weekly merchandise orders and returns. The export has one suspicious week and one gap. Report an honest return rate."]),
                "constraints": ["Work only from the data shown", "State every assumption you make", "Show arithmetic, not only conclusions"],
                "deliverables": ["Which week is anomalous and why", "How you treat the missing value", "Return rate before and after cleaning, with numbers"],
                "milestones": ["Inspect the data", "Decide on cleaning", "Compute the result", "Explain your reasoning"],
                "followups": [f"If you removed {weeks[spike]} instead of capping it, how would your return rate change? Show the arithmetic.",
                              f"What did you assume for {weeks[miss]}, and how would a wrong assumption change your conclusion?"],
                "facts": [weeks[spike], str(orders[spike]), weeks[miss]]}
    if s in {"machine learning", "deep learning", "computer vision", "nlp", "natural language processing", "tensorflow", "pytorch", "opencv", "artificial intelligence"}:
        major = rng.randint(7, 9)
        labels = [1] * major + [0] * (10 - major)
        rng.shuffle(labels)
        rows = ["hours,attendance,passed,result_copy"] + [
            f"{rng.randint(1, 9)},{rng.randint(40, 98)},{y},{y}" for y in labels]
        pct = major * 10
        return {"title": "Choose and defend a classifier", "minutes": 45, "dataset": "\n".join(rows),
                "scenario": "Predict whether a student passes from the table below. Decide how to model it and how to measure it, and explain your choices.",
                "constraints": ["Only these 10 rows are available", "No more than one model family", "Justify the evaluation metric"],
                "deliverables": ["Which columns you use and which you refuse", "Model and evaluation choice", "Risks of this dataset"],
                "milestones": ["Inspect features", "Choose approach", "Describe evaluation", "Explain risks"],
                "followups": [f"The class split is {major}:{10 - major}. What accuracy does always predicting the majority class get, and why is that a problem?",
                              "Which column would you remove before training and what would go wrong if you kept it?"],
                "facts": ["result_copy", str(pct)]}
    if s in {"html", "css", "javascript", "react", "ui design", "ux design", "figma"}:
        field = rng.choice(["email", "phone", "student id"])
        kb, width = rng.choice([40, 60, 80]), rng.choice([320, 360])
        return {"title": f"Design a {field} sign-up step", "minutes": 40, "dataset": "",
                "scenario": f"A campus app needs a one-field sign-up step that asks for a {field}. It must work on phones and for keyboard users.",
                "constraints": [f"Must work at {width}px width", f"Page weight under {kb} KB", "Keyboard and screen-reader accessible"],
                "deliverables": ["Structure of the screen (code or annotated sketch)", "Validation and error behaviour", "Accessibility decisions"],
                "milestones": ["Plan the layout", "Define states", "Handle errors", "Explain trade-offs"],
                "followups": [f"Users report the {field} field loses focus on Android. Walk through your debugging steps in order.",
                              "Which constraint would you relax first if forced to, and what breaks?"],
                "facts": [str(width), str(kb), field]}
    n, m = rng.randint(300, 900), rng.randint(3, 9)
    return {"title": "Triage a login incident", "minutes": 30, "dataset": "",
            "scenario": f"Monitoring shows {n} failed logins from {m} IP addresses in ten minutes against the campus portal.",
            "constraints": ["Students must still be able to log in", "No data about the IPs beyond the counts", "Explain what you would check first"],
            "deliverables": ["Triage steps in order", "Containment option and its cost", "What you would monitor afterwards"],
            "milestones": ["Assess severity", "Contain", "Verify", "Report"],
            "followups": [f"Why might blocking all {m} addresses be the wrong first move?",
                          "What evidence would change your mind about this being an attack?"],
            "facts": [str(n), str(m)]}


def ai_build(skill, opp, mine):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = (f"Create a short timed project challenge testing '{skill}' for a student whose skills are {mine[:8]}"
              + (f" applying to: {opp['title']} - {opp['description'][:300]}" if opp else "")
              + ". Return ONLY JSON with keys title, scenario, dataset (string, may be empty), constraints, deliverables, "
                "milestones, followups (each a list of strings), facts (list of 2-3 specific strings that appear in "
                "the scenario or dataset and that a correct answer must mention), minutes (integer 20-60). Follow-ups must "
                "require reasoning about specifics so a generic answer is insufficient.")
    body = json.dumps({"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), "max_tokens": 1500,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    request = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        text = json.load(urllib.request.urlopen(request, timeout=25))["content"][0]["text"]
        spec = json.loads(text[text.index("{"):text.rindex("}") + 1])
        lists = ("constraints", "deliverables", "milestones", "followups", "facts")
        if not (isinstance(spec.get("title"), str) and isinstance(spec.get("scenario"), str)
                and all(isinstance(spec.get(k), list) and spec[k] for k in lists)):
            return None
        for k in lists:
            spec[k] = [str(x)[:400] for x in spec[k]][:6]
        spec["dataset"] = str(spec.get("dataset", ""))[:3000]
        spec["minutes"] = max(15, min(90, int(spec.get("minutes", 40))))
        return spec
    except Exception:
        return None


def public(ch, full=True):
    out = {k: v for k, v in ch.items() if k != "facts"}
    if not full:
        out.pop("subs", None)
    return out


def summary(ch):
    return {"id": ch["id"], "title": ch["title"], "skill": ch["skill"], "opp_id": ch.get("opp_id"),
            "status": ch["status"], "issued_at": ch["issued_at"], "deadline_at": ch["deadline_at"],
            "submissions": len(ch["subs"]), "auto": ch.get("auto"), "review": ch.get("review"),
            "level": "HUMAN-VERIFIED" if ch.get("review") else ("AUTOMATED CHECK ONLY" if ch.get("auto") else "NOT SUBMITTED")}


def get_ch(cid):
    ch = next((c for c in ensure()["challenges"] if c["id"] == cid), None)
    if not ch:
        raise HTTPException(404, "Challenge not found.")
    return ch


class Gen(BaseModel):
    opportunity_id: str | None = None
    skill: str | None = None


@router.post("/challenges")
def generate(g: Gen, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "student")
    ensure()
    mine = [s.lower() for s in core.db["profiles"].get(user["id"], {}).get("skills", [])]
    opp = core.find_opportunity(g.opportunity_id) if g.opportunity_id else None
    req = [s.lower() for s in (opp or {}).get("skills", [])]
    skill = ((g.skill or "").strip().lower() or next((s for s in req if s in mine), None)
             or (req[0] if req else None) or (mine[0] if mine else None))
    skill = skill or "problem solving"  # students with no skills yet still get a general challenge
    live = [c for c in core.db["challenges"] if c["student"] == user["id"] and c["status"] == "issued"
            and c["deadline_at"] > iso(now())]
    if len(live) >= 3:
        raise HTTPException(409, "You already have 3 open challenges. Open one from the list, or wait for one to expire, before generating another.")
    spec = ai_build(skill, opp, mine)
    source = "ai" if spec else "template"
    spec = spec or build(skill, random.Random(secrets.randbits(32)))
    ch = {"id": secrets.token_hex(6), "student": user["id"], "opp_id": opp["id"] if opp else None, "skill": skill,
          "source": source, "title": spec["title"], "scenario": spec["scenario"], "dataset": spec["dataset"],
          "constraints": spec["constraints"], "deliverables": spec["deliverables"], "milestones": spec["milestones"],
          "followups": spec["followups"], "facts": spec["facts"], "limit": spec["minutes"],
          "rubric": [{"id": i, "label": label, "weight": w} for i, label, w in CRIT],
          "issued_at": iso(now()), "deadline_at": iso(now() + timedelta(minutes=spec["minutes"])),
          "status": "issued", "subs": []}
    core.db["challenges"].append(ch)
    core.save_state(core.db)
    return public(ch)


@router.get("/challenges")
def mine_list(authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "student")
    return [public(c) for c in ensure()["challenges"] if c["student"] == user["id"]][::-1]


@router.get("/challenges/{cid}")
def one(cid: str, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    ch = get_ch(cid)
    if ch["student"] != user["id"] and not (can_view(user, ch["student"]) and ch["status"] != "issued"
                                            and (consent(ch["student"])["challenges"])):
        raise HTTPException(403, "You do not have access to this challenge.")
    return public(ch)


def assess(ch, sub):
    text = (sub["answer"] + " " + sub["reasoning"] + " " + " ".join(sub["followups"])).lower()
    facts = [f.lower() for f in ch["facts"]]
    hits = [f for f in facts if f in text]
    kws = len({k for k in KW if k in text})
    fu = sum(1 for f in sub["followups"] if len(f.strip()) >= 60 and any(x in f.lower() for x in facts))
    scores = {"correctness": round(4 * len(hits) / len(facts)) if facts else None,
              "reasoning": min(4, kws // 2) if len(sub["reasoning"]) >= 200 else min(2, kws // 2),
              "understanding": round(4 * fu / len(ch["followups"])) if ch["followups"] else None,
              "debugging": None, "communication": None}
    done = [k for k, v in scores.items() if v is not None]
    pct = round(100 * sum(scores[k] * WEIGHT[k] for k in done) / (4 * sum(WEIGHT[k] for k in done))) if done else None
    return {"scores": scores, "facts_found": len(hits), "facts_total": len(facts), "partial_pct": pct,
            "level": "AUTOMATED", "note": "Automated keyword and consistency checks only. Debugging and communication "
                                          "need a human reviewer. Not verified."}


class Sub(BaseModel):
    answer: str = Field(min_length=40, max_length=8000)
    reasoning: str = Field(min_length=40, max_length=4000)
    ai_used: bool = False
    ai_notes: str = Field(default="", max_length=1500)
    followups: list[str] = Field(max_length=8)
    milestones: list[str] = Field(default_factory=list, max_length=8)


@router.post("/challenges/{cid}/submit")
def submit(cid: str, s: Sub, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    ch = get_ch(cid)
    if ch["student"] != user["id"]:
        raise HTTPException(403, "This is not your challenge.")
    if ch["status"] == "reviewed":
        raise HTTPException(409, "This challenge has already been reviewed.")
    if now() > datetime.fromisoformat(ch["deadline_at"]) + timedelta(seconds=30):
        raise HTTPException(409, "The time limit for this challenge has ended.")
    if len(s.followups) != len(ch["followups"]) or any(len(f.strip()) < 30 for f in s.followups):
        raise HTTPException(422, "Answer every follow-up question (at least 30 characters each).")
    if s.ai_used and len(s.ai_notes.strip()) < 10:
        raise HTTPException(422, "Describe how you used AI tools.")
    sub = {"n": len(ch["subs"]) + 1, "at": iso(now()), **s.model_dump()}
    ch["subs"].append(sub)
    ch["status"] = "submitted"
    ch["auto"] = assess(ch, sub)
    core.save_state(core.db)
    return public(ch)


class Review(BaseModel):
    scores: dict[str, int]
    feedback: str = Field(min_length=10, max_length=2000)


@router.post("/challenges/{cid}/review")
def review(cid: str, r: Review, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "creator")
    ch = get_ch(cid)
    if not can_view(user, ch["student"]) or not consent(ch["student"])["challenges"]:
        raise HTTPException(403, "The student has not shared this result with you.")
    if ch["status"] == "issued":
        raise HTTPException(409, "This challenge has not been submitted yet.")
    if set(r.scores) != set(WEIGHT) or any(not 0 <= v <= 4 for v in r.scores.values()):
        raise HTTPException(422, "Score every rubric criterion from 0 to 4.")
    pct = round(100 * sum(r.scores[k] * WEIGHT[k] for k in WEIGHT) / (4 * sum(WEIGHT.values())))
    ch["review"] = {"reviewer": user["name"], "reviewer_id": user["id"], "at": iso(now()), "scores": r.scores,
                    "feedback": r.feedback, "pct": pct, "level": "HUMAN-VERIFIED"}
    ch["status"] = "reviewed"
    core.save_state(core.db)
    return public(ch)


# ---------------------------------------------------------------- consent + passport
class Consent(BaseModel):
    level: str
    documents: bool = False
    challenges: bool = True


@router.get("/consent")
def get_consent(authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "student")
    log = [{"viewer": core.db["users"].get(x["viewer"], {}).get("name", "A reviewer"), "at": x["at"]}
           for x in ensure()["access_log"] if x["student"] == user["id"]][-20:]
    return {"consent": consent(user["id"]), "access_log": log}


@router.put("/consent")
def put_consent(c: Consent, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "student")
    if c.level not in LEVELS:
        raise HTTPException(422, "Unknown sharing level.")
    ensure()["consents"][user["id"]] = c.model_dump()
    core.save_state(core.db)
    return c.model_dump()


@router.get("/students/{sid}/passport")
def passport(sid: str, authorization: str | None = Header(default=None)):
    viewer = core.current_user(authorization)
    ensure()
    student = core.db["users"].get(sid)
    if not student or student["role"] != "student":
        raise HTTPException(404, "Student not found.")
    if not can_view(viewer, sid):
        raise HTTPException(403, "This student has not shared their passport with you.")
    c, p, own = consent(sid), core.db["profiles"].get(sid, {}), viewer["id"] == sid
    if not own:
        core.db["access_log"] = (core.db["access_log"] + [{"viewer": viewer["id"], "student": sid, "at": iso(now())}])[-500:]
        core.save_state(core.db)
    out = {"id": sid, "name": student["name"], "field": student.get("field", ""), "bio": p.get("bio", ""),
           "interests": p.get("interests", ""), "skills": p.get("skills", []), "projects": p.get("projects", []),
           "achievements": p.get("achievements", []), "links": p.get("links", []), "evidence": p.get("evidence", []),
           "consent": c}
    if c["documents"] or own:
        out["documents"] = [{"id": d["id"], "name": d["name"], "kind": d["kind"], "uploaded_at": d["uploaded_at"],
                             "image": d.get("image", False), "excerpt": d["text"][:600]} for d in p.get("documents", [])]
    if c["challenges"] or own:
        out["challenges"] = [summary(x) for x in core.db["challenges"] if x["student"] == sid and x["status"] != "issued"]
    return out


@router.get("/recruiter/candidates")
def rec_candidates(opportunity_id: str | None = None, authorization: str | None = Header(default=None)):
    viewer = core.current_user(authorization)
    need_role(viewer, "creator")
    ensure()
    opp = core.find_opportunity(opportunity_id) if opportunity_id else None
    if opp and opp["creator"] != viewer["id"]:
        raise HTTPException(403, "You can only review candidates for your own opportunities.")
    mine = {o["id"] for o in core.db["opportunities"] if o.get("creator") == viewer["id"]}
    out = []
    for sid, p in core.db["profiles"].items():
        user = core.db["users"].get(sid)
        if not user or user["role"] != "student" or not can_view(viewer, sid):
            continue
        applied = [a["opp"] for a in core.db["applications"] if a["user"] == sid and a["opp"] in mine]
        if opp and opp["id"] not in applied and consent(sid)["level"] != "reviewers":
            continue
        shown = consent(sid)["challenges"]
        out.append({"id": sid, "name": user["name"], "field": user.get("field", ""), "skills": p.get("skills", []),
                    "projects": len(p.get("projects", [])), "applied": bool(opp and opp["id"] in applied),
                    "similarity": core.cosine_similarity(core.opportunity_text(opp), core.profile_text(p)) if opp else None,
                    "challenges": [summary(x) for x in core.db["challenges"]
                                   if x["student"] == sid and x["status"] != "issued" and shown]})
    return sorted(out, key=lambda x: -(x["similarity"] or 0))


# ---------------------------------------------------------------- documents
@router.post("/documents")
async def upload_document(file: UploadFile = File(...), kind: str = Form("certificate"),
                          authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    need_role(user, "student")
    name = Path(file.filename or "document").name[:80]
    ext = Path(name).suffix.lower()
    if ext not in {".pdf", ".docx", ".txt"} | IMG_EXT:
        raise HTTPException(415, "Supported formats are .pdf, .docx, .txt, .png and .jpg.")
    raw = await file.read(MAX_DOC + 1)
    if len(raw) > MAX_DOC:
        raise HTTPException(413, "Documents must be 3 MB or smaller.")
    image = None
    if ext in IMG_EXT:
        png, jpg = raw.startswith(b"\x89PNG\r\n\x1a\n"), raw.startswith(b"\xff\xd8\xff")
        if not (png or jpg):
            raise HTTPException(415, "That file is not a valid PNG or JPEG image.")
        if len(raw) > MAX_IMG:
            raise HTTPException(413, "Images must be 600 KB or smaller. The app shrinks large images automatically.")
        image = f"data:{'image/png' if png else 'image/jpeg'};base64," + base64.b64encode(raw).decode()
    try:
        if image:
            text = ""
        elif ext == ".pdf":
            text = "\n".join(pg.extract_text() or "" for pg in core.PdfReader(io.BytesIO(raw)).pages)
        elif ext == ".docx":
            text = core.extract_docx_text(raw)
        else:
            text = raw.decode("utf-8")
    except (core.FileNotDecryptedError, core.PdfReadError, UnicodeDecodeError, ValueError, OSError, zipfile.BadZipFile):
        raise HTTPException(400, "The document could not be read.")
    docs = core.db["profiles"].setdefault(user["id"], {}).setdefault("documents", [])
    if len(docs) >= 10:
        raise HTTPException(409, "You can store up to 10 documents.")
    if image and sum(1 for d in docs if d.get("image")) >= 3:
        raise HTTPException(409, "You can store up to 3 image certificates.")
    doc = {"id": secrets.token_hex(6), "name": name, "size": len(raw), "uploaded_at": iso(now()), "image": bool(image),
           "kind": kind if kind in {"certificate", "transcript", "project", "other"} else "other", "text": text[:20000]}
    docs.append(doc)
    if image:
        core.db.setdefault("doc_images", {})[doc["id"]] = image
    core.save_state(core.db)
    return {k: v for k, v in doc.items() if k != "text"}


@router.get("/documents/{did}/image")
def document_image(did: str, authorization: str | None = Header(default=None)):
    viewer = core.current_user(authorization)
    ensure()
    owner = next((sid for sid, p in core.db["profiles"].items() if any(d["id"] == did for d in p.get("documents", []))), None)
    if not owner or did not in core.db.get("doc_images", {}):
        raise HTTPException(404, "Image not found.")
    if owner != viewer["id"] and not (can_view(viewer, owner) and consent(owner)["documents"]):
        raise HTTPException(403, "This document has not been shared with you.")
    return {"data_url": core.db["doc_images"][did]}


@router.delete("/documents/{did}")
def delete_document(did: str, authorization: str | None = Header(default=None)):
    user = core.current_user(authorization)
    docs = core.db["profiles"].get(user["id"], {}).get("documents", [])
    keep = [d for d in docs if d["id"] != did]
    if len(keep) == len(docs):
        raise HTTPException(404, "Document not found.")
    core.db["profiles"][user["id"]]["documents"] = keep
    core.db.get("doc_images", {}).pop(did, None)
    core.save_state(core.db)
    return {"ok": True}


# ---------------------------------------------------------------- static helper for the API-served frontend
pages = APIRouter()


@pages.get("/lab.js")
def lab_js():
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).resolve().parent / "static" / "lab.js", media_type="text/javascript")
