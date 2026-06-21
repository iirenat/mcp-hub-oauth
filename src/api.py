"""
MCP Hub - Full API with Auth (Google + GitHub OAuth, Sessions, SQLite)
"""
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))
from database import (
    create_user, get_user_by_email, get_user_by_id,
    verify_password, create_session, get_session, delete_session,
    get_db, init_db
)
from models import RegistrationService

app = FastAPI(title="MCP Hub", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# OAuth config - set these in Render environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "https://mcp-hub-clean-2-0.onrender.com")

auth_svc = RegistrationService()

class ServerCreate(BaseModel):
    name: str; description: str; url: str; category: str = "general"; tags: List[str] = []; requires_auth: bool = False

class AuthStart(BaseModel):
    server_id: str; user_id: str

class RegisterRequest(BaseModel):
    email: str; password: str

class LoginRequest(BaseModel):
    email: str; password: str

class ContactRequest(BaseModel):
    name: str; email: str; message: str

class CheckoutRequest(BaseModel):
    plan: str; email: str

PLANS = {
    "free": {"name": "Free", "price": 0, "period": "month", "features": ["1 agent", "3 MCP servers", "Basic OAuth", "100 audit logs"]},
    "pro": {"name": "Pro", "price": 6.99, "period": "month", "features": ["Up to 10 agents", "50 MCP servers", "OAuth 2.0 + SSO", "Full audit (10K)", "Rate limiting", "Email support"], "popular": True},
    "enterprise": {"name": "Enterprise", "price": 29.99, "period": "month", "features": ["Unlimited agents", "Unlimited MCP servers", "OAuth + SSO + SAML", "Unlimited audit logs", "SLA 99.9%", "Priority 24/7 support", "Custom integrations"]}
}

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if token:
        return get_session(token)
    return None

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    user = get_current_user(request)
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    # Inject user data
    user_json = json.dumps(user) if user else "null"
    html = html.replace("/* USER_DATA */", f"const currentUser = {user_json};")
    return html

# === Auth Routes ===

@app.post("/api/auth/register")
async def register(req: RegisterRequest, response: Response):
    try:
        user = auth_svc.register(req.email, req.password)
        token = create_session(user["id"])
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=30*24*3600, samesite="lax")
        return {"status": "ok", "user": {"id": user["id"], "email": user["email"], "plan": user["plan"]}}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    try:
        user = auth_svc.login(req.email, req.password)
        token = create_session(user["id"])
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=30*24*3600, samesite="lax")
        return {"status": "ok", "user": {"id": user["id"], "email": user["email"], "plan": user["plan"]}}
    except ValueError as e:
        raise HTTPException(401, str(e))

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        delete_session(token)
    response.delete_cookie("session_token")
    return {"status": "ok"}

@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"user": {"id": user["user_id"], "email": user["email"], "name": user.get("name"), "plan": user.get("plan")}}

# === Google OAuth ===
@app.get("/api/auth/google")
async def google_auth():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google OAuth not configured")
    url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={OAUTH_REDIRECT_URI}/api/auth/google/callback&response_type=code&scope=email profile"
    return RedirectResponse(url)

@app.get("/api/auth/google/callback")
async def google_callback(code: str, response: Response):
    # Exchange code for token (simplified - in production use proper OAuth library)
    import urllib.request
    import urllib.parse
    
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": f"{OAUTH_REDIRECT_URI}/api/auth/google/callback",
        "grant_type": "authorization_code"
    }).encode()
    
    try:
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=token_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_info = json.loads(resp.read())
        
        # Get user info
        user_req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_info['access_token']}"}
        )
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            google_user = json.loads(resp.read())
        
        user = create_user(
            email=google_user["email"],
            name=google_user.get("name"),
            provider="google",
            provider_id=google_user["id"]
        )
        token = create_session(user["id"])
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=30*24*3600, samesite="lax")
        return RedirectResponse("/")
    except Exception as e:
        return RedirectResponse(f"/?error=google_auth_failed&message={str(e)}")

# === GitHub OAuth ===
@app.get("/api/auth/github")
async def github_auth():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(500, "GitHub OAuth not configured")
    url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={OAUTH_REDIRECT_URI}/api/auth/github/callback&scope=user:email"
    return RedirectResponse(url)

@app.get("/api/auth/github/callback")
async def github_callback(code: str, response: Response):
    import urllib.request
    import urllib.parse
    
    # Exchange code for token
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "redirect_uri": f"{OAUTH_REDIRECT_URI}/api/auth/github/callback"
    }).encode()
    
    try:
        req = urllib.request.Request("https://github.com/login/oauth/access_token", data=token_data, method="POST")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_info = json.loads(resp.read())
        
        # Get user info
        user_req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token_info['access_token']}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            github_user = json.loads(resp.read())
        
        # Get email
        email_req = urllib.request.Request(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"token {token_info['access_token']}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(email_req, timeout=10) as resp:
            emails = json.loads(resp.read())
            primary_email = next((e["email"] for e in emails if e["primary"]), emails[0]["email"] if emails else None)
        
        if not primary_email:
            return RedirectResponse("/?error=github_no_email")
        
        user = create_user(
            email=primary_email,
            name=github_user.get("name") or github_user.get("login"),
            provider="github",
            provider_id=str(github_user["id"])
        )
        token = create_session(user["id"])
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=30*24*3600, samesite="lax")
        return RedirectResponse("/")
    except Exception as e:
        return RedirectResponse(f"/?error=github_auth_failed&message={str(e)}")

# === Servers ===

@app.get("/api/servers")
async def list_servers(category: str = None, search: str = None):
    servers = list(servers_db.values()) if 'servers_db' in dir() else []
    if category:
        servers = [s for s in servers if s["category"] == category]
    if search:
        sl = search.lower()
        servers = [s for s in servers if sl in s["name"].lower() or sl in s["description"].lower()]
    return {"servers": servers, "total": len(servers)}

@app.get("/api/servers/{server_id}")
async def get_server(server_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Not found")
    return dict(row)

@app.post("/api/servers")
async def add_server(server: ServerCreate, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required")
    server_id = hashlib.md5(server.name.encode()).hexdigest()[:12]
    data = server.dict()
    data["id"] = server_id
    data["created_at"] = datetime.now().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO servers (id, name, description, url, category, tags, requires_auth, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (data["id"], data["name"], data["description"], data["url"], data["category"], json.dumps(data["tags"]), int(data["requires_auth"]), data["created_at"]))
    conn.commit()
    conn.close()
    return data

@app.post("/api/auth/start")
async def start_auth(auth: AuthStart):
    state = secrets.token_hex(16)
    return {"auth_url": f"#oauth?state={state}", "state": state}

@app.get("/api/tokens")
async def list_tokens():
    return {"tokens": []}

@app.get("/api/audit")
async def get_audit(limit: int = 50, request: Request = None):
    user = get_current_user(request) if request else None
    conn = get_db()
    if user:
        rows = conn.execute("SELECT * FROM audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user["user_id"], limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return {"logs": [dict(r) for r in rows]}

@app.get("/api/stats")
async def get_stats():
    conn = get_db()
    servers_count = conn.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    audit_count = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM servers").fetchall()]
    conn.close()
    return {"servers": servers_count, "users": users_count, "audit_logs": audit_count, "categories": categories}

@app.get("/api/plans")
async def get_plans():
    return {"plans": PLANS}

@app.post("/api/checkout")
async def create_checkout(req: CheckoutRequest, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required")
    if req.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    return {"plan": req.plan, "amount": PLANS[req.plan]["price"], "status": "registered", "message": "Thanks! Payment integration coming soon."}

@app.post("/api/feedback")
async def feedback(req: ContactRequest):
    conn = get_db()
    conn.execute("INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)", (req.name, req.email, req.message))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Message received!"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "MCP Hub", "version": "3.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
