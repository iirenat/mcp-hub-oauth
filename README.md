# MCP Hub with OAuth

**Enterprise-безопасность для AI-агентов**

## Что это?

Центральная панель для управления всеми AI-агентами в компании.

## Проблема

Компании используют 10-50 AI-агентов. У каждого свои API-ключи, токены, права доступа. Нет единого места для управления.

## Решение

MCP Hub — одна панель для всех AI-агентов:
- Каталог MCP-серверов
- OAuth 2.0 авторизация
- Права доступа (RBAC)
- Аудит всех запросов
- Rate limiting
- Мониторинг

## Quick Start

```bash
pip install -r requirements.txt
python src/api.py
```

## API

- `GET /` — Дашборд
- `GET /api/servers` — Список MCP-серверов
- `POST /api/auth/start` — OAuth авторизация
- `GET /api/audit` — Лог аудита
- `GET /api/stats` — Статистика

## Стек

- Python + FastAPI
- PostgreSQL (в продакшне)
- Redis (кэш)
- Docker

## Лицензия

MIT
