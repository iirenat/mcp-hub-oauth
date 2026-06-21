"""
MCP Hub - Database models with SQLite
"""
import sqlite3
import hashlib
import secrets
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "mcp_hub.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            name TEXT,
            avatar TEXT,
            provider TEXT DEFAULT 'local',
            provider_id TEXT,
            plan TEXT DEFAULT 'free',
            api_key TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS servers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            url TEXT,
            category TEXT DEFAULT 'general',
            tags TEXT DEFAULT '[]',
            requires_auth INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            message TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def create_user(email, password=None, name=None, provider='local', provider_id=None):
    conn = get_db()
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    api_key = secrets.token_hex(32)
    password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
    
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, name, provider, provider_id, api_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, email, password_hash, name, provider, provider_id, api_key)
        )
        conn.commit()
        return {"id": user_id, "email": email, "name": name, "plan": "free", "api_key": api_key}
    except sqlite3.IntegrityError:
        # User exists, update last login
        conn.execute("UPDATE users SET last_login = ? WHERE email = ?", (datetime.now().isoformat(), email))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row)
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def verify_password(email, password):
    user = get_user_by_email(email)
    if not user or not user.get('password_hash'):
        return False
    return user['password_hash'] == hashlib.sha256(password.encode()).hexdigest()

def create_session(user_id):
    token = secrets.token_hex(32)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, datetime('now', '+30 days'))",
        (token, user_id)
    )
    conn.commit()
    conn.close()
    return token

def get_session(token):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, u.email, u.name, u.plan, u.api_key FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ? AND s.expires_at > datetime('now')",
        (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(token):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

# Initialize on import
init_db()
