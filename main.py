from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import hashlib, secrets, os, sqlite3

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB = "app.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    d = db()
    d.executescript("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE, password TEXT, name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT, expires_at TEXT);")
    d.commit(); d.close()

init()

def get_user(req: Request):
    t = req.cookies.get("sess")
    if not t: return None
    r = db().execute("SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires_at>datetime('now')", (t,)).fetchone()
    return dict(r) if r else None

class Reg(BaseModel): email: str; password: str; name: str = ""
class Log(BaseModel): email: str; password: str

HTML_PAGE = open("index.html").read() if os.path.exists("index.html") else ""

@app.get("/")
async def home(req: Request):
    return HTMLResponse(HTML_PAGE)

@app.post("/api/register")
async def reg(req: Reg, resp: Response):
    uid = hashlib.md5(req.email.encode()).hexdigest()[:12]
    pw = hashlib.sha256(req.password.encode()).hexdigest()
    try:
        d = db(); d.execute("INSERT INTO users (id,email,password,name) VALUES (?,?,?,?)", (uid, req.email, pw, req.name)); d.commit(); d.close()
    except: d.close(); raise HTTPException(400, "Email exists")
    tok = secrets.token_hex(32)
    db().execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,datetime('now','+30 days'))", (tok, uid))
    resp.set_cookie("sess", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    return {"status": "ok"}

@app.post("/api/login")
async def log(req: Log, resp: Response):
    r = db().execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
    if not r or r["password"] != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid credentials")
    tok = secrets.token_hex(32)
    db().execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,datetime('now','+30 days'))", (tok, r["id"]))
    resp.set_cookie("sess", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    return {"status": "ok"}

@app.post("/api/logout")
async def out(req: Request, resp: Response):
    t = req.cookies.get("sess")
    if t: db().execute("DELETE FROM sessions WHERE token=?", (t,))
    resp.delete_cookie("sess")
    return {"status": "ok"}

@app.get("/api/me")
async def me(req: Request):
    u = get_user(req)
    if not u: raise HTTPException(401)
    return {"user": {"email": u["email"], "name": u.get("name")}}

@app.get("/dashboard")
async def dash(req: Request):
    u = get_user(req)
    if not u: return RedirectResponse("/")
    name = u.get("name") or u["email"]
    return HTMLResponse(f"<html><body style='background:#000;color:#fff;padding:40px;font-family:sans-serif'><h1>Welcome, {name}!</h1><p>Dashboard coming soon.</p><a href='/' style='color:#6366f1'>Back</a></body></html>")

@app.get("/settings")
async def sett(req: Request):
    u = get_user(req)
    if not u: return RedirectResponse("/")
    return HTMLResponse(f"<html><body style='background:#000;color:#fff;padding:40px;font-family:sans-serif'><h1>Settings</h1><p>Email: {u['email']}</p><p>Plan: Free</p><a href='/' style='color:#6366f1'>Back</a></body></html>")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))