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
    data = server.dict()
    data["id"] = server_id
    data["created_at"] = datetime.now().isoformat()
    servers_db[server_id] = data
    audit_db.append({"action": "server_added", "server_id": server_id, "timestamp": datetime.now().isoformat()})
    return data

@app.post("/api/auth/start")
async def start_auth(auth: AuthStart):
    state = secrets.token_hex(16)
    return {"auth_url": "#oauth?state=" + state, "state": state}

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
    return {"plan": req.plan, "amount": PLANS[req.plan]["price"], "status": "registered", "message": "Thanks! Payment integration coming soon."}

@app.get("/health")
async def health(): return {"status": "ok", "service": "MCP Hub", "version": "2.0.0", "servers": len(servers_db)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)