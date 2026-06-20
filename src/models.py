"""
MCP Hub — Database models and registration.
"""
import hashlib
import secrets
import os
from datetime import datetime
from typing import Optional, Dict, List

# В реальности — PostgreSQL через SQLAlchemy
# Пока — файловое хранилище для демо

DATA_DIR = os.path.expanduser("~/mcp_hub_data")
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
SUBS_FILE = os.path.join(DATA_DIR, "subscriptions.json")

def _load_json(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def _save_json(filepath: str, data: dict):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class User:
    def __init__(self, email: str, password: str, plan: str = "free"):
        self.id = hashlib.md5(email.encode()).hexdigest()[:12]
        self.email = email
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
        self.plan = plan
        self.created_at = datetime.now().isoformat()
        self.is_active = True
        self.api_key = secrets.token_hex(32)
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "plan": self.plan,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "api_key": self.api_key
        }
    
    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class RegistrationService:
    def register(self, email: str, password: str) -> dict:
        """Регистрирует нового пользователя."""
        users = _load_json(USERS_FILE)
        
        # Проверяем что email не занят
        for uid, u in users.items():
            if u["email"] == email:
                raise ValueError("Email already registered")
        
        user = User(email, password)
        users[user.id] = user.to_dict()
        _save_json(USERS_FILE, users)
        
        # Создаём бесплатную подписку
        subs = _load_json(SUBS_FILE)
        subs[user.id] = {
            "user_id": user.id,
            "plan": "free",
            "status": "active",
            "started_at": datetime.now().isoformat(),
            "expires_at": None  # Бесплатный — не истекает
        }
        _save_json(SUBS_FILE, subs)
        
        return user.to_dict()
    
    def login(self, email: str, password: str) -> Optional[dict]:
        """Авторизует пользователя."""
        users = _load_json(USERS_FILE)
        
        for uid, u in users.items():
            if u["email"] == email:
                user_obj = User(u["email"], "dummy")
                user_obj.password_hash = u.get("password_hash", "")
                # Проверяем пароль напрямую
                if hashlib.sha256(password.encode()).hexdigest() == u.get("password_hash", ""):
                    return u
                raise ValueError("Invalid password")
        
        raise ValueError("User not found")
    
    def get_user(self, user_id: str) -> Optional[dict]:
        users = _load_json(USERS_FILE)
        return users.get(user_id)
    
    def get_sub(self, user_id: str) -> Optional[dict]:
        subs = _load_json(SUBS_FILE)
        return subs.get(user_id)
    
    def upgrade_plan(self, user_id: str, new_plan: str) -> dict:
        """Обновляет тариф пользователя."""
        subs = _load_json(SUBS_FILE)
        if user_id not in subs:
            raise ValueError("Subscription not found")
        
        subs[user_id]["plan"] = new_plan
        subs[user_id]["status"] = "active"
        subs[user_id]["upgraded_at"] = datetime.now().isoformat()
        _save_json(SUBS_FILE, subs)
        
        return subs[user_id]
    
    def get_stats(self) -> dict:
        users = _load_json(USERS_FILE)
        subs = _load_json(SUBS_FILE)
        
        by_plan = {}
        for sid, sub in subs.items():
            plan = sub["plan"]
            by_plan[plan] = by_plan.get(plan, 0) + 1
        
        return {
            "total_users": len(users),
            "active_users": sum(1 for u in users.values() if u.get("is_active")),
            "by_plan": by_plan
        }
