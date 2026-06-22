from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib, secrets, os, sys, json, sqlite3

app = FastAPI(title="MCP Hub", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# === Database ===
DB = os.path.join(os.path.dirname(__file__), "mcp_hub.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, name TEXT, provider TEXT DEFAULT 'local', plan TEXT DEFAULT 'free', api_key TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT, expires_at TEXT);
        CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, name TEXT, email TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    c.commit(); c.close()

init_db()

# === Models ===
class RegisterReq(BaseModel): email: str; password: str
class LoginReq(BaseModel): email: str; password: str
class ContactReq(BaseModel): name: str; email: str; message: str
class ServerCreate(BaseModel): name: str; description: str; url: str; category: str = "general"; tags: List[str] = []; requires_auth: bool = False

# === Helpers ===
def get_user(request: Request):
    token = request.cookies.get("session_token")
    if not token: return None
    c = db()
    row = c.execute("SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires_at>datetime('now')", (token,)).fetchone()
    c.close()
    return dict(row) if row else None

def create_user(email, password=None, name=None, provider='local'):
    uid = hashlib.md5(email.encode()).hexdigest()[:12]
    pw = hashlib.sha256(password.encode()).hexdigest() if password else None
    key = secrets.token_hex(32)
    try:
        c = db()
        c.execute("INSERT INTO users (id,email,password_hash,name,provider,api_key) VALUES (?,?,?,?,?,?)", (uid, email, pw, name, provider, key))
        c.commit(); c.close()
        return {"id": uid, "email": email, "name": name, "plan": "free"}
    except:
        c.close()
        c = db()
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        c.close()
        return dict(row) if row else None

def make_session(uid):
    tok = secrets.token_hex(32)
    c = db()
    c.execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,datetime('now','+30 days'))", (tok, uid))
    c.commit(); c.close()
    return tok

# === Routes ===
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/auth/register")
async def register(req: RegisterReq, response: Response):
    u = create_user(req.email, req.password)
    if not u: raise HTTPException(400, "Email exists")
    tok = make_session(u["id"])
    response.set_cookie("session_token", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    return {"status": "ok", "user": {"id": u["id"], "email": u["email"], "plan": u["plan"]}}

@app.post("/api/auth/login")
async def login(req: LoginReq, response: Response):
    c = db()
    row = c.execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
    c.close()
    if not row or row["password_hash"] != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid credentials")
    tok = make_session(row["id"])
    response.set_cookie("session_token", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    return {"status": "ok", "user": {"id": row["id"], "email": row["email"], "plan": row["plan"]}}

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    tok = request.cookies.get("session_token")
    if tok:
        c = db(); c.execute("DELETE FROM sessions WHERE token=?", (tok,)); c.commit(); c.close()
    response.delete_cookie("session_token")
    return {"status": "ok"}

@app.get("/api/auth/me")
async def me(request: Request):
    u = get_user(request)
    if not u: raise HTTPException(401, "Not authenticated")
    return {"user": {"id": u["id"], "email": u["email"], "name": u.get("name"), "plan": u.get("plan")}}

@app.post("/api/feedback")
async def feedback(req: ContactReq):
    c = db()
    c.execute("INSERT INTO contacts (name,email,message) VALUES (?,?,?)", (req.name, req.email, req.message))
    c.commit(); c.close()
    return {"status": "ok", "message": "Message received!"}

@app.get("/api/servers")
async def servers():
    return {"servers": [
        {"id": "1", "name": "GitHub", "description": "GitHub API for AI agents", "url": "https://api.github.com/mcp", "category": "development"},
        {"id": "2", "name": "Slack", "description": "Slack integration", "url": "https://slack.com/api/mcp", "category": "communication"},
        {"id": "3", "name": "Notion", "description": "Notion knowledge base", "url": "https://notion.so/api/mcp", "category": "productivity"},
        {"id": "4", "name": "PostgreSQL", "description": "PostgreSQL database", "url": "postgresql://localhost:5432/mcp", "category": "database"},
    ], "total": 4}

@app.get("/api/plans")
async def plans():
    return {"plans": {"free": {"name": "Free", "price": 0}, "pro": {"name": "Pro", "price": 6.99}, "enterprise": {"name": "Enterprise", "price": 29.99}}}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
