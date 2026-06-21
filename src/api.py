"""
MCP Hub - Full Feature API (No payment required)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from models import RegistrationService

app = FastAPI(title="MCP Hub", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

servers_db = {}
tokens_db = []
audit_db = []
contacts_db = []
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

PLANS = {"free": {"name": "Free", "price": 0, "period": "month", "features": ["1 agent", "3 MCP servers", "Basic OAuth", "100 audit logs"]}, "pro": {"name": "Pro", "price": 6.99, "period": "month", "features": ["Up to 10 agents", "50 MCP servers", "OAuth 2.0 + SSO", "Full audit (10K)", "Rate limiting", "Email support"], "popular": True}, "enterprise": {"name": "Enterprise", "price": 14.99, "period": "month", "features": ["Up to 100 agents", "Unlimited MCP servers", "OAuth + SSO + SAML", "Unlimited audit", "SLA 99.9%", "Priority support"]}}

DEFAULT_SERVERS = [
    {"name": "GitHub", "description": "GitHub API for AI agents", "url": "https://api.github.com/mcp", "category": "development", "tags": ["git", "code"], "requires_auth": True},
    {"name": "Slack", "description": "Slack integration for agents", "url": "https://slack.com/api/mcp", "category": "communication", "tags": ["chat"], "requires_auth": True},
    {"name": "Notion", "description": "Notion knowledge base", "url": "https://notion.so/api/mcp", "category": "productivity", "tags": ["notes"], "requires_auth": True},
    {"name": "PostgreSQL", "description": "PostgreSQL database", "url": "postgresql://localhost:5432/mcp", "category": "database", "tags": ["sql"], "requires_auth": True},
    {"name": "Pinecone", "description": "Vector search", "url": "https://api.pinecone.io/mcp", "category": "ai", "tags": ["vector", "embeddings"], "requires_auth": True},
    {"name": "Sentry", "description": "Error monitoring", "url": "https://sentry.io/api/mcp", "category": "monitoring", "tags": ["errors"], "requires_auth": True},
    {"name": "Stripe", "description": "Payments API", "url": "https://api.stripe.com/mcp", "category": "payments", "tags": ["billing"], "requires_auth": True},
    {"name": "S3", "description": "Object storage", "url": "https://s3.amazonaws.com/mcp", "category": "storage", "tags": ["files"], "requires_auth": True},
]

for s in DEFAULT_SERVERS:
    sid = hashlib.md5(s["name"].encode()).hexdigest()[:12]
    s["id"] = sid
    s["created_at"] = datetime.now().isoformat()
    servers_db[sid] = s

@app.get("/", response_class=HTMLResponse)
async def homepage():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    try:
        user = auth_svc.register(req.email, req.password)
        return {"status": "ok", "user": {"id": user["id"], "email": user["email"], "plan": user["plan"], "api_key": user["api_key"]}}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    try:
        user = auth_svc.login(req.email, req.password)
        return {"status": "ok", "user": {"id": user["id"], "email": user["email"], "plan": user["plan"], "api_key": user["api_key"]}}
    except ValueError as e:
        raise HTTPException(401, str(e))

@app.get("/api/users/me")
async def get_me(user_id: str):
    user = auth_svc.get_user(user_id)
    if not user: raise HTTPException(404, "Not found")
    return {"user": user, "subscription": auth_svc.get_sub(user_id)}

@app.post("/api/feedback")
async def feedback(req: ContactRequest):
    contacts_db.append({"name": req.name, "email": req.email, "message": req.message, "time": datetime.now().isoformat()})
    return {"status": "ok", "message": "Message received!"}

@app.get("/api/servers")
async def list_servers(category: str = None, search: str = None):
    servers = list(servers_db.values())
    if category: servers = [s for s in servers if s["category"] == category]
    if search:
        sl = search.lower()
        servers = [s for s in servers if sl in s["name"].lower() or sl in s["description"].lower()]
    return {"servers": servers, "total": len(servers)}

@app.get("/api/servers/{server_id}")
async def get_server(server_id: str):
    if server_id not in servers_db: raise HTTPException(404, "Not found")
    return servers_db[server_id]

@app.post("/api/servers")
async def add_server(server: ServerCreate):
    server_id = hashlib.md5(server.name.encode()).hexdigest()[:12]
    data = server.dict(); data["id"] = server_id; data["created_at"] = datetime.now().isoformat()
    servers_db[server_id] = data
    audit_db.append({"action": "server_added", "server_id": server_id, "timestamp": datetime.now().isoformat()})
    return data

@app.post("/api/auth/start")
async def start_auth(auth: AuthStart):
    state = secrets.token_hex(16)
    return {"auth_url": f"#oauth?state={state}", "state": state}

@app.get("/api/tokens")
async def list_tokens(): return {"tokens": tokens_db}

@app.get("/api/audit")
async def get_audit(limit: int = 50): return {"logs": audit_db[-limit:]}

@app.get("/api/stats")
async def get_stats(): return {"servers": len(servers_db), "tokens": len(tokens_db), "audit_logs": len(audit_db)}

@app.get("/api/plans")
async def get_plans(): return {"plans": PLANS}

@app.post("/api/checkout")
async def create_checkout(req: CheckoutRequest):
    if req.plan not in PLANS: raise HTTPException(400, "Invalid plan")
    return {"plan": req.plan, "amount": PLANS[req.plan]["price"], "status": "registered", "message": "Thanks! Payment coming soon."}

@app.get("/health")
async def health(): return {"status": "ok", "service": "MCP Hub", "version": "2.0.0", "servers": len(servers_db)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)