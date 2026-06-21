PLANS = {
    "free": {"name": "Free", "price": 0, "period": "month", "features": ["1 agent", "3 MCP servers", "Basic OAuth", "100 audit logs"]},
    "pro": {"name": "Pro", "price": 6.99, "period": "month", "features": ["Up to 10 agents", "50 MCP servers", "OAuth 2.0 + SSO", "Full audit (10K)", "Rate limiting", "Email support"], "popular": True},
    "enterprise": {"name": "Enterprise", "price": 14.99, "period": "month", "features": ["Up to 100 agents", "Unlimited MCP servers", "OAuth + SSO + SAML", "Unlimited audit", "SLA 99.9%", "Priority support"]}
}

DEFAULT_SERVERS = [
    {"name": "GitHub", "description": "GitHub API for AI agents", "url": "https://api.github.com/mcp", "category": "development", "tags": ["git", "code"], "requires_auth": True},
    {"name": "Slack", "description": "Slack integration for agents", "url": "https://slack.com/api/mcp", "category": "communication", "tags": ["chat"], "requires_auth": True},
    {"name": "Notion", "description": "Notion knowledge base", "url": "https://notion.so/api/mcp", "category": "productivity", "tags": ["notes"], "requires_auth": True},
    {"name": "PostgreSQL", "description": "PostgreSQL database", "url": "https://localhost/mcp", "category": "database", "tags": ["sql"], "requires_auth": True},
    {"name": "Pinecone", "description": "Vector search", "url": "https://api.pinecone.io/mcp", "category": "ai", "tags": ["vector"], "requires_auth": True},
    {"name": "Sentry", "description": "Error monitoring", "url": "https://sentry.io/api/mcp", "category": "monitoring", "tags": ["errors"], "requires_auth": True},
    {"name": "Stripe", "description": "Payments API", "url": "https://api.stripe.com/mcp", "category": "payments", "tags": ["billing"], "requires_auth": True},
    {"name": "S3", "description": "Object storage", "url": "https://s3.amazonaws.com/mcp", "category": "storage", "tags": ["files"], "requires_auth": True}
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