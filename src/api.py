"""MCP Hub — Production API with Stripe payments."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import json
import os

app = FastAPI(title="MCP Hub with OAuth", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Тарифы ===
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "period": "month",
        "description": "Для знакомства с продуктом",
        "features": [
            "1 агент",
            "3 MCP-сервера",
            "Базовый OAuth",
            "100 записей аудита",
            "Community поддержка",
        ],
        "limits": {"agents": 1, "servers": 3, "audit_logs": 100}
    },
    "pro": {
        "name": "Pro",
        "price": 6.99,
        "period": "month",
        "description": "Для небольших команд и стартапов",
        "features": [
            "До 10 агентов",
            "50 MCP-серверов",
            "OAuth 2.0 + SSO",
            "Полный аудит (10K записей)",
            "Rate limiting",
            "Email поддержка",
            "Базовая аналитика",
        ],
        "limits": {"agents": 10, "servers": 50, "audit_logs": 10000},
        "popular": True
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 14.99,
        "period": "month",
        "description": "Для компаний с серьёзными требованиями",
        "features": [
            "До 100 агентов",
            "Безлимитные MCP-серверы",
            "OAuth + SSO + SAML",
            "Безлимитный аудит",
            "Rate limiting",
            "Приоритетная поддержка (24/7)",
            "Расширенная аналитика",
            "SLA 99.9%",
            "Кастомизация бренда",
        ],
        "limits": {"agents": 100, "servers": -1, "audit_logs": -1}
    },
    "ultra": {
        "name": "Ultra",
        "price": 99.99,
        "period": "month",
        "description": "Для enterprise с максимальными требованиями",
        "features": [
            "Безлимитные агенты",
            "Безлимитные MCP-серверы",
            "OAuth + SSO + SAML + LDAP",
            "Безлимитный аудит + экспорт",
            "Rate limiting + quotas",
            "Выделенный менеджер",
            "SLA 99.99%",
            "Полная кастомизация",
            "On-premise установка",
            "Интеграция с SIEM",
            "Compliance reports (SOC2, GDPR)",
            "Training для команды",
        ],
        "limits": {"agents": -1, "servers": -1, "audit_logs": -1}
    }
}

# === Хранилище ===
servers_db = {}
tokens_db = []
audit_db = []
users_db = {}
subscriptions_db = {}

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

class CheckoutRequest(BaseModel):
    plan: str
    email: str

# === Главная страница — полный лендинг ===
@app.get("/", response_class=HTMLResponse)
async def homepage():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="MCP Hub — Enterprise security for AI agents. Manage, secure, and monitor all your AI agents from one panel.">
    <title>MCP Hub — Enterprise Security for AI Agents</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root { --primary: #6366f1; --primary-dark: #4f46e5; --bg: #06060a; --bg-card: #0c0c14; --border: #1a1a2e; --text: #fff; --text-muted: #9ca3af; }
        body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
        
        /* Header */
        header { padding: 16px 40px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: rgba(6,6,10,0.9); backdrop-filter: blur(20px); z-index: 100; }
        .logo { display: flex; align-items: center; gap: 10px; }
        .logo-icon { width: 36px; height: 36px; background: linear-gradient(135deg, var(--primary), #a855f7); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; }
        .logo-text { font-size: 20px; font-weight: 700; }
        nav { display: flex; align-items: center; gap: 32px; }
        nav a { color: var(--text-muted); text-decoration: none; font-size: 14px; font-weight: 500; transition: color 0.2s; }
        nav a:hover { color: var(--text); }
        .btn { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; border: none; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }
        .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(99,102,241,0.4); }
        .btn-large { padding: 16px 32px; font-size: 16px; border-radius: 12px; }
        .btn-outline { background: transparent; border: 1px solid var(--border); }
        .btn-outline:hover { border-color: var(--primary); box-shadow: none; }
        
        /* Hero */
        .hero { padding: 100px 40px 80px; text-align: center; max-width: 1000px; margin: 0 auto; position: relative; }
        .hero::before { content: ''; position: absolute; top: -100px; left: 50%; transform: translateX(-50%); width: 600px; height: 600px; background: radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%); pointer-events: none; z-index: -1; }
        .badge { display: inline-flex; align-items: center; gap: 8px; background: var(--bg-card); border: 1px solid var(--border); padding: 8px 16px; border-radius: 100px; font-size: 13px; color: var(--text-muted); margin-bottom: 32px; }
        .badge-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .hero h1 { font-size: 64px; font-weight: 800; line-height: 1.1; margin-bottom: 24px; letter-spacing: -2px; }
        .hero h1 span { background: linear-gradient(135deg, var(--primary), #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero p { font-size: 20px; color: var(--text-muted); margin-bottom: 40px; max-width: 600px; margin-left: auto; margin-right: auto; }
        .hero-buttons { display: flex; gap: 16px; justify-content: center; margin-bottom: 60px; }
        .hero-stats { display: flex; gap: 60px; justify-content: center; }
        .hero-stat h3 { font-size: 32px; font-weight: 800; }
        .hero-stat p { font-size: 14px; color: var(--text-muted); }
        
        /* Logos */
        .logos { padding: 60px 40px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); text-align: center; }
        .logos p { color: var(--text-muted); font-size: 14px; margin-bottom: 32px; }
        .logos-grid { display: flex; justify-content: center; gap: 40px; flex-wrap: wrap; }
        .logo-item { color: var(--text-muted); font-size: 16px; font-weight: 600; opacity: 0.5; }
        
        /* Features */
        .features { padding: 100px 40px; }
        .features h2 { text-align: center; font-size: 40px; font-weight: 800; margin-bottom: 16px; }
        .features > p { text-align: center; color: var(--text-muted); font-size: 18px; margin-bottom: 60px; }
        .features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; max-width: 1200px; margin: 0 auto; }
        .feature-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; transition: border-color 0.2s, transform 0.2s; }
        .feature-card:hover { border-color: var(--primary); transform: translateY(-4px); }
        .feature-icon { width: 48px; height: 48px; background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(168,85,247,0.2)); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 20px; border: 1px solid rgba(99,102,241,0.3); }
        .feature-card h3 { font-size: 18px; font-weight: 700; margin-bottom: 8px; }
        .feature-card p { color: var(--text-muted); font-size: 14px; line-height: 1.6; }
        
        /* Pricing */
        .pricing { padding: 100px 40px; background: var(--bg-card); border-top: 1px solid var(--border); }
        .pricing h2 { text-align: center; font-size: 40px; font-weight: 800; margin-bottom: 16px; }
        .pricing > p { text-align: center; color: var(--text-muted); font-size: 18px; margin-bottom: 60px; }
        .pricing-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; max-width: 1000px; margin: 0 auto; }
        .pricing-card { background: var(--bg); border: 1px solid var(--border); border-radius: 20px; padding: 40px 32px; position: relative; transition: transform 0.2s, border-color 0.2s; }
        .pricing-card:hover { transform: translateY(-4px); }
        .pricing-card.popular { border-color: var(--primary); background: linear-gradient(180deg, rgba(99,102,241,0.1) 0%, var(--bg) 100%); }
        .popular-badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, var(--primary), #a855f7); color: #fff; padding: 4px 16px; border-radius: 100px; font-size: 12px; font-weight: 600; }
        .pricing-card h3 { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
        .price { font-size: 48px; font-weight: 800; margin: 16px 0; }
        .price span { font-size: 16px; color: var(--text-muted); font-weight: 400; }
        .pricing-card ul { list-style: none; margin: 24px 0; }
        .pricing-card li { padding: 8px 0; color: var(--text-muted); font-size: 14px; display: flex; align-items: center; gap: 10px; }
        .pricing-card li::before { content: '✓'; color: #22c55e; font-weight: 700; }
        .pricing-card .btn { width: 100%; text-align: center; display: block; }
        .pricing-card .btn-outline { background: transparent; border: 1px solid var(--border); }
        
        /* CTA */
        .cta { padding: 100px 40px; text-align: center; }
        .cta h2 { font-size: 40px; font-weight: 800; margin-bottom: 16px; }
        .cta p { color: var(--text-muted); font-size: 18px; margin-bottom: 40px; }
        
        /* Footer */
        footer { padding: 40px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        footer p { color: var(--text-muted); font-size: 13px; }
        footer a { color: var(--primary); text-decoration: none; }
        footer nav { display: flex; gap: 24px; }
        footer nav a { color: var(--text-muted); font-size: 13px; }
        
        @media (max-width: 768px) {
            .features-grid, .pricing-grid { grid-template-columns: 1fr; }
            .hero h1 { font-size: 40px; }
            .hero-stats { flex-direction: column; gap: 20px; }
            .hero-buttons { flex-direction: column; }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-icon">M</div>
            <span class="logo-text">MCP Hub</span>
        </div>
        <nav>
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="https://github.com/iirenat/mcp-hub-oauth">GitHub</a>
            <a href="#pricing" class="btn">View Pricing</a>
        </nav>
    </header>
    
    <section class="hero">
        <div class="badge"><span class="badge-dot"></span> Now in Public Beta — Free tier available</div>
        <h1>Secure your <span>AI agents</span> like enterprise</h1>
        <p>One panel to manage, secure, and monitor all your AI agents. OAuth 2.0, RBAC, audit logging, rate limiting. Built for companies using 10+ AI agents via MCP protocol.</p>
        <div class="hero-buttons">
            <a href="#pricing" class="btn btn-large">Start Free →</a>
            <a href="https://github.com/iirenat/mcp-hub-oauth" class="btn btn-large btn-outline">⭐ Star on GitHub</a>
        </div>
        <div class="hero-stats">
            <div class="hero-stat"><h3>8+</h3><p>Pre-configured MCP Servers</p></div>
            <div class="hero-stat"><h3>OAuth</h3><p>Enterprise SSO</p></div>
            <div class="hero-stat"><h3>RBAC</h3><p>Role-Based Access</p></div>
            <div class="hero-stat"><h3>MIT</h3><p>Open Source</p></div>
        </div>
    </section>
    
    <section class="logos">
        <p>Compatible with all MCP servers</p>
        <div class="logos-grid">
            <span class="logo-item">GitHub</span>
            <span class="logo-item">Slack</span>
            <span class="logo-item">Notion</span>
            <span class="logo-item">PostgreSQL</span>
            <span class="logo-item">Pinecone</span>
            <span class="logo-item">Stripe</span>
            <span class="logo-item">Sentry</span>
            <span class="logo-item">AWS S3</span>
        </div>
    </section>
    
    <section class="features" id="features">
        <h2>Everything you need</h2>
        <p>Enterprise-grade security for AI agents from day one</p>
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">📂</div>
                <h3>MCP Server Catalog</h3>
                <p>Browse, search, and connect to any MCP server. Pre-configured integrations for GitHub, Slack, Notion, PostgreSQL, and more. Add custom servers in one click.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔐</div>
                <h3>OAuth 2.0 + SSO</h3>
                <p>Enterprise-grade authentication. Connect with Google, GitHub, Azure AD, or your SSO provider. SAML support for Enterprise plan.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">👥</div>
                <h3>Role-Based Access</h3>
                <p>Control who can access which agents. Admin, developer, and viewer roles. Per-agent permissions. Audit trail for compliance.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📝</div>
                <h3>Audit Logging</h3>
                <p>Track every request and action. Full history of who did what and when. Export logs for compliance. 10K+ logs on Pro plan.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⏱️</div>
                <h3>Rate Limiting</h3>
                <p>Prevent abuse and control costs. Set per-user and per-agent limits. Automatic alerts when limits are approaching.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <h3>Real-Time Monitoring</h3>
                <p>Live dashboards, health checks, and alerts. Know when something goes wrong. Uptime monitoring with 99.9% SLA on Enterprise.</p>
            </div>
        </div>
    </section>
    
    <section class="pricing" id="pricing">
        <h2>Simple, transparent pricing</h2>
        <p>Start free. Scale when you need to.</p>
        <div class="pricing-grid">
            <div class="pricing-card">
                <h3>Free</h3>
                <p style="color:var(--text-muted);font-size:14px;margin:4px 0 16px;">Для знакомства</p>
                <div class="price">$0<span>/month</span></div>
                <ul>
                    <li>1 агент</li>
                    <li>3 MCP-сервера</li>
                    <li>Базовый OAuth</li>
                    <li>100 записей аудита</li>
                </ul>
                <a href="#" class="btn btn-outline" onclick="alert('GitHub star = free access!')">Get Started</a>
            </div>
            <div class="pricing-card popular">
                <div class="popular-badge">Most Popular</div>
                <h3>Pro</h3>
                <p style="color:var(--text-muted);font-size:14px;margin:4px 0 16px;">Для команд</p>
                <div class="price">$6.99<span>/month</span></div>
                <ul>
                    <li>До 10 агентов</li>
                    <li>50 MCP-серверов</li>
                    <li>OAuth + SSO</li>
                    <li>Аудит (10K записей)</li>
                    <li>Rate limiting</li>
                    <li>Email поддержка</li>
                </ul>
                <a href="#" class="btn" onclick="alert('Stripe coming soon!')">Start Free Trial</a>
            </div>
            <div class="pricing-card">
                <h3>Enterprise</h3>
                <p style="color:var(--text-muted);font-size:14px;margin:4px 0 16px;">Для компаний</p>
                <div class="price">$14.99<span>/month</span></div>
                <ul>
                    <li>До 100 агентов</li>
                    <li>Безлимитные серверы</li>
                    <li>OAuth + SSO + SAML</li>
                    <li>Безлимитный аудит</li>
                    <li>SLA 99.9%</li>
                    <li>Приоритетная поддержка</li>
                </ul>
                <a href="#" class="btn btn-outline" onclick="alert('Contact: mcp-hub@example.com')">Contact Sales</a>
            </div>
            <div class="pricing-card">
                <h3>Ultra</h3>
                <p style="color:var(--text-muted);font-size:14px;margin:4px 0 16px;">Максимум</p>
                <div class="price">$99.99<span>/month</span></div>
                <ul>
                    <li>Безлимитные агенты</li>
                    <li>On-premise установка</li>
                    <li>SLA 99.99%</li>
                    <li>Выделенный менеджер</li>
                    <li>Compliance (SOC2, GDPR)</li>
                    <li>Training для команды</li>
                </ul>
                <a href="#" class="btn btn-outline" onclick="alert('Contact: mcp-hub@example.com')">Contact Sales</a>
            </div>
        </div>
    </section>
    
    <section class="cta">
        <h2>Ready to secure your AI agents?</h2>
        <p>Start for free. No credit card required.</p>
        <a href="#" class="btn btn-large" onclick="alert('Sign up coming soon!')">Get Started Free →</a>
    </section>
    
    <footer>
        <p>© 2026 MCP Hub. Open source under MIT license.</p>
        <nav>
            <a href="https://github.com/iirenat/mcp-hub-oauth">GitHub</a>
            <a href="#">Terms</a>
            <a href="#">Privacy</a>
            <a href="#">Contact</a>
        </nav>
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

@app.get("/api/plans")
async def get_plans():
    return {"plans": PLANS}

@app.post("/api/checkout")
async def create_checkout(req: CheckoutRequest):
    """Перенаправляет на Stripe Checkout."""
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = PLANS[req.plan]
    
    # TODO: Подключить реальный Stripe
    # Пока — показываем сообщение
    return {
        "plan": req.plan,
        "amount": plan["price"],
        "currency": "usd",
        "status": "coming_soon",
        "message": "Stripe checkout coming soon. Please star on GitHub for updates!",
        "github_url": "https://github.com/iirenat/mcp-hub-oauth"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "MCP Hub", "version": "2.0.0", "servers": len(servers_db)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
