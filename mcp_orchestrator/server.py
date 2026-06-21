#!/usr/bin/env python3
"""
Multi-Agent MCP Orchestrator v2.0
- OpenRouter: Claude, Gemini, DeepSeek, Grok, Perplexity
- Память между сессиями (JSON файл)
- Работа с файлами VSCode проекта
"""
import os, json, sys, urllib.request, pathlib, datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL         = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            return json.loads(pathlib.Path(MEMORY_FILE).read_text(encoding="utf-8"))
        except:
            pass
    return {"facts": [], "history": []}

def save_memory(mem):
    pathlib.Path(MEMORY_FILE).write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")

def remember(fact):
    mem = load_memory()
    mem["facts"].append({"fact": fact, "time": datetime.datetime.now().isoformat()})
    save_memory(mem)
    return f"Запомнил: {fact}"

def recall():
    mem = load_memory()
    if not mem["facts"]:
        return "Память пуста."
    return "\n".join(f"- {f['fact']} ({f['time'][:10]})" for f in mem["facts"])

def forget_all():
    save_memory({"facts": [], "history": []})
    return "Память очищена."

def memory_context():
    mem = load_memory()
    if not mem["facts"]:
        return ""
    facts = "\n".join(f"- {f['fact']}" for f in mem["facts"][-20:])
    return f"\n\n[Контекст из памяти]:\n{facts}\n"

def call_openrouter(model, prompt):
    ctx = memory_context()
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": ctx + prompt}],
        "max_tokens": 2048
    }).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=data, headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[OpenRouter Error] {e}"

def call_gemini_direct(prompt):
    if not GEMINI_API_KEY:
        return call_openrouter("google/gemma-4-31b-it:free", prompt)
    ctx = memory_context()
    data = json.dumps({"contents": [{"parts": [{"text": ctx + prompt}]}]}).encode()
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"[Gemini Error] {e}"

def ask_claude(prompt):    return call_openrouter("nvidia/nemotron-3-nano-30b-a3b:free", prompt)
def ask_gemini(prompt):    return call_gemini_direct(prompt)
def ask_deepseek(prompt):  return call_openrouter("nvidia/nemotron-3-nano-30b-a3b:free", prompt)
def ask_grok(prompt):      return call_openrouter("x-ai/grok-4", prompt)
def ask_perplexity(prompt):return call_openrouter("perplexity/sonar", prompt)

def ask_both(prompt):
    r1 = ask_claude(prompt)
    r2 = ask_deepseek(prompt)
    return f"=== Claude ===\n{r1}\n\n=== DeepSeek ===\n{r2}"

def auto_route(task):
    t = task.lower()
    if any(w in t for w in ["поиск", "найди", "актуальн", "новост", "search", "latest"]):
        model_name, model = "Perplexity (поиск)", "perplexity/sonar"
    elif any(w in t for w in ["код", "code", "функци", "рефактор", "bug", "ошибк", "debug"]):
        model_name, model = "DeepSeek (код)", "nvidia/nemotron-3-nano-30b-a3b:free"
    elif any(w in t for w in ["анализ", "объясни", "сравни", "стих", "creative", "текст"]):
        model_name, model = "Claude (анализ)", "nvidia/nemotron-3-nano-30b-a3b:free"
    elif any(w in t for w in ["гугл", "google", "youtube", "gmail", "перевод"]):
        model_name, model = "Gemini (Google)", "google/gemma-4-31b-it:free"
    else:
        model_name, model = "Grok (общее)", "x-ai/grok-3-mini-beta"
    result = call_openrouter(model, task)
    mem = load_memory()
    mem["history"].append({"task": task[:100], "model": model_name, "time": datetime.datetime.now().isoformat()})
    mem["history"] = mem["history"][-50:]
    save_memory(mem)
    return f"[Агент: {model_name}]\n\n{result}"

def read_file(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"[Ошибка чтения] {e}"

def write_file(path, content):
    try:
        pathlib.Path(path).write_text(content, encoding="utf-8")
        return f"Файл сохранён: {path}"
    except Exception as e:
        return f"[Ошибка записи] {e}"

def list_project(folder):
    try:
        result = []
        for p in pathlib.Path(folder).rglob("*"):
            if p.is_file() and ".git" not in str(p) and "node_modules" not in str(p):
                result.append(str(p))
        return "\n".join(result[:100]) or "Папка пуста."
    except Exception as e:
        return f"[Ошибка] {e}"

def analyze_file(path):
    content = read_file(path)
    if content.startswith("[Ошибка"):
        return content
    prompt = f"Проанализируй этот файл и объясни что он делает:\n\n{content[:4000]}"
    return ask_claude(prompt)

def refactor_file(path, instruction):
    content = read_file(path)
    if content.startswith("[Ошибка"):
        return content
    prompt = f"Задача: {instruction}\n\nФайл ({path}):\n\n{content[:4000]}\n\nВерни только исправленный код без объяснений."
    return ask_deepseek(prompt)

TOOLS = [
    {"name": "ask_claude",     "description": "Claude — анализ, текст, творчество",           "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "ask_gemini",     "description": "Gemini — твоя подписка, Google-задачи",         "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "ask_deepseek",   "description": "DeepSeek — код, логика, технические задачи",    "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "ask_grok",       "description": "Grok (xAI) — общие задачи, юмор, нестандартно","inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "ask_perplexity", "description": "Perplexity — поиск в реальном времени",         "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "ask_both",       "description": "Claude + DeepSeek параллельно для сравнения",   "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "auto_route",     "description": "Автовыбор лучшего агента для задачи",           "inputSchema": {"type": "object", "properties": {"task":   {"type": "string"}}, "required": ["task"]}},
    {"name": "remember",       "description": "Запомнить факт между сессиями",                 "inputSchema": {"type": "object", "properties": {"fact":   {"type": "string"}}, "required": ["fact"]}},
    {"name": "recall",         "description": "Вспомнить всё что было запомнено",              "inputSchema": {"type": "object", "properties": {}}},
    {"name": "forget_all",     "description": "Очистить всю память",                           "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_file",      "description": "Прочитать файл проекта",                        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file",     "description": "Записать/сохранить файл",                       "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "list_project",   "description": "Показать все файлы в папке проекта",            "inputSchema": {"type": "object", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}},
    {"name": "analyze_file",   "description": "Проанализировать файл через Claude",            "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "refactor_file",  "description": "Отрефакторить файл через DeepSeek",             "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "instruction": {"type": "string"}}, "required": ["path", "instruction"]}},
]

def handle(req):
    method = req.get("method", "")
    params = req.get("params", {})
    rid    = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "multi-agent-orchestrator", "version": "2.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})
        dispatch = {
            "ask_claude":     lambda: ask_claude(args["prompt"]),
            "ask_gemini":     lambda: ask_gemini(args["prompt"]),
            "ask_deepseek":   lambda: ask_deepseek(args["prompt"]),
            "ask_grok":       lambda: ask_grok(args["prompt"]),
            "ask_perplexity": lambda: ask_perplexity(args["prompt"]),
            "ask_both":       lambda: ask_both(args["prompt"]),
            "auto_route":     lambda: auto_route(args["task"]),
            "remember":       lambda: remember(args["fact"]),
            "recall":         lambda: recall(),
            "forget_all":     lambda: forget_all(),
            "read_file":      lambda: read_file(args["path"]),
            "write_file":     lambda: write_file(args["path"], args["content"]),
            "list_project":   lambda: list_project(args["folder"]),
            "analyze_file":   lambda: analyze_file(args["path"]),
            "refactor_file":  lambda: refactor_file(args["path"], args["instruction"]),
        }
        fn = dispatch.get(name)
        result = fn() if fn else f"Unknown tool: {name}"
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": result}]}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req  = json.loads(line)
            resp = handle(req)
            print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            continue

if __name__ == "__main__":
    main()
