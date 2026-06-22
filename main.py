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
DB = "mcp_hub.db"

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
        CREATE TABLE IF NOT EXISTS user_settings (user_id TEXT PRIMARY KEY, notifications INTEGER DEFAULT 1, theme TEXT DEFAULT 'dark', language TEXT DEFAULT 'en');
    """)
    c.commit(); c.close()

init_db()

# === Models ===
class RegisterReq(BaseModel): email: str; password: str
class LoginReq(BaseModel): email: str; password: str
class ContactReq(BaseModel): name: str; email: str; message: str
class SettingsReq(BaseModel): name: Optional[str] = None; notifications: Optional[int] = None; theme: Optional[str] = None

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
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    u = get_user(request)
    if not u: return RedirectResponse("/")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard — MCP Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#000;color:#fff;line-height:1.6}}
header{{position:fixed;top:0;left:0;right:0;z-index:100;padding:16px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.5);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.08)}}
.logo{{display:flex;align-items:center;gap:10px;text-decoration:none;color:#fff;font-weight:800;font-size:18px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#06b6d4);border-radius:9px;display:flex;align-items:center;justify-content:center}}
.nav-btns{{display:flex;gap:8px}}
.btn{{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:9px;font-size:14px;font-weight:600;text-decoration:none;border:none;cursor:pointer;transition:all 0.3s}}
.btn-ghost{{background:transparent;color:#fff;border:1px solid rgba(255,255,255,0.15)}}
.btn-ghost:hover{{border-color:rgba(255,255,255,0.3)}}
.btn-primary{{background:linear-gradient(135deg,#6366f1,#06b6d4);color:#fff}}
.main{{padding:100px 40px 60px;max-width:1200px;margin:0 auto}}
h1{{font-size:32px;font-weight:800;margin-bottom:8px}}
.subtitle{{color:rgba(255,255,255,0.5);margin-bottom:40px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:40px}}
.stat-card{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px}}
.stat-card h3{{font-size:28px;font-weight:800;background:linear-gradient(135deg,#6366f1,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.stat-card p{{font-size:13px;color:rgba(255,255,255,0.4);margin-top:4px}}
.section{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:18px;padding:30px;margin-bottom:20px}}
.section h2{{font-size:18px;font-weight:700;margin-bottom:16px}}
.agent-list{{display:flex;flex-direction:column;gap:12px}}
.agent-item{{display:flex;align-items:center;justify-content:space-between;padding:14px;background:rgba(255,255,255,0.03);border-radius:12px}}
.agent-item .name{{font-weight:600;font-size:14px}}
.agent-item .status{{font-size:12px;padding:4px 10px;border-radius:100px}}
.status-active{{background:rgba(34,197,94,0.15);color:#22c55e}}
.status-inactive{{background:rgba(248,113,113,0.15);color:#f87171}}
@media(max-width:768px){{header{{padding:12px 16px}}.main{{padding:80px 16px 40px}}.stats{{grid-template-columns:1fr}}}}
</style></head><body>
<header>
<a href="/" class="logo"><div class="logo-icon">+</div>MCP Hub</a>
<div class="nav-btns">
<a href="/settings" class="btn btn-ghost">⚙️ Settings</a>
<button class="btn btn-ghost" onclick="logout()">🚪 Log out</button>
</div>
</header>
<div class="main">
<h1>Welcome, {u.get('name') or u['email'].split('@')[0]}!</h1>
<p class="subtitle">Manage your AI agents and MCP servers.</p>
<div class="stats">
<div class="stat-card"><h3>1</h3><p>Active Agent</p></div>
<div class="stat-card"><h3>3</h3><p>MCP Servers</p></div>
<div class="stat-card"><h3>0</h3><p>Audit Logs</p></div>
<div class="stat-card"><h3>Free</h3><p>Current Plan</p></div>
</div>
<div class="section">
<h2>Your Agents</h2>
<div class="agent-list">
<div class="agent-item"><span class="name">🤖 Default Agent</span><span class="status status-active">Active</span></div>
</div>
</div>
<div class="section">
<h2>Quick Actions</h2>
<div style="display:flex;gap:12px;flex-wrap:wrap">
<button class="btn btn-primary" onclick="showToast('Coming soon!')">+ Add Agent</button>
<button class="btn btn-ghost" onclick="showToast('Coming soon!')">📂 Browse Servers</button>
<button class="btn btn-ghost" onclick="showToast('Coming soon!')">📊 View Logs</button>
</div>
</div>
</div>
<div id="toast" style="display:none;position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.2);color:#fff;padding:12px 24px;border-radius:10px;font-size:14px;z-index:9999;"></div>
<script>
function showToast(msg){{const t=document.getElementById('toast');t.textContent=msg;t.style.display='block';t.style.opacity='1';setTimeout(()=>{{t.style.opacity='0';setTimeout(()=>t.style.display='none',300);}},3000);}}
async function logout(){{await fetch('/api/auth/logout',{{method:'POST'}});location.href='/';}}
</script>
</body></html>"""

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    u = get_user(request)
    if not u: return RedirectResponse("/")
    c = db()
    s = c.execute("SELECT * FROM user_settings WHERE user_id=?", (u["id"],)).fetchone()
    c.close()
    if not s:
        c = db()
        c.execute("INSERT INTO user_settings (user_id) VALUES (?)", (u["id"],))
        c.commit()
        s = {"notifications": 1, "theme": "dark", "language": "en"}
        c.close()
    else:
        s = dict(s)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Settings — MCP Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#000;color:#fff;line-height:1.6}}
header{{position:fixed;top:0;left:0;right:0;z-index:100;padding:16px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.5);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.08)}}
.logo{{display:flex;align-items:center;gap:10px;text-decoration:none;color:#fff;font-weight:800;font-size:18px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#06b6d4);border-radius:9px;display:flex;align-items:center;justify-content:center}}
.nav-btns{{display:flex;gap:8px}}
.btn{{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:9px;font-size:14px;font-weight:600;text-decoration:none;border:none;cursor:pointer;transition:all 0.3s}}
.btn-ghost{{background:transparent;color:#fff;border:1px solid rgba(255,255,255,0.15)}}
.btn-ghost:hover{{border-color:rgba(255,255,255,0.3)}}
.btn-primary{{background:linear-gradient(135deg,#6366f1,#06b6d4);color:#fff}}
.main{{padding:100px 40px 60px;max-width:600px;margin:0 auto}}
h1{{font-size:32px;font-weight:800;margin-bottom:30px}}
.section{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:18px;padding:30px;margin-bottom:20px}}
.section h2{{font-size:18px;font-weight:700;margin-bottom:16px}}
.form-group{{margin-bottom:16px}}
.form-group label{{display:block;font-size:13px;color:rgba(255,255,255,0.5);margin-bottom:6px}}
.form-group input,.form-group select{{width:100%;padding:12px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#fff;font-size:14px;font-family:inherit}}
.form-group input:focus,.form-group select:focus{{outline:none;border-color:#6366f1}}
.toggle{{display:flex;align-items:center;justify-content:space-between;padding:12px 0}}
.toggle span{{font-size:14px}}
.toggle-btn{{width:48px;height:26px;border-radius:13px;background:rgba(255,255,255,0.1);position:relative;cursor:pointer;transition:all 0.3s}}
.toggle-btn.active{{background:linear-gradient(135deg,#6366f1,#06b6d4)}}
.toggle-btn::after{{content:'';position:absolute;width:20px;height:20px;border-radius:50%;background:#fff;top:3px;left:3px;transition:all 0.3s}}
.toggle-btn.active::after{{left:25px}}
@media(max-width:768px){{header{{padding:12px 16px}}.main{{padding:80px 16px 40px}}}}
</style></head><body>
<header>
<a href="/" class="logo"><div class="logo-icon">+</div>MCP Hub</a>
<div class="nav-btns">
<a href="/dashboard" class="btn btn-ghost">📊 Dashboard</a>
<button class="btn btn-ghost" onclick="logout()">🚪 Log out</button>
</div>
</header>
<div class="main">
<h1>Settings</h1>
<div class="section">
<h2>Profile</h2>
<div class="form-group"><label>Display Name</label><input id="setName" value="{u.get('name') or ''}" placeholder="Your name"></div>
<div class="form-group"><label>Email</label><input value="{u['email']}" disabled style="opacity:0.5"></div>
</div>
<div class="section">
<h2>Preferences</h2>
<div class="toggle"><span>Email Notifications</span><div class="toggle-btn {'active' if s.get('notifications') else ''}" onclick="this.classList.toggle('active')" id="toggleNotif"></div></div>
<div class="toggle" style="margin-top:12px"><span>Dark Theme</span><div class="toggle-btn active" onclick="this.classList.toggle('active')" id="toggleTheme"></div></div>
</div>
<div class="section">
<h2>Account</h2>
<p style="font-size:13px;color:rgba(255,255,255,0.4);margin-bottom:12px;">Plan: <strong>Free</strong></p>
<button class="btn btn-ghost" onclick="showToast('Coming soon!')">Upgrade to Pro</button>
</div>
<div style="display:flex;gap:12px;margin-top:20px">
<button class="btn btn-primary" onclick="saveSettings()">Save Changes</button>
<a href="/dashboard" class="btn btn-ghost">Cancel</a>
</div>
</div>
<div id="toast" style="display:none;position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.2);color:#fff;padding:12px 24px;border-radius:10px;font-size:14px;z-index:9999;"></div>
<script>
function showToast(msg){{const t=document.getElementById('toast');t.textContent=msg;t.style.display='block';t.style.opacity='1';setTimeout(()=>{{t.style.opacity='0';setTimeout(()=>t.style.display='none',300);}},3000);}}
async function saveSettings(){{const name=document.getElementById('setName').value;const notif=document.getElementById('toggleNotif').classList.contains('active')?1:0;const theme=document.getElementById('toggleTheme').classList.contains('active')?'dark':'light';try{{const r=await(await fetch('/api/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name,notifications:notif,theme}})}})).json();showToast('Settings saved!');}}catch(e){{showToast('Error saving');}}}}
async function logout(){{await fetch('/api/auth/logout',{{method:'POST'}});location.href='/';}}
</script>
</body></html>"""

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

@app.post("/api/settings")
async def save_settings(req: SettingsReq, request: Request):
    u = get_user(request)
    if not u: raise HTTPException(401, "Not authenticated")
    c = db()
    c.execute("INSERT OR REPLACE INTO user_settings (user_id,notifications,theme) VALUES (?,?,?)", (u["id"], req.notifications or 1, req.theme or "dark"))
    if req.name:
        c.execute("UPDATE users SET name=? WHERE id=?", (req.name, u["id"]))
    c.commit(); c.close()
    return {"status": "ok"}

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
    ]}

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
