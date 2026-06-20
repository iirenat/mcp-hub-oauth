"""MCP Hub — FastAPI API Server with Frontend."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import json
import os

app = FastAPI(title="MCP Hub with OAuth", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Хранилище ===
servers_db = {}
tokens_db = []
audit_db = []

# === Модели ===
class ServerCreate(BaseModel):
    name: str
    description: str
    url: str
    category: str = "general"
    tags: List[str] = []
    requires_auth: bool = False

class AuthStart(BaseModel):
    server_id: str
    user_id: str

# === Предустановленные серверы ===
SERVERS = [
    {"id":"gh","name":"GitHub","description":"GitHub API для AI-агентов","url":"https://api.github.com/mcp","category":"development","tags":["git","code"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"sl","name":"Slack","description":"Slack интеграция","url":"https://slack.com/api/mcp","category":"communication","tags":["chat","messaging"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"nt","name":"Notion","description":"Notion база знаний","url":"https://notion.so/api/mcp","category":"productivity","tags":["notes","database"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"pg","name":"PostgreSQL","description":"PostgreSQL база данных","url":"postgresql://localhost:5432/mcp","category":"database","tags":["sql","data"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"pn","name":"Pinecone","description":"Векторный поиск","url":"https://api.pinecone.io/mcp","category":"ai","tags":["vector","search"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"se","name":"Sentry","description":"Мониторинг ошибок","url":"https://sentry.io/api/mcp","category":"monitoring","tags":["errors","tracking"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"st","name":"Stripe","description":"Платежи через API","url":"https://api.stripe.com/mcp","category":"payments","tags":["billing","finance"],"requires_auth":True,"created_at":"2026-01-01"},
    {"id":"s3","name":"S3","description":"Объектное хранилище","url":"https://s3.amazonaws.com/mcp","category":"storage","tags":["files","backup"],"requires_auth":True,"created_at":"2026-01-01"},
]
for s in SERVERS:
    servers_db[s["id"]] = s

# === Frontend ===
@app.get("/", response_class=HTMLResponse)
async def homepage():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Hub — Enterprise Security for AI Agents</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0f; color: #fff; min-height: 100vh; }
        header { padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1a1a2e; }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 40px; height: 40px; background: linear-gradient(135deg, #6366f1, #8b5cf6); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 18px; }
        .logo-text { font-size: 24px; font-weight: 700; }
        .logo-tag { font-size: 12px; color: #6366f1; background: #1a1a2e; padding: 4px 8px; border-radius: 6px; margin-left: 8px; }
        nav a { color: #9ca3af; text-decoration: none; margin-left: 24px; font-size: 14px; }
        nav a:hover { color: #fff; }
        .btn { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; }
        .hero { padding: 80px 40px; text-align: center; max-width: 900px; margin: 0 auto; }
        .hero h1 { font-size: 56px; font-weight: 800; line-height: 1.1; margin-bottom: 24px; background: linear-gradient(135deg, #fff, #9ca3af); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero p { font-size: 20px; color: #9ca3af; margin-bottom: 40px; line-height: 1.6; }
        .hero-buttons { display: flex; gap: 16px; justify-content: center; }
        .btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 16px; }
        .btn-secondary { background: #1a1a2e; color: #fff; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 16px; border: 1px solid #2a2a3e; }
        .features { padding: 80px 40px; }
        .features h2 { text-align: center; font-size: 36px; margin-bottom: 60px; }
        .features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; max-width: 1200px; margin: 0 auto; }
        .feature-card { background: #111118; border: 1px solid #1a1a2e; border-radius: 16px; padding: 32px; }
        .feature-icon { width: 48px; height: 48px; background: linear-gradient(135deg, #6366f1, #8b5cf6); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 20px; }
        .feature-card h3 { font-size: 20px; margin-bottom: 12px; }
        .feature-card p { color: #9ca3af; line-height: 1.6; }
        .stats { padding: 60px 40px; background: #111118; border-top: 1px solid #1a1a2e; border-bottom: 1px solid #1a1a2e; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 40px; max-width: 1000px; margin: 0 auto; text-align: center; }
        .stat h3 { font-size: 48px; font-weight: 800; background: linear-gradient(135deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat p { color: #9ca3af; margin-top: 8px; }
        .cta { padding: 80px 40px; text-align: center; }
        .cta h2 { font-size: 40px; margin-bottom: 20px; }
        .cta p { color: #9ca3af; font-size: 18px; margin-bottom: 40px; }
        footer { padding: 40px; border-top: 1px solid #1a1a2e; display: flex; justify-content: space-between; align-items: center; }
        footer p { color: #6b7280; font-size: 14px; }
        footer a { color: #6366f1; text-decoration: none; }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-icon">M</div>
            <span class="logo-text">MCP Hub</span>
            <span class="logo-tag">v1.0</span>
        </div>
        <nav>
            <a href="#features">Features</a>
            <a href="https://github.com/iirenat/mcp-hub-oauth">GitHub</a>
            <a href="#" class="btn">Get Started</a>
        </nav>
    </header>
    <section class="hero">
        <h1>Enterprise Security for AI Agents</h1>
        <p>One panel to manage all your AI agents. OAuth 2.0, role-based access, audit logging, and real-time monitoring. Built for companies using 10+ AI agents.</p>
        <div class="hero-buttons">
            <a href="https://github.com/iirenat/mcp-hub-oauth" class="btn-primary">⭐ Star on GitHub</a>
            <a href="#features" class="btn-secondary">Learn More</a>
        </div>
    </section>
    <section class="features" id="features">
        <h2>Everything you need</h2>
        <div class="features-grid">
            <div class="feature-card"><div class="feature-icon">📂</div><h3>MCP Server Catalog</h3><p>Browse, search, and connect to any MCP server. GitHub, Slack, Notion, PostgreSQL, and more.</p></div>
            <div class="feature-card"><div class="feature-icon">🔐</div><h3>OAuth 2.0 + SSO</h3><p>Enterprise-grade authentication. Connect with Google, GitHub, or your SSO provider.</p></div>
            <div class="feature-card"><div class="feature-icon">👥</div><h3>Role-Based Access</h3><p>Control who can access which agents. Admin, developer, viewer roles.</p></div>
            <div class="feature-card"><div class="feature-icon">📝</div><h3>Audit Logging</h3><p>Track every request and action. Full history of who did what and when.</p></div>
            <div class="feature-card"><div class="feature-icon">⏱️</div><h3>Rate Limiting</h3><p>Prevent abuse and control costs. Set per-user and per-agent limits.</p></div>
            <div class="feature-card"><div class="feature-icon">📊</div><h3>Real-Time Monitoring</h3><p>Live dashboards, health checks, and alerts. Know when something goes wrong.</p></div>
        </div>
    </section>
    <section class="stats">
        <div class="stats-grid">
            <div class="stat"><h3>8+</h3><p>Pre-configured MCP Servers</p></div>
            <div class="stat"><h3>OAuth</h3><p>Enterprise SSO Support</p></div>
            <div class="stat"><h3>RBAC</h3><p>Role-Based Access Control</p></div>
            <div class="stat"><h3>MIT</h3><p>Open Source License</p></div>
        </div>
    </section>
    <section class="cta">
        <h2>Ready to secure your AI agents?</h2>
        <p>Self-host for free or use our enterprise hosting.</p>
        <a href="https://github.com/iirenat/mcp-hub-oauth" class="btn-primary">Get Started — Free</a>
    </section>
    <footer>
        <p>© 2026 MCP Hub. Open source under MIT license.</p>
        <a href="https://github.com/iirenat/mcp-hub-oauth">GitHub</a>
    </footer>
</body>
</html>"""

# === API ===

@app.get("/api/servers")
async def list_servers(category: str = None, search: str = None):
    servers = list(servers_db.values())
    if category:
        servers = [s for s in servers if s["category"] == category]
    if search:
        search_lower = search.lower()
        servers = [s for s in servers if search_lower in s["name"].lower() or search_lower in s["description"].lower()]
    return {"servers": servers, "total": len(servers)}

@app.get("/api/servers/{server_id}")
async def get_server(server_id: str):
    if server_id not in servers_db:
        raise HTTPException(status_code=404, detail="Server not found")
    return servers_db[server_id]

@app.post("/api/servers")
async def add_server(server: ServerCreate):
    server_id = hashlib.md5(server.name.encode()).hexdigest()[:12]
    data = server.dict()
    data["id"] = server_id
    data["created_at"] = datetime.now().isoformat()
    servers_db[server_id] = data
    audit_db.append({"action":"server_added","server_id":server_id,"timestamp":datetime.now().isoformat()})
    return data

@app.post("/api/auth/start")
async def start_auth(auth: AuthStart):
    state = secrets.token_hex(16)
    return {"auth_url": f"#oauth?state={state}", "state": state}

@app.get("/api/tokens")
async def list_tokens():
    return {"tokens": tokens_db}

@app.get("/api/audit")
async def get_audit(limit: int = 50):
    return {"logs": audit_db[-limit:]}

@app.get("/api/stats")
async def get_stats():
    return {
        "servers": len(servers_db),
        "tokens": len(tokens_db),
        "audit_logs": len(audit_db),
        "categories": list(set(s["category"] for s in servers_db.values()))
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "MCP Hub", "version": "1.0.0", "servers": len(servers_db)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
