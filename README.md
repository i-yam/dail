# Propaganda Watchdog Bot  🤖

> **DIAL 2026 Hackathon** · Problem 03 · Team bot layer

A Telegram bot that spots propaganda narratives in real time.
Pluggable into any channel as a slash command.

---

## Project structure

```
help_pavel/
├── bot/
│   ├── main.py          # Entry point — run this
│   ├── handlers.py      # All /command handlers + message watcher
│   └── formatter.py     # Telegram HTML message formatting
├── services/
│   ├── classifier.py    # HTTP client → teammates' model API (+ mock fallback)
│   └── __init__.py
├── storage/
│   ├── db.py            # SQLite — messages, flagged, watch_chats
│   └── __init__.py
├── data/                # Auto-created — holds bot.db
├── .env.example
├── requirements.txt
└── index.html           # Hackathon landing page (from repo)
```

---

## Quick start

### 1. Get a Bot Token
Open Telegram → search **@BotFather** → `/newbot` → copy the token.

Then disable privacy mode so the bot can read all messages:
```
/setprivacy → @YourBot → Disable
```

### 2. Install dependencies

```bash
cd help_pavel
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and paste your TELEGRAM_BOT_TOKEN
```

### 4. Run the bot

```bash
python bot/main.py
```

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | List all commands |
| `/watch` | Toggle real-time monitoring on/off |
| `/analyze` | Analyse last 10 stored messages |
| `/analyze 20` | Analyse last 20 stored messages |
| `/analyze <text>` | Analyse a specific text snippet |
| `/report` | Show last 10 flagged messages (with receipts) |
| `/report 20` | Show last 20 flagged messages |
| `/cluster` | Show narrative cluster map |

---

## Classifier API integration

Set `CLASSIFIER_API_URL` in `.env` to point at the teammates' model:

```
CLASSIFIER_API_URL=http://their-server:8001
```

### Expected contract

```
POST /classify
{ "text": "message content" }

→ 200 OK
{
    "is_propaganda": true,
    "confidence": 0.92,
    "narrative_label": "Anti-NATO destabilisation",
    "cluster_id": "cluster_42"     ← optional
}
```

If the API URL is not set or unreachable, the bot automatically falls back to a **built-in mock classifier** (keyword heuristics) so the demo works standalone.

---

## Adding the bot to a Telegram group

1. Create a group or use an existing one
2. Add the bot as a member: **Group Settings → Members → search your bot's username**
3. Promote to **Admin** (so it can read messages)
4. Send `/watch` in the group to start monitoring

No cloud hosting needed — polling mode works with the bot running locally.
