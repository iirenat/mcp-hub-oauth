# MCP Hub with OAuth — Production Ready

## Структура проекта

```
mcp-hub-oauth/
├── src/
│   ├── mcp_hub.py          # Основной код
│   ├── api.py              # FastAPI endpoints
│   ├── auth.py             # OAuth 2.0
│   ├── models.py           # Модели данных
│   └── config.py           # Конфигурация
├── tests/
│   └── test_hub.py         # Тесты
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Быстрый старт

```bash
# Установка
pip install -r requirements.txt

# Запуск
python src/api.py

# Тесты
pytest tests/
```

## API Endpoints

- `GET /` — Дашборд
- `GET /api/servers` — Список MCP-серверов
- `GET /api/servers/{id}` — Информация о сервере
- `POST /api/servers` — Добавить сервер
- `POST /api/auth/start` — Начать OAuth авторизацию
- `POST /api/auth/callback` — Завершить OAuth
- `GET /api/tokens` — Список токенов
- `GET /api/audit` — Лог аудита
- `GET /api/stats` — Статистика

## Деплой на Railway

```bash
railway init
railway up
```

## Деплой на Render

1. Подключить GitHub репозиторий
2. Выбрать Docker
3. Deploy
"""
