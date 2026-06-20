"""MCP Hub — FastAPI API Server."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# === Хранилище (в реальности — PostgreSQL) ===
servers_db = {}
tokens_db = {}
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

class AuthCallback(BaseModel):
    state: str
    code: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 3600

# === Endpoints ===

@app.get("/")
async def dashboard():
    return {"status": "ok", "service": "MCP Hub", "version": "1.0.0"}

@app.get("/api/servers")
async def list_servers(category: str = None, search: str = None):
    servers = list(servers_db.values())
    if category:
        servers = [s for s in servers if s["category"] == category]
    if search:
        search_lower = search.lower()
        servers = [s for s in servers if search_lower in s["name"].lower()]
    return {"servers": servers, "total": len(servers)}

@app.post("/api/servers")
async def add_server(server: ServerCreate):
    server_id = hashlib.md5(server.name.encode()).hexdigest()[:12]
    data = server.dict()
    data["id"] = server_id
    data["created_at"] = datetime.now().isoformat()
    data["rating"] = 0.0
    servers_db[server_id] = data
    audit_db.append({"action": "server_added", "server_id": server_id, "timestamp": datetime.now().isoformat()})
    return data

@app.post("/api/auth/start")
async def start_auth(auth: AuthStart):
    state = secrets.token_hex(16)
    return {
        "auth_url": f"http://localhost:8000/oauth/callback?state={state}",
        "state": state
    }

@app.post("/api/auth/callback")
async def complete_auth(cb: AuthCallback):
    token_key = f"{cb.state}:{cb.access_token[:16]}"
    tokens_db[token_key] = {
        "access_token": cb.access_token[:10] + "...",
        "created_at": datetime.now().isoformat(),
        "expires_in": cb.expires_in,
        "is_active": True
    }
    audit_db.append({"action": "auth_completed", "state": cb.state, "timestamp": datetime.now().isoformat()})
    return {"status": "ok", "token": tokens_db[token_key]}

@app.get("/api/tokens")
async def list_tokens():
    return {"tokens": list(tokens_db.values())}

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
