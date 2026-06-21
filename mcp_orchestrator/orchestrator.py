#!/usr/bin/env python3
"""
Multi-Agent Orchestrator
Запускает параллельных суб-агентов через Hermes delegate_task
и координирует их работу.
"""
import subprocess
import json
import sys
import os
import time
from datetime import datetime
from typing import Optional

AGENTS_DIR = os.path.expanduser("~/hermes_agents")
LOG_DIR = os.path.expanduser("~/hermes_agents/logs")
os.makedirs(AGENTS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(f"{LOG_DIR}/orchestrator.log", "a") as f:
        f.write(line + "\n")

def run_agent(agent_id: str, task: str, model: str = "default") -> dict:
    """Запускает суб-агента через hermes CLI"""
    log(f"Starting agent {agent_id} with model {model}")
    
    # Создаём файл задачи
    task_file = f"{AGENTS_DIR}/{agent_id}.task.json"
    with open(task_file, "w") as f:
        json.dump({
            "id": agent_id,
            "task": task,
            "model": model,
            "started_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    # Запускаем через hermes
    result = subprocess.run(
        ["hermes", "chat", "-Q", "--model", model, task],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    output = result.stdout.strip()
    
    # Парсим ответ (убираем UI элементы)
    lines = output.split("\n")
    clean_lines = []
    for line in lines:
        if line.startswith("[") or line.startswith("═") or line.startswith("─"):
            continue
        if "tool call" in line.lower() or "tool result" in line.lower():
            continue
        clean_lines.append(line)
    
    clean_output = "\n".join(clean_lines).strip()
    
    # Сохраняем результат
    result_file = f"{AGENTS_DIR}/{agent_id}.result.json"
    with open(result_file, "w") as f:
        json.dump({
            "id": agent_id,
            "task": task,
            "output": clean_output,
            "completed_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    log(f"Agent {agent_id} completed")
    return {"id": agent_id, "output": clean_output}

def auto_route(task: str) -> str:
    """Автоматический выбор модели по типу задачи"""
    task_lower = task.lower()
    
    # Определяем тип задачи
    if any(w in task_lower for w in ["код", "code", "функци", "рефактор", "bug", "ошибк", "python", "javascript", "typescript"]):
        model = "deepseek/deepseek-v4-pro"
        agent_type = "coder"
    elif any(w in task_lower for w in ["поиск", "найти", "актуальн", "новост", "search"]):
        model = "google/gemini-2.5-flash"
        agent_type = "researcher"
    elif any(w in task_lower for w in ["анализ", "объясни", "сравни"]):
        model = "anthropic/claude-sonnet-4"
        agent_type = "analyzer"
    elif any(w in task_lower for w in ["текст", "стих", "поэзия", "creative", "пиши", "напиши"]):
        model = "anthropic/claude-sonnet-4"
        agent_type = "writer"
    else:
        model = "deepseek/deepseek-v4-pro"
        agent_type = "general"
    
    log(f"auto_route: task type = {agent_type}, model = {model}")
    result = run_agent(f"agent_{agent_type}_{int(time.time())}", task, model)
    return result["output"]

def ask_claude(task: str) -> str:
    """Задать вопрос Claude"""
    result = run_agent("claude_agent", task, "anthropic/claude-sonnet-4")
    return result["output"]

def ask_gemini(task: str) -> str:
    """Задать вопрос Gemini"""
    result = run_agent("gemini_agent", task, "google/gemini-2.5-flash")
    return result["output"]

def ask_deepseek(task: str) -> str:
    """Задать вопрос DeepSeek"""
    result = run_agent("deepseek_agent", task, "deepseek/deepseek-v4-pro")
    return result["output"]

def ask_both(task: str) -> str:
    """Сравнить ответы от Claude и DeepSeek"""
    r1 = ask_claude(task)
    r2 = ask_deepseek(task)
    return f"=== Claude ===\n{r1}\n\n=== DeepSeek ===\n{r2}"

def list_agents() -> list:
    """Список всех запущенных агентов"""
    agents = []
    for f in os.listdir(AGENTS_DIR):
        if f.endswith(".result.json"):
            with open(f"{AGENTS_DIR}/{f}") as fp:
                agents.append(json.load(fp))
    return agents

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <tool> [args]")
        print("Tools: auto_route, ask_claude, ask_gemini, ask_deepseek, ask_both, list_agents")
        sys.exit(1)
    
    tool = sys.argv[1]
    
    if tool == "auto_route":
        task = " ".join(sys.argv[2:])
        print(auto_route(task))
    elif tool == "ask_claude":
        task = " ".join(sys.argv[2:])
        print(ask_claude(task))
    elif tool == "ask_gemini":
        task = " ".join(sys.argv[2:])
        print(ask_gemini(task))
    elif tool == "ask_deepseek":
        task = " ".join(sys.argv[2:])
        print(ask_deepseek(task))
    elif tool == "ask_both":
        task = " ".join(sys.argv[2:])
        print(ask_both(task))
    elif tool == "list_agents":
        agents = list_agents()
        for a in agents:
            print(f"{a['id']}: {a['completed_at']}")
    else:
        print(f"Unknown tool: {tool}")
