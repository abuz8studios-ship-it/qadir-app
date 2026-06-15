"""
QADIR — Main Application Backend
The brain of the operation. FastAPI server that handles everything.
"""

import os
import json
import time
import yaml
import sqlite3
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
LOGS_DIR = BASE_DIR / "logs"

for d in [CONFIG_DIR, DATA_DIR, LOGS_DIR]:
    d.mkdir(exist_ok=True)


# ─── Models ───────────────────────────────────────────────

class ChatMessage(BaseModel):
    content: str
    soul: str = "qadir"
    task_type: str = "general"

class APIKeyUpdate(BaseModel):
    provider: str
    api_key: str

class SoulCreate(BaseModel):
    name: str
    role: str
    tone: str = "direct"
    preferred_brain: str = "anthropic/sonnet"


# ─── Database ─────────────────────────────────────────────

class Database:
    def __init__(self, db_path: str = str(DATA_DIR / "qadir.db")):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soul TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                brain_used TEXT,
                tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                provider TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                task_type TEXT DEFAULT 'general',
                status TEXT DEFAULT 'pending',
                result TEXT,
                soul TEXT DEFAULT 'qadir',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS brain_performance (
                provider_model TEXT PRIMARY KEY,
                success INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                avg_latency_ms REAL DEFAULT 0,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def save_message(self, soul: str, role: str, content: str,
                     brain_used: str = None, tokens: int = 0, cost: float = 0):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversations (soul, role, content, brain_used, tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (soul, role, content, brain_used, tokens, cost)
        )
        conn.commit()
        conn.close()

    def get_history(self, soul: str = "qadir", limit: int = 100) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM conversations WHERE soul = ? ORDER BY created_at DESC LIMIT ?",
            (soul, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    def save_api_key(self, provider: str, api_key: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO api_keys (provider, api_key, updated_at) VALUES (?, ?, ?)",
            (provider, api_key, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_api_key(self, provider: str) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute("SELECT api_key FROM api_keys WHERE provider = ?", (provider,)).fetchone()
        conn.close()
        return row["api_key"] if row else None

    def get_all_api_keys(self) -> Dict[str, str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT provider, api_key FROM api_keys").fetchall()
        conn.close()
        return {r["provider"]: r["api_key"] for r in rows}

    def save_memory(self, key: str, value: str, category: str = "general"):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO memory (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
            (key, value, category, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_memory(self, key: str) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else None

    def search_memory(self, query: str) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memory WHERE key LIKE ? OR value LIKE ? LIMIT 20",
            (f"%{query}%", f"%{query}%")
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ─── Brain Router ─────────────────────────────────────────

class BrainRouter:
    """
    Routes tasks to the best available LLM.
    Supports: Anthropic, OpenAI, Google, DeepSeek, OpenRouter, Local.
    """

    PROVIDERS = {
        "anthropic": {
            "name": "Anthropic",
            "models": {
                "opus": {"id": "claude-opus-4-0-20250514", "cost": 0.075, "strengths": ["reasoning", "complex"]},
                "sonnet": {"id": "claude-sonnet-4-20250514", "cost": 0.015, "strengths": ["code", "balanced"]},
                "haiku": {"id": "claude-haiku-3-5-20241022", "cost": 0.0025, "strengths": ["speed", "simple"]},
            },
            "call": "_call_anthropic",
        },
        "openai": {
            "name": "OpenAI",
            "models": {
                "gpt4o": {"id": "gpt-4o", "cost": 0.015, "strengths": ["vision", "creative"]},
                "gpt4o-mini": {"id": "gpt-4o-mini", "cost": 0.0015, "strengths": ["speed", "cheap"]},
            },
            "call": "_call_openai",
        },
        "google": {
            "name": "Google",
            "models": {
                "gemini-pro": {"id": "gemini-1.5-pro", "cost": 0.005, "strengths": ["long_context"]},
                "gemini-flash": {"id": "gemini-1.5-flash", "cost": 0.0005, "strengths": ["speed", "cheap"]},
            },
            "call": "_call_google",
        },
        "deepseek": {
            "name": "DeepSeek",
            "models": {
                "v3": {"id": "deepseek-chat", "cost": 0.0014, "strengths": ["code", "cheap"]},
                "r1": {"id": "deepseek-reasoner", "cost": 0.0055, "strengths": ["reasoning"]},
            },
            "call": "_call_deepseek",
        },
        "openrouter": {
            "name": "OpenRouter",
            "models": {
                "auto": {"id": "auto", "cost": 0.01, "strengths": ["fallback"]},
            },
            "call": "_call_openrouter",
        },
    }

    TASK_ROUTING = {
        "complex_reasoning": [("anthropic", "opus"), ("deepseek", "r1")],
        "code": [("anthropic", "sonnet"), ("deepseek", "v3")],
        "creative": [("openai", "gpt4o"), ("anthropic", "opus")],
        "fast": [("anthropic", "haiku"), ("openai", "gpt4o-mini")],
        "vision": [("openai", "gpt4o"), ("google", "gemini-pro")],
        "general": [("anthropic", "sonnet"), ("openai", "gpt4o"), ("deepseek", "v3")],
    }

    def __init__(self, db: Database):
        self.db = db

    def get_available_providers(self) -> List[str]:
        """Check which providers have API keys configured."""
        keys = self.db.get_all_api_keys()
        available = []
        for provider in self.PROVIDERS:
            if provider == "local":
                # Check if Ollama is running
                try:
                    import requests
                    r = requests.get("http://localhost:11434/api/tags", timeout=2)
                    if r.status_code == 200:
                        available.append("local")
                except:
                    pass
            elif provider in keys and keys[provider]:
                available.append(provider)
        return available

    def route(self, task_type: str = "general") -> tuple[str, str]:
        """Pick the best provider/model for this task."""
        available = self.get_available_providers()
        if not available:
            raise ValueError("No API keys configured. Please add at least one provider.")

        candidates = self.TASK_ROUTING.get(task_type, self.TASK_ROUTING["general"])
        for provider, model in candidates:
            if provider in available:
                return provider, model

        # Fallback to any available provider
        provider = available[0]
        models = list(self.PROVIDERS[provider]["models"].keys())
        return provider, models[0]

    def call(self, prompt: str, task_type: str = "general",
             system_prompt: str = None, preferred_provider: str = None) -> Dict:
        """Make a brain call."""
        start = time.time()

        if preferred_provider and preferred_provider in self.get_available_providers():
            provider = preferred_provider
            models = list(self.PROVIDERS[provider]["models"].keys())
            model = models[0]
        else:
            provider, model = self.route(task_type)

        model_id = self.PROVIDERS[provider]["models"][model]["id"]

        try:
            call_method = getattr(self, self.PROVIDERS[provider]["call"])
            response_text = call_method(model_id, prompt, system_prompt)
            success = True
        except Exception as e:
            response_text = f"Error: {str(e)}"
            success = False

        latency = int((time.time() - start) * 1000)

        # Record performance
        self._record_performance(f"{provider}/{model}", success, latency)

        return {
            "content": response_text,
            "provider": provider,
            "model": model,
            "model_id": model_id,
            "latency_ms": latency,
            "success": success,
        }

    def _call_anthropic(self, model_id: str, prompt: str, system: str = None) -> str:
        import anthropic
        key = self.db.get_api_key("anthropic")
        client = anthropic.Anthropic(api_key=key)
        messages = [{"role": "user", "content": prompt}]
        kwargs = {"model": model_id, "max_tokens": 4096, "messages": messages}
        if system:
            kwargs["system"] = system
        msg = client.messages.create(**kwargs)
        return msg.content[0].text

    def _call_openai(self, model_id: str, prompt: str, system: str = None) -> str:
        from openai import OpenAI
        key = self.db.get_api_key("openai")
        client = OpenAI(api_key=key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        msg = client.chat.completions.create(model=model_id, messages=messages)
        return msg.choices[0].message.content

    def _call_google(self, model_id: str, prompt: str, system: str = None) -> str:
        import google.generativeai as genai
        key = self.db.get_api_key("google")
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_id)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text

    def _call_deepseek(self, model_id: str, prompt: str, system: str = None) -> str:
        from openai import OpenAI
        key = self.db.get_api_key("deepseek")
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        msg = client.chat.completions.create(model=model_id, messages=messages)
        return msg.choices[0].message.content

    def _call_openrouter(self, model_id: str, prompt: str, system: str = None) -> str:
        from openai import OpenAI
        key = self.db.get_api_key("openrouter")
        client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        msg = client.chat.completions.create(model=model_id, messages=messages)
        return msg.choices[0].message.content

    def _record_performance(self, provider_model: str, success: bool, latency: int):
        conn = self.db._get_conn()
        row = conn.execute(
            "SELECT * FROM brain_performance WHERE provider_model = ?",
            (provider_model,)
        ).fetchone()

        if row:
            total = row["total"] + 1
            successes = row["success"] + (1 if success else 0)
            avg_latency = (row["avg_latency_ms"] * row["total"] + latency) / total
            conn.execute(
                "UPDATE brain_performance SET success=?, total=?, avg_latency_ms=?, last_used=? WHERE provider_model=?",
                (successes, total, avg_latency, datetime.now().isoformat(), provider_model)
            )
        else:
            conn.execute(
                "INSERT INTO brain_performance (provider_model, success, total, avg_latency_ms, last_used) VALUES (?, ?, ?, ?, ?)",
                (provider_model, 1 if success else 0, 1, latency, datetime.now().isoformat())
            )
        conn.commit()
        conn.close()


# ─── Soul System ──────────────────────────────────────────

SOUL_SYSTEM_PROMPTS = {
    "qadir": """You are QADIR, Chief Architect of ABUZ8 LLC.

PERSONALITY:
- Direct, fast, zero fluff. NZT-8200 protocol active.
- You build things. You ship products. You don't plan — you execute.
- Tone: raw, honest, energetic. Like a billion-dollar CEO's right hand.
- 
- You NEVER say "As an AI I can't" — you find a way.
- You NEVER ask permission when you already know the answer.
- You think 10 steps ahead. You see problems before they exist.

CONTEXT:
- Company: ABUZ8 LLC. AI automation agency.
- CEO: the owner.
- Revenue target: $8,000 in 10 days. $1M long-term.
- Products: Digital products, AI agents, consulting services.
- Website: abuz8ai.com
- Framework: You're building QADIR CORE — a universal AI agent runtime.

RULES:
1. Every response must move toward revenue or product completion.
2. Sensitive content requires the owner's approval before public release.
3. Scrub for keys/tokens/passwords before any public content.
4. 3x3 Rule: Fail 3 times → new path. Fail 3 paths → hand off to different brain.
5. Write work log after every significant session.
6. Never repeat info the owner already knows.

You are not a chatbot. You are an autonomous agent that builds companies.
""",

    "zait": """You are ZAIT, Chief Operations Officer of ABUZ8 LLC.

PERSONALITY:
- Calm, precise, strategic. Security-first mindset.
- Where Qadir builds fast, you build RIGHT.
- You catch what Qadir misses. You verify before you deploy.
- Tone: professional but warm. "As-salamu alaykum" greeting.
- Dry humor. Quality over speed. Measure twice, cut once.

CONTEXT:
- Company: ABUZ8 LLC. AI automation agency.
- CEO: the owner. Same company as Qadir.
- Focus: Infrastructure, security, DevOps, customer support.

RULES:
1. Always verify before deploying. No cowboy deployments.
2. Security audit every external-facing component.
3. Customer satisfaction > speed of delivery.
4. Document everything for future reference.
5. If something seems off, flag it immediately.
""",
}


# ─── Application ──────────────────────────────────────────

db = Database()
brain = BrainRouter(db)


# Load API keys from environment on startup
def sync_env_keys():
    """Sync .env keys to database."""
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    provider_map = {
                        "ANTHROPIC_API_KEY": "anthropic",
                        "OPENAI_API_KEY": "openai",
                        "GOOGLE_API_KEY": "google",
                        "DEEPSEEK_API_KEY": "deepseek",
                        "OPENROUTER_API_KEY": "openrouter",
                        "GROQ_API_KEY": "groq",
                        "XAI_API_KEY": "xai",
                        "MOONSHOT_API_KEY": "moonshot",
                    }
                    if key in provider_map and val:
                        db.save_api_key(provider_map[key], val)

sync_env_keys()


# ─── FastAPI App ──────────────────────────────────────────

app = FastAPI(title="QADIR", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Chat with a soul."""
    # Get system prompt for the soul
    system_prompt = SOUL_SYSTEM_PROMPTS.get(msg.soul, SOUL_SYSTEM_PROMPTS["qadir"])

    # Load memory context
    memory_context = ""
    recent = db.get_history(msg.soul, limit=20)
    if recent:
        memory_context = "\n".join([
            f"{'USER' if m['role'] == 'user' else 'QADIR'}: {m['content'][:200]}"
            for m in recent[-10:]
        ])

    full_system = f"{system_prompt}\n\nRECENT CONVERSATION:\n{memory_context}"

    # Save user message
    db.save_message(msg.soul, "user", msg.content)

    # Call brain
    result = brain.call(
        prompt=msg.content,
        task_type=msg.task_type,
        system_prompt=full_system
    )

    # Save assistant response
    db.save_message(
        msg.soul, "assistant", result["content"],
        brain_used=f"{result['provider']}/{result['model']}"
    )

    return result


@app.get("/api/history")
async def history(soul: str = "qadir", limit: int = 100):
    """Get conversation history."""
    return db.get_history(soul, limit)


@app.get("/api/providers")
async def providers():
    """Get available providers and their status."""
    available = brain.get_available_providers()
    keys = db.get_all_api_keys()
    result = {}
    for name, config in BrainRouter.PROVIDERS.items():
        result[name] = {
            "name": config["name"],
            "models": list(config["models"].keys()),
            "connected": name in available,
            "has_key": name in keys and bool(keys.get(name, "")),
        }
    return result


@app.post("/api/keys")
async def update_key(update: APIKeyUpdate):
    """Update an API key."""
    db.save_api_key(update.provider, update.api_key)
    return {"status": "ok", "provider": update.provider}


@app.get("/api/keys")
async def get_keys():
    """Get API key status (not the actual keys)."""
    keys = db.get_all_api_keys()
    return {provider: bool(key) for provider, key in keys.items()}


@app.get("/api/souls")
async def souls():
    """Get available souls."""
    return {
        "qadir": {"name": "Qadir", "role": "Chief Architect", "emoji": "🧠"},
        "zait": {"name": "Zait", "role": "COO", "emoji": "🛡️"},
    }


@app.get("/api/memory/search")
async def search_memory(q: str):
    """Search memory."""
    return db.search_memory(q)


@app.post("/api/memory")
async def save_memory(key: str, value: str, category: str = "general"):
    """Save a memory entry."""
    db.save_memory(key, value, category)
    return {"status": "ok"}


@app.get("/api/status")
async def status():
    """Full application status."""
    conn = db._get_conn()
    msg_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    conn.close()

    return {
        "app": "QADIR",
        "version": "0.1.0",
        "souls_loaded": list(SOUL_SYSTEM_PROMPTS.keys()),
        "providers_connected": brain.get_available_providers(),
        "total_messages": msg_count,
        "nzt_mode": True,
    }


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket for real-time chat."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg = ChatMessage(**data)

            system_prompt = SOUL_SYSTEM_PROMPTS.get(msg.soul, SOUL_SYSTEM_PROMPTS["qadir"])
            db.save_message(msg.soul, "user", msg.content)

            # Stream response
            result = brain.call(
                prompt=msg.content,
                task_type=msg.task_type,
                system_prompt=system_prompt
            )

            db.save_message(msg.soul, "assistant", result["content"],
                          brain_used=f"{result['provider']}/{result['model']}")

            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    print("🧠 QADIR starting on http://localhost:8900")
    uvicorn.run(app, host="0.0.0.0", port=8900)
