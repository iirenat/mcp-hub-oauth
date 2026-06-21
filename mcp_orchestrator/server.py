#!/usr/bin/env python3
"""Multi-Agent MCP Orchestrator — работает через OpenRouter"""
import os
import json
import sys
import urllib.request
import urllib.error

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_model(model: str, prompt: str) -> str:
    """Вызывает модель через OpenRouter"""
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048
    }).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"

def ask_claude(prompt: str) -> str:
    """Claude через OpenRouter (бесплатная модель)"""
    return call_model("anthropic/claude-sonnet-4:free", prompt)

def ask_gemini(prompt: str) -> str:
    """Gemini через OpenRouter (бесплатная модель)"""
    return call_model("google/gemma-4-31b-it:free", prompt)

def ask_deepseek(prompt: str) -> str:
    """DeepSeek через OpenRouter (бесплатная)"""
    return call_model("deepseek/deepseek-r1:free", prompt)

def auto_route(task: str) -> str:
    """Автоматический выбор модели по типу задачи"""
    task_lower = task.lower()
    if any(w in task_lower for w in ["код", "code", "функци", "рефактор", "bug", "ошибк"]):
        return ask_deepseek(task)
    elif any(w in task_lower for w in ["поиск", "найти", "актуальн", "новост", "search"]):
        return ask_gemini(task)
    elif any(w in task_lower for w in ["анализ", "объясни", "сравни", "текст", "стих", "поэзия", "creative"]):
        return ask_claude(task)
    else:
        return ask_deepseek(task)

def ask_both(task: str) -> str:
    """Обе модели — для сравнения"""
    r1 = ask_claude(task)
    r2 = ask_deepseek(task)
    return f"=== Claude ===\n{r1}\n\n=== DeepSeek ===\n{r2}"

# === MCP Server (stdio) ===
def handle_request(req: dict) -> dict:
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "multi-agent-orchestrator", "version": "1.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "ask_claude",
                        "description": "Анализ, код, рассуждения, длинный текст, творчество",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}
                    },
                    {
                        "name": "ask_gemini",
                        "description": "Поиск, актуальные данные, Google-интеграции",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}
                    },
                    {
                        "name": "ask_deepseek",
                        "description": "Кодинг, логика, технические задачи",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}
                    },
                    {
                        "name": "ask_both",
                        "description": "Обе модели — для сравнения ответов",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}
                    },
                    {
                        "name": "auto_route",
                        "description": "Автовыбор агента по типу задачи",
                        "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}
                    }
                ]
            }
        }

    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})

        if name == "ask_claude":
            result = ask_claude(args.get("prompt", ""))
        elif name == "ask_gemini":
            result = ask_gemini(args.get("prompt", ""))
        elif name == "ask_deepseek":
            result = ask_deepseek(args.get("prompt", ""))
        elif name == "ask_both":
            result = ask_both(args.get("prompt", ""))
        elif name == "auto_route":
            result = auto_route(args.get("task", ""))
        else:
            result = f"Unknown tool: {name}"

        return {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {"content": [{"type": "text", "text": result}]}
        }

    return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "Method not found"}}

def main():
    """MCP stdio server loop"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            continue

if __name__ == "__main__":
    main()
