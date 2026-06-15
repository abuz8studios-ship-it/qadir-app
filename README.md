# QADIR — AI Agent Application

**Your AI Chief Architect. Desktop application. Plug in keys. Start working.**

## Quick Start

```bash
# 1. Enter the directory
cd /mnt/e/ABU/QADIR_APP

# 2. Launch
python3 launch.py

# 3. Browser opens automatically at http://localhost:8900
```

## What You Get

- **Chat interface** — Talk to Qadir or Zait
- **Multi-brain routing** — Automatically picks the best AI for each task
- **Memory system** — Remembers everything across sessions
- **Agent system** — Multiple AI personalities (Qadir, Zait, more coming)
- **Settings panel** — Add API keys, see provider status

## Adding API Keys

1. Open the app
2. Click ⚙️ Settings
3. Paste your API keys
4. Click Save

Supported providers:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)
- DeepSeek
- OpenRouter (universal fallback)

## Agents

| Agent | Role | Personality |
|-------|------|-------------|
| 🧠 Qadir | Chief Architect | Direct, fast, aggressive |
| 🛡️ Zait | COO | Calm, precise, security-first |

## Architecture

```
QADIR_APP/
├── launch.py           ← Run this to start
├── requirements.txt    ← Python dependencies
├── backend/
│   └── app.py          ← FastAPI server (brain router, chat, memory)
├── frontend/
│   ├── index.html      ← Chat UI
│   ├── css/style.css   ← Dark theme styles
│   └── js/app.js       ← Frontend logic
├── config/             ← App configuration
├── data/               ← SQLite database (auto-created)
└── logs/               ← Application logs
```

## File Structure

Everything is local. No data leaves your machine unless you:
- Send a message to a cloud AI provider
- That's it

Your API keys, conversations, and memory are stored in SQLite on your machine.

## Custom Port

```bash
python3 launch.py --port 9000
```

## Headless Mode (no browser)

```bash
python3 launch.py --no-open
```
Then access at http://localhost:8900 from any device on your network.
