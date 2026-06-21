"""
MCP Hub — Full Feature API (No payment required)
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
    name: str
    description: str
    url: str
    category: str = "general"
    tags: List[str] = []
    requires_auth: bool = False

class AuthStart(BaseModel):
    server_id: str
    user_id: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ContactRequest(BaseModel):
    name: str
    email: str
    message: str

class CheckoutRequest(BaseModel):
    plan: str
    email: str