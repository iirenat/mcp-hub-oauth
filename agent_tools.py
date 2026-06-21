#!/usr/bin/env python3
"""
Agent Tools — набор инструментов для оркестрации
Используй эти функции для делегирования задач разным моделям
"""
import json, urllib.request, os, datetime, pathlib

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")

def call_model(model, prompt, max_tokens=2048):
    """Вызов модели через OpenRouter"""
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=data, headers={
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        return "[Error] " + str(e)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try: return json.loads(pathlib.Path(MEMORY_FILE).read_text(encoding="utf-8"))
        except: pass
    return {"facts": [], "history": []}

def save_memory(mem):
    pathlib.Path(MEMORY_FILE).write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")

def remember(fact):
    mem = load_memory()
    mem["facts"].append({"fact": fact, "time": datetime.datetime.now().isoformat()})
    save_memory(mem)
    return "Запомнил: " + fact

def recall():
    mem = load_memory()
    if not mem["facts"]: return "Память пуста."
    return "\n".join("- " + f["fact"] for f in mem["facts"])

def auto_route(task):
    t = task.lower()
    if any(w in t for w in ["поиск", "найди", "актуальн", "новост", "search", "latest"]):
        model, name = "perplexity/sonar", "Perplexity"
    elif any(w in t for w in ["код", "code", "функци", "рефактор", "bug", "ошибк", "debug"]):
        model, name = "nvidia/nemotron-3-nano-30b-a3b:free", "DeepSeek"
    elif any(w in t for w in ["анализ", "объясни", "сравни", "стих", "creative", "текст"]):
        model, name = "nvidia/nemotron-3-nano-30b-a3b:free", "Claude"
    elif any(w in t for w in ["гугл", "google", "youtube", "gmail", "перевод"]):
        model, name = "google/gemma-4-31b-it:free", "Gemini"
    else:
        model, name = "x-ai/grok-3-mini-beta", "Grok"
    result = call_model(model, task)
    return "[" + name + "]\n\n" + result

def ask_claude(prompt):  return call_model("nvidia/nemotron-3-nano-30b-a3b:free", prompt)
def ask_deepseek(prompt): return call_model("nvidia/nemotron-3-nano-30b-a3b:free", prompt)
def ask_gemini(prompt):  return call_model("google/gemma-4-31b-it:free", prompt)
def ask_grok(prompt):    return call_model("x-ai/grok-3-mini-beta", prompt)
def ask_perplexity(prompt): return call_model("perplexity/sonar", prompt)

def ask_both(prompt):
    r1 = ask_claude(prompt)
    r2 = ask_deepseek(prompt)
    return "=== Claude ===\n" + r1 + "\n\n=== DeepSeek ===\n" + r2

def read_file(path):
    try: return pathlib.Path(path).read_text(encoding="utf-8")
    except Exception as e: return "[Ошибка] " + str(e)

def write_file(path, content):
    try: pathlib.Path(path).write_text(content, encoding="utf-8"); return "OK: " + path
    except Exception as e: return "[Ошибка] " + str(e)

def list_project(folder):
    try:
        files = [str(p) for p in pathlib.Path(folder).rglob("*") if p.is_file() and ".git" not in str(p)]
        return "\n".join(files[:100])
    except Exception as e: return "[Ошибка] " + str(e)

def analyze_file(path):
    content = read_file(path)
    if content.startswith("[Ошибка"): return content
    return ask_claude("Проанализируй этот файл:\n\n" + content[:4000])

def refactor_file(path, instruction):
    content = read_file(path)
    if content.startswith("[Ошибка"): return content
    return ask_deepseek("Задача: " + instruction + "\n\nФайл:\n" + content[:4000] + "\n\nВерни только исправленный код.")
