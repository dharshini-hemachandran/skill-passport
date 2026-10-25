"""Skill Passport API. Same ML as matching.py/simple_ml.py: clean -> TF-IDF (tfidf_data.pkl) -> cosine.
Run from project root: uvicorn server:app --reload --port 8000"""
import io, json, os, re, uuid, hashlib
from collections import Counter
import joblib, numpy as np, pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB_FILE = "db.json"

# ---------- ML (identical logic to matching.py) ----------
_m = joblib.load("model/tfidf_data.pkl")
vocabulary, word_to_index, idf = _m["vocabulary"], _m["word_to_index"], _m["idf"]

SKILLS = ["python","java","javascript","c++","sql","html","css","react","machine learning","deep learning",
 "artificial intelligence","data science","data analysis","pandas","numpy","tensorflow","pytorch",
 "computer vision","opencv","nlp","natural language processing","statistics","excel","power bi","tableau",
 "git","github","docker","linux","cybersecurity","networking","figma","ui design","ux design"]

def clean_text(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", t.lower())).strip()

def extract_skills(t):
    t = t.lower()
    return [s for s in SKILLS if re.search(r"\b" + re.escape(s) + r"\b", t)]

def create_vector(text):
    words = clean_text(text).split()
    v = np.zeros(len(vocabulary), dtype=np.float32)
    if not words: return v
    for w, c in Counter(words).items():
        if w in word_to_index:
            i = word_to_index[w]; v[i] = (c / len(words)) * idf[i]
    return v

def cosine(a, b):
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d else 0.0

def opp_text(o): return f"{o['description']} {' '.join(o.get('skills', []))}"
def profile_text(p):
    parts = list(p.get("skills", []))
    for x in p.get("projects", []): parts += [x.get("title", ""), x.get("description", ""), x.get("tech", "")]
    for x in p.get("achievements", []): parts.append(x.get("title", ""))
    parts.append(p.get("resume_text", ""))
    return " ".join(parts)

# ---------- persistence (local JSON fallback) ----------
def load():
    if os.path.exists(DB_FILE): return json.load(open(DB_FILE))
    db = {"users": {}, "profiles": {}, "opportunities": [], "applications": [], "saved": [], "sessions": {}}
    if os.path.exists("data/opportunities.csv"):
        for i, r in pd.read_csv("data/opportunities.csv").iterrows():
            desc = str(r["description"])
            db["opportunities"].append({"id": f"o{i+1}", "title": str(r["title"]), "org": str(r.get("organization", "Campus")),
              "type": str(r.get("type", "Club")), "description": desc, "skills": extract_skills(desc),
              "deadline": "", "contact": "", "creator": None})
    save(db); return db
def save(db): json.dump(db, open(DB_FILE, "w"), indent=1)
db = load()
def hp(p): return hashlib.sha256(p.encode()).hexdigest()
def me(token):
    uid = db["sessions"].get((token or "").replace("Bearer ", ""))
    if not uid: raise HTTPException(401, "Not logged in")
    return db["users"][uid]

def ranked(profile):
    pv = create_vector(profile_text(profile))
    out = [{**o, "similarity": cosine(pv, create_vector(opp_text(o)))} for o in db["opportunities"]]
    return sorted(out, key=lambda x: -x["similarity"])

# ---------- auth ----------
class Signup(BaseModel):
    name: str; email: str; password: str; role: str = "student"
    field: str = ""; year: str = ""; org: str = ""; org_type: str = ""; position: str = ""
class Login(BaseModel): email: str; password: str

@app.post("/api/signup")
def signup(s: Signup):
    if any(u["email"] == s.email for u in db["users"].values()): raise HTTPException(400, "Email already registered")
    uid = uuid.uuid4().hex[:8]; tok = uuid.uuid4().hex
    db["users"][uid] = {**s.dict(exclude={"password"}), "id": uid, "pw": hp(s.password)}
    db["profiles"][uid] = {"skills": [], "projects": [], "achievements": [], "links": [], "evidence": [], "resume_text": ""}
    db["sessions"][tok] = uid; save(db)
    return {"token": tok, "user": {k: v for k, v in db["users"][uid].items() if k != "pw"}}

@app.post("/api/login")
def login(l: Login):
    u = next((u for u in db["users"].values() if u["email"] == l.email and u["pw"] == hp(l.password)), None)
    if not u: raise HTTPException(401, "Invalid credentials")
    tok = uuid.uuid4().hex; db["sessions"][tok] = u["id"]; save(db)
    return {"token": tok, "user": {k: v for k, v in u.items() if k != "pw"}}

@app.post("/api/forgot-password")
def forgot(d: dict): return {"ok": True, "message": "If the account exists, a reset link would be sent (demo mode)."}

# ---------- profile ----------
@app.get("/api/profile")
def get_profile(authorization: str = Header(None)):
    u = me(authorization); return {"user": {k: v for k, v in u.items() if k != "pw"}, "profile": db["profiles"][u["id"]]}

@app.put("/api/profile")
def put_profile(p: dict, authorization: str = Header(None)):
    u = me(authorization); db["profiles"][u["id"]] = p; save(db); return p

# ---------- ML endpoints ----------
@app.post("/api/analyze-resume")
async def analyze(file: UploadFile = File(...)):
    raw = await file.read()
    if file.filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        text = "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(raw)).pages)
    else: text = raw.decode("utf-8", "ignore")
    return {"skills": extract_skills(text), "text": text}

@app.post("/api/match-opportunities")
def match(profile: dict): return ranked(profile)

# ---------- opportunities ----------
@app.get("/api/opportunities")
def list_opps(): return db["opportunities"]

@app.post("/api/opportunities")
def create_opp(o: dict, authorization: str = Header(None)):
    u = me(authorization)
    if not o.get("title") or not o.get("description"): raise HTTPException(400, "Title and description required")
    o = {**o, "id": "o" + uuid.uuid4().hex[:6], "creator": u["id"]}
    o["skills"] = o.get("skills") or extract_skills(o["description"])
    db["opportunities"].append(o); save(db); return o

def _find(i):
    o = next((o for o in db["opportunities"] if o["id"] == i), None)
    if not o: raise HTTPException(404, "Not found")
    return o

@app.get("/api/opportunities/{i}")
def get_opp(i: str): return _find(i)

@app.put("/api/opportunities/{i}")
def upd_opp(i: str, d: dict, authorization: str = Header(None)):
    u = me(authorization); o = _find(i)
    if o["creator"] != u["id"]: raise HTTPException(403, "Not yours")
    o.update({k: v for k, v in d.items() if k not in ("id", "creator")}); save(db); return o

@app.delete("/api/opportunities/{i}")
def del_opp(i: str, authorization: str = Header(None)):
    u = me(authorization); o = _find(i)
    if o["creator"] != u["id"]: raise HTTPException(403, "Not yours")
    db["opportunities"].remove(o); save(db); return {"ok": True}

@app.post("/api/opportunities/{i}/apply")
def apply(i: str, authorization: str = Header(None)):
    u = me(authorization); _find(i)
    if not any(a["opp"] == i and a["user"] == u["id"] for a in db["applications"]):
        db["applications"].append({"opp": i, "user": u["id"]}); save(db)
    return {"status": "APPLICATION SUBMITTED"}

@app.post("/api/opportunities/{i}/save")
def save_opp(i: str, authorization: str = Header(None)):
    u = me(authorization); _find(i)
    e = {"opp": i, "user": u["id"]}
    if e in db["saved"]: db["saved"].remove(e); s = False
    else: db["saved"].append(e); s = True
    save(db); return {"saved": s}

@app.get("/api/my-status")
def status(authorization: str = Header(None)):
    u = me(authorization)
    return {"applied": [a["opp"] for a in db["applications"] if a["user"] == u["id"]],
            "saved": [a["opp"] for a in db["saved"] if a["user"] == u["id"]]}

@app.get("/api/opportunities/{i}/candidates")
def candidates(i: str):
    ov = create_vector(opp_text(_find(i))); out = []
    for uid, p in db["profiles"].items():
        u = db["users"][uid]
        if u["role"] != "student": continue
        out.append({"id": uid, "name": u["name"], "field": u.get("field", ""), "profile": p,
                    "similarity": cosine(ov, create_vector(profile_text(p)))})
    return sorted(out, key=lambda x: -x["similarity"])

@app.get("/")
def index(): return FileResponse("static/index.html")
