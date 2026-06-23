from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import hashlib, secrets, os, sqlite3, json, datetime

app = FastAPI(title="MCP Hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB = "/tmp/mcp_hub_v5.db" if os.path.exists("/tmp") else "app.db"

# ── Database ──────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    d = db()
    d.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE, password TEXT, name TEXT,
            plan TEXT DEFAULT 'free', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, user_id TEXT, expires_at TEXT
        );
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, user_id TEXT, name TEXT, type TEXT,
            status TEXT DEFAULT 'active', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT, requests INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT,
            details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id TEXT PRIMARY KEY, name TEXT, description TEXT,
            category TEXT, url TEXT, verified INTEGER DEFAULT 0
        );
    """)
    # Add plan column if missing (old db)
    try:
        d.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'")
    except: pass
    try:
        d.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
    except: pass
    # Seed MCP catalog
    servers = [
        ("github", "GitHub", "Repositories, issues, PRs, actions", "development", "https://api.githubcopilot.com/mcp/", 1),
        ("slack", "Slack", "Messages, channels, users", "communication", "https://mcp.slack.com/", 1),
        ("notion", "Notion", "Pages, databases, blocks", "productivity", "https://mcp.notion.com/", 1),
        ("postgres", "PostgreSQL", "Database queries, schema", "database", "https://mcp.postgres.com/", 1),
        ("filesystem", "Filesystem", "Read/write files", "system", "https://mcp.filesystem.com/", 1),
        ("browser", "Browser", "Web scraping, automation", "web", "https://mcp.browser.com/", 0),
        ("docker", "Docker", "Containers, images, compose", "devops", "https://mcp.docker.com/", 0),
        ("stripe", "Stripe", "Payments, subscriptions", "finance", "https://mcp.stripe.com/", 0),
    ]
    for s in servers:
        d.execute("INSERT OR IGNORE INTO mcp_servers VALUES (?,?,?,?,?,?)", s)
    d.commit(); d.close()

init()

def get_user(req: Request):
    t = req.cookies.get("sess")
    if not t: return None
    r = db().execute("SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires_at>datetime('now')", (t,)).fetchone()
    return dict(r) if r else None

def log_action(user_id, action, details=""):
    db().execute("INSERT INTO audit_log (user_id, action, details) VALUES (?,?,?)", (user_id, action, details))

# ── Models ────────────────────────────────────────────────
class Reg(BaseModel): email: str; password: str; name: str = ""
class Log(BaseModel): email: str; password: str
class AgentCreate(BaseModel): name: str; type: str = "generic"
class UpgradeReq(BaseModel): plan: str

# ── HTML ──────────────────────────────────────────────────
HTML_PAGE = open("index.html").read() if os.path.exists("index.html") else ""

# ── Routes ────────────────────────────────────────────────
@app.get("/")
async def home(req: Request):
    return HTMLResponse(HTML_PAGE)

@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.datetime.now().isoformat()}

# Auth
@app.post("/api/register")
async def reg(req: Reg, resp: Response):
    uid = hashlib.md5(req.email.encode()).hexdigest()[:12]
    pw = hashlib.sha256(req.password.encode()).hexdigest()
    d = db()
    try:
        d.execute("INSERT INTO users (id,email,password,name) VALUES (?,?,?,?)", (uid, req.email, pw, req.name))
        d.commit()
    except Exception as e:
        d.close()
        raise HTTPException(400, "Email already registered")
    d.close()
    tok = secrets.token_hex(32)
    db().execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,datetime('now','+30 days'))", (tok, uid))
    resp.set_cookie("sess", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    log_action(uid, "register")
    return {"status": "ok", "user": {"email": req.email, "name": req.name, "plan": "free"}}

@app.post("/api/login")
async def log(req: Log, resp: Response):
    r = db().execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
    if not r or r["password"] != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid email or password")
    tok = secrets.token_hex(32)
    db().execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,datetime('now','+30 days'))", (tok, r["id"]))
    resp.set_cookie("sess", tok, httponly=True, max_age=30*24*3600, samesite="lax")
    log_action(r["id"], "login")
    return {"status": "ok", "user": {"email": r["email"], "name": r["name"], "plan": r["plan"]}}

@app.post("/api/logout")
async def out(req: Request, resp: Response):
    t = req.cookies.get("sess")
    if t:
        u = get_user(req)
        if u: log_action(u["id"], "logout")
        db().execute("DELETE FROM sessions WHERE token=?", (t,))
    resp.delete_cookie("sess")
    return {"status": "ok"}

@app.get("/api/me")
async def me(req: Request):
    u = get_user(req)
    if not u: raise HTTPException(401)
    return {"user": {"email": u["email"], "name": u.get("name"), "plan": u["plan"], "created_at": u["created_at"]}}

# MCP Catalog
@app.get("/api/servers")
async def list_servers():
    rows = db().execute("SELECT * FROM mcp_servers ORDER BY verified DESC, name").fetchall()
    return {"servers": [dict(r) for r in rows]}

@app.get("/api/servers/{sid}")
async def get_server(sid: str):
    r = db().execute("SELECT * FROM mcp_servers WHERE id=?", (sid,)).fetchone()
    if not r: raise HTTPException(404)
    return dict(r)

# Agents
@app.get("/api/agents")
async def list_agents(req: Request):
    u = get_user(req)
    if not u: raise HTTPException(401)
    rows = db().execute("SELECT * FROM agents WHERE user_id=? ORDER BY created_at DESC", (u["id"],)).fetchall()
    return {"agents": [dict(r) for r in rows]}

@app.post("/api/agents")
async def create_agent(req: AgentCreate, request: Request):
    u = get_user(request)
    if not u: raise HTTPException(401)
    # Plan limits
    count = db().execute("SELECT COUNT(*) FROM agents WHERE user_id=?", (u["id"],)).fetchone()[0]
    limits = {"free": 1, "pro": 10, "enterprise": 100}
    limit = limits.get(u["plan"], 1)
    if count >= limit:
        raise HTTPException(403, f"Plan '{u['plan']}' limited to {limit} agents. Upgrade for more.")
    aid = secrets.token_hex(8)
    db().execute("INSERT INTO agents (id,user_id,name,type) VALUES (?,?,?,?)", (aid, u["id"], req.name, req.type))
    db().commit()
    log_action(u["id"], "agent_create", req.name)
    return {"id": aid, "name": req.name, "type": req.type, "status": "active"}

@app.delete("/api/agents/{aid}")
async def delete_agent(aid: str, req: Request):
    u = get_user(req)
    if not u: raise HTTPException(401)
    db().execute("DELETE FROM agents WHERE id=? AND user_id=?", (aid, u["id"]))
    db().commit()
    log_action(u["id"], "agent_delete", aid)
    return {"status": "ok"}

# Dashboard stats
@app.get("/api/stats")
async def stats(req: Request):
    u = get_user(req)
    if not u: raise HTTPException(401)
    agents = db().execute("SELECT COUNT(*) FROM agents WHERE user_id=?", (u["id"],)).fetchone()[0]
    active = db().execute("SELECT COUNT(*) FROM agents WHERE user_id=? AND status='active'", (u["id"],)).fetchone()[0]
    total_req = db().execute("SELECT COALESCE(SUM(requests),0) FROM agents WHERE user_id=?", (u["id"],)).fetchone()[0]
    recent = db().execute("SELECT * FROM audit_log WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (u["id"],)).fetchall()
    return {
        "agents": {"total": agents, "active": active},
        "requests": total_req,
        "plan": u["plan"],
        "recent_activity": [dict(r) for r in recent]
    }

# Upgrade
PLANS = {"free": 0, "pro": 6.99, "enterprise": 29.99}

@app.post("/api/upgrade")
async def upgrade(req: UpgradeReq, request: Request):
    u = get_user(request)
    if not u: raise HTTPException(401)
    if req.plan not in PLANS:
        raise HTTPException(400, f"Invalid plan. Choose: {', '.join(PLANS.keys())}")
    db().execute("UPDATE users SET plan=? WHERE id=?", (req.plan, u["id"]))
    db().commit()
    log_action(u["id"], "upgrade", req.plan)
    return {"status": "ok", "plan": req.plan}

@app.get("/api/plans")
async def plans():
    features = {
        "free": {"agents": 1, "servers": 3, "support": "community", "audit": False},
        "pro": {"agents": 10, "servers": 50, "support": "email", "audit": True},
        "enterprise": {"agents": 100, "servers": 999, "support": "24/7", "audit": True},
    }
    return {"plans": {k: {"price": PLANS[k], **features[k]} for k in PLANS}}

# Dashboard / Settings pages
@app.get("/dashboard")
async def dash(req: Request):
    u = get_user(req)
    if not u: return RedirectResponse("/")
    return HTMLResponse(f"""<html><body style="background:#000;color:#fff;padding:40px;font-family:sans-serif">
    <h1>Dashboard</h1><p>Welcome, {u.get('name') or u['email']}!</p>
    <p>Plan: {u['plan']}</p><a href="/" style="color:#6366f1">Back</a></body></html>""")

@app.get("/settings")
async def sett(req: Request):
    u = get_user(req)
    if not u: return RedirectResponse("/")
    return HTMLResponse(f"""<html><body style="background:#000;color:#fff;padding:40px;font-family:sans-serif">
    <h1>Settings</h1><p>Email: {u['email']}</p><p>Plan: {u['plan']}</p>
    <a href="/" style="color:#6366f1">Back</a></body></html>""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
