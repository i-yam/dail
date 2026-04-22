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

## Semantic matching with known disinformation articles

The bot now includes a backend matcher in `services/disinfo_matcher.py` that compares incoming text against the EUvsDisinfo article base in `data/processed/euvsdisinfo_reports.csv`.

- Uses sentence embeddings (`all-MiniLM-L6-v2`) when available.
- Falls back to a lexical TF-IDF-like matcher if embeddings cannot be loaded.
- Allows switching source CSV via `DISINFO_ARTICLES_CSV` (file must include `title`, `summary`, `response`, `report_url` columns).
- Exposes a clean service API for Telegram integration:

```python
from services.disinfo_matcher import find_similar_disinfo_articles

matches = find_similar_disinfo_articles(
    message_text="Your incoming Telegram message",
    top_k=3,
    min_score=0.18,
)
```

Each match returns article metadata (`title`, `report_url`, `date_of_publication`) plus a similarity score, so bot developers can show "possible source narratives" without relying on exact text overlap.

Matching uses a disinformation-oriented score:
- compare input to the article's disinfo claim (`summary`/`title`) and debunk (`response`) separately
- keep candidates where claim similarity is stronger than debunk similarity
- down-weight broad neutral texts that do not contain disinfo-style framing cues

Pipeline behavior:
- if verified DB matches are found, return those matches
- if no verified DB matches are found, run classifier fallback (local model in `classifier/classifier.py` when available)

### Optional LLM verification stage

For better precision on near-duplicate but different events, you can enable a second-stage LLM check:

- Stage 1: retrieval gets top likely disinfo claims from the database
- Stage 2: LLM verifies relation between message and each retrieved claim
  - `supports_claim`
  - `refutes_claim`
  - `different_event_or_neutral`
  - `uncertain`

Configure `.env`:

```bash
DISINFO_LLM_API_URL=https://api.openai.com/v1/chat/completions
DISINFO_LLM_API_KEY=your_key
DISINFO_LLM_MODEL=gpt-4o-mini
DISINFO_LLM_TIMEOUT=20
```

Call with verification enabled:

```python
matches = find_similar_disinfo_articles(
    message_text="...",
    top_k=3,
    verify_with_llm=True,
)
```

### Test without Telegram bot

Use the standalone CLI tester:

```bash
python3 scripts/test_disinfo_matcher.py --text "EU uses censorship tools to influence elections"
```

Or interactive mode:

```bash
python3 scripts/test_disinfo_matcher.py --interactive
```

Test against a specific compatible CSV file:

```bash
python3 scripts/test_disinfo_matcher.py --text "..." --csv-path "/absolute/path/to/compatible_reports.csv"
```

With LLM verification enabled:

```bash
python3 scripts/test_disinfo_matcher.py --text "..." --verify-llm
```

---

## Adding the bot to a Telegram group

1. Create a group or use an existing one
2. Add the bot as a member: **Group Settings → Members → search your bot's username**
3. Promote to **Admin** (so it can read messages)
4. Send `/watch` in the group to start monitoring

No cloud hosting needed — polling mode works with the bot running locally.
