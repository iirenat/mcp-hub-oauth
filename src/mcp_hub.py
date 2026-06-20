"""
MCP Hub with OAuth — Enterprise-безопасность для AI-агентов.

Что делает:
- Каталог MCP-серверов с поиском и фильтрацией
- OAuth 2.0 авторизация для подключения к серверам
- Управление токенами и правами доступа
- Логирование всех запросов (аудит)
- Ограничение  rate limiting
- Дашборд для мониторинга

Стек: Python + FastAPI + React + PostgreSQL
"""
import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# === Конфигурация ===

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mcp_hub.db")
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
    OAUTH_CALLBACK_URL = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:8000/oauth/callback")
    TOKEN_EXPIRY_HOURS = int(os.getenv("TOKEN_EXPIRY_HOURS", "24"))
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@localhost")


# === Модели данных ===

class MCPServer:
    """MCP-сервер в каталоге."""
    def __init__(self, name: str, description: str, url: str, 
                 category: str = "general", tags: List[str] = None,
                 oauth_provider: str = None, requires_auth: bool = False):
        self.id = hashlib.md5(name.encode()).hexdigest()[:12]
        self.name = name
        self.description = description
        self.url = url
        self.category = category
        self.tags = tags or []
        self.oauth_provider = oauth_provider
        self.requires_auth = requires_auth
        self.created_at = datetime.now().isoformat()
        self.rating = 0.0
        self.usage_count = 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'url': self.url,
            'category': self.category,
            'tags': self.tags,
            'oauth_provider': self.oauth_provider,
            'requires_auth': self.requires_auth,
            'created_at': self.created_at,
            'rating': self.rating,
            'usage_count': self.usage_count
        }


class OAuthToken:
    """OAuth токен для доступа к MCP-серверу."""
    def __init__(self, server_id: str, user_id: str, 
                 access_token: str, refresh_token: str = None,
                 expires_in: int = 3600):
        self.server_id = server_id
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=expires_in)
        self.is_active = True
    
    @property
    def is_expired(self):
        return datetime.now() > self.expires_at
    
    def to_dict(self):
        return {
            'server_id': self.server_id,
            'user_id': self.user_id,
            'access_token': self.access_token[:10] + '...',  # Не показываем полный токен
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_active': self.is_active,
            'is_expired': self.is_expired
        }


class AuditLog:
    """Лог запросов для аудита."""
    def __init__(self, server_id: str, user_id: str, 
                 action: str, details: str = ""):
        self.timestamp = datetime.now()
        self.server_id = server_id
        self.user_id = user_id
        self.action = action
        self.details = details
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'server_id': self.server_id,
            'user_id': self.user_id,
            'action': self.action,
            'details': self.details
        }


# === Каталог MCP-серверов ===

class MCPCatalog:
    """Каталог MCP-серверов с поиском и фильтрацией."""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self._load_defaults()
    
    def _load_defaults(self):
        """Загружает известные MCP-серверы."""
        defaults = [
            MCPServer("GitHub", "GitHub API для AI-агентов", 
                     "https://api.github.com/mcp", "development",
                     ["git", "code", "collaboration"], "github", True),
            MCPServer("Slack", "Slack интеграция для агентов",
                     "https://slack.com/api/mcp", "communication",
                     ["chat", "messaging"], "slack", True),
            MCPServer("Notion", "Notion база знаний для агентов",
                     "https://notion.so/api/mcp", "productivity",
                     ["notes", "database"], "notion", True),
            MCPServer("PostgreSQL", "PostgreSQL база данных",
                     "https://localhost:5432/mcp", "database",
                     ["sql", "data"], requires_auth=True),
            MCPServer("Pinecone", "Векторный поиск",
                     "https://api.pinecone.io/mcp", "ai",
                     ["vector", "search", "embeddings"], requires_auth=True),
            MCPServer("Sentry", "Мониторинг ошибок",
                     "https://sentry.io/api/mcp", "monitoring",
                     ["errors", "tracking"], "sentry", True),
            MCPServer("Stripe", "Платежи через API",
                     "https://api.stripe.com/mcp", "payments",
                     ["billing", "finance"], "stripe", True),
            MCPServer("S3", "Объектное хранилище",
                     "https://s3.amazonaws.com/mcp", "storage",
                     ["files", "backup"], requires_auth=True),
        ]
        for s in defaults:
            self.servers[s.id] = s
    
    def search(self, query: str = "", category: str = None, 
               tags: List[str] = None, requires_auth: bool = None) -> List[MCPServer]:
        """Поиск серверов с фильтрацией."""
        results = list(self.servers.values())
        
        if query:
            query_lower = query.lower()
            results = [s for s in results 
                      if query_lower in s.name.lower() 
                      or query_lower in s.description.lower()]
        
        if category:
            results = [s for s in results if s.category == category]
        
        if tags:
            results = [s for s in results if any(t in s.tags for t in tags)]
        
        if requires_auth is not None:
            results = [s for s in results if s.requires_auth == requires_auth]
        
        return sorted(results, key=lambda s: s.rating, reverse=True)
    
    def get(self, server_id: str) -> Optional[MCPServer]:
        return self.servers.get(server_id)
    
    def add(self, server: MCPServer):
        self.servers[server.id] = server
    
    def get_categories(self) -> List[str]:
        return list(set(s.category for s in self.servers.values()))
    
    def get_stats(self):
        total = len(self.servers)
        auth_required = sum(1 for s in self.servers.values() if s.requires_auth)
        by_category = {}
        for s in self.servers.values():
            by_category[s.category] = by_category.get(s.category, 0) + 1
        return {
            'total_servers': total,
            'auth_required': auth_required,
            'by_category': by_category
        }


# === OAuth менеджер ===

class OAuthManager:
    """Управление OAuth токенами и авторизацией."""
    
    def __init__(self):
        self.tokens: Dict[str, OAuthToken] = {}
        self.pending_authorizations: Dict[str, dict] = {}
    
    def start_auth(self, server_id: str, user_id: str, 
                   redirect_uri: str = None) -> str:
        """Начинает процесс OAuth авторизации. Возвращает URL для редиректа."""
        state = secrets.token_hex(16)
        self.pending_authorizations[state] = {
            'server_id': server_id,
            'user_id': user_id,
            'redirect_uri': redirect_uri or Config.OAUTH_CALLBACK_URL,
            'created_at': datetime.now().isoformat()
        }
        # В реальности здесь был бы URL провайдера OAuth
        return f"https://oauth.provider.com/authorize?state={state}&response_type=code"
    
    def complete_auth(self, state: str, code: str, 
                      access_token: str, refresh_token: str = None,
                      expires_in: int = 3600) -> OAuthToken:
        """Завершает OAuth авторизацию, сохраняет токен."""
        pending = self.pending_authorizations.pop(state, None)
        if not pending:
            raise ValueError("Invalid or expired state")
        
        token = OAuthToken(
            server_id=pending['server_id'],
            user_id=pending['user_id'],
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
        
        key = f"{token.server_id}:{token.user_id}"
        self.tokens[key] = token
        return token
    
    def get_token(self, server_id: str, user_id: str) -> Optional[OAuthToken]:
        """Получает активный токен."""
        key = f"{server_id}:{user_id}"
        token = self.tokens.get(key)
        if token and token.is_active and not token.is_expired:
            return token
        return None
    
    def refresh_token(self, server_id: str, user_id: str, 
                      new_access_token: str, 
                      new_refresh_token: str = None,
                      expires_in: int = 3600) -> OAuthToken:
        """Обновляет токен."""
        key = f"{server_id}:{user_id}"
        old_token = self.tokens.get(key)
        if not old_token:
            raise ValueError("Token not found")
        
        return self.complete_auth(
            state=secrets.token_hex(16),
            code="refresh",
            access_token=new_access_token,
            refresh_token=new_refresh_token or old_token.refresh_token,
            expires_in=expires_in
        )
    
    def revoke_token(self, server_id: str, user_id: str):
        """Отзывает токен."""
        key = f"{server_id}:{user_id}"
        if key in self.tokens:
            self.tokens[key].is_active = False
    
    def get_user_tokens(self, user_id: str) -> List[dict]:
        """Все токены пользователя."""
        result = []
        for key, token in self.tokens.items():
            if token.user_id == user_id and token.is_active:
                result.append(token.to_dict())
        return result


# === Аудит ===

class AuditManager:
    """Логирование и аудит запросов."""
    
    def __init__(self, max_logs: int = 10000):
        self.logs: List[AuditLog] = []
        self.max_logs = max_logs
    
    def log(self, server_id: str, user_id: str, 
            action: str, details: str = ""):
        log_entry = AuditLog(server_id, user_id, action, details)
        self.logs.append(log_entry)
        # Ограничиваем размер логов
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
    def get_logs(self, server_id: str = None, user_id: str = None,
                 limit: int = 100) -> List[dict]:
        results = self.logs
        if server_id:
            results = [l for l in results if l.server_id == server_id]
        if user_id:
            results = [l for l in results if l.user_id == user_id]
        return [l.to_dict() for l in results[-limit:]]
    
    def get_stats(self):
        actions = {}
        for log_entry in self.logs:
            actions[log_entry.action] = actions.get(log_entry.action, 0) + 1
        return {
            'total_logs': len(self.logs),
            'actions': actions
        }


# === Rate Limiter ===

class RateLimiter:
    """Ограничение частоты запросов."""
    
    def __init__(self, limit_per_minute: int = 60):
        self.limit = limit_per_minute
        self.requests: Dict[str, List[datetime]] = {}
    
    def check(self, user_id: str, server_id: str) -> bool:
        """Проверяет не превышен ли лимит."""
        key = f"{user_id}:{server_id}"
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Очищаем старые запросы
        self.requests[key] = [t for t in self.requests[key] if t > minute_ago]
        
        if len(self.requests[key]) >= self.limit:
            return False  # Лимит превышен
        
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, user_id: str, server_id: str) -> int:
        key = f"{user_id}:{server_id}"
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        if key not in self.requests:
            return self.limit
        
        recent = len([t for t in self.requests[key] if t > minute_ago])
        return max(0, self.limit - recent)


# === Главный класс ===

class MCPHub:
    """Главный класс MCP Hub."""
    
    def __init__(self):
        self.catalog = MCPCatalog()
        self.oauth = OAuthManager()
        self.audit = AuditManager()
        self.rate_limiter = RateLimiter(Config.RATE_LIMIT_PER_MINUTE)
    
    def get_dashboard(self) -> dict:
        """Данные для дашборда."""
        return {
            'stats': self.catalog.get_stats(),
            'audit': self.audit.get_stats(),
            'active_tokens': len([t for t in self.oauth.tokens.values() if t.is_active]),
            'categories': self.catalog.get_categories(),
            'recent_servers': [s.to_dict() for s in list(self.catalog.servers.values())[:5]]
        }
    
    def health(self) -> dict:
        return {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'version': '0.1.0',
            'servers': len(self.catalog.servers)
        }


# === Тесты ===

if __name__ == "__main__":
    hub = MCPHub()
    
    print("=== MCP Hub with OAuth ===\n")
    
    # Статистика
    print("📊 Статистика:")
    stats = hub.catalog.get_stats()
    print(f"   Серверов: {stats['total_servers']}")
    print(f"   С авторизацией: {stats['auth_required']}")
    print(f"   По категориям: {stats['by_category']}")
    
    # Поиск
    print("\n🔍 Поиск 'data':")
    results = hub.catalog.search("data")
    for s in results:
        print(f"   - {s.name}: {s.description}")
    
    # OAuth
    print("\n🔐 OAuth:")
    auth_url = hub.oauth.start_auth("test-server", "user-1")
    print(f"   Auth URL: {auth_url[:60]}...")
    
    # Токен
    token = hub.oauth.complete_auth(
        state=list(hub.oauth.pending_authorizations.keys())[0] if hub.oauth.pending_authorizations else "test",
        code="test-code",
        access_token="tok_" + secrets.token_hex(32),
        expires_in=3600
    )
    print(f"   Токен: {token.to_dict()['access_token']}")
    
    # Аудит
    print("\n📝 Аудит:")
    hub.audit.log("server-1", "user-1", "connect", "Подключение к серверу")
    hub.audit.log("server-1", "user-1", "request", "GET /tools")
    print(f"   Логов: {hub.audit.get_stats()}")
    
    # Rate limit
    print("\n⏱️ Rate Limit:")
    for i in range(5):
        allowed = hub.rate_limiter.check("user-1", "server-1")
        remaining = hub.rate_limiter.get_remaining("user-1", "server-1")
        print(f"   Запрос {i+1}: {'✅' if allowed else '❌'} (осталось: {remaining})")
    
    print("\n✅ MCP Hub готов к работе!")
