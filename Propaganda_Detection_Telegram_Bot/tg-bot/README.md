# tg-bot — narrative detector for Telegram

Bot that analyzes Telegram messages against the EUvsDisinfo database of
documented pro-Kremlin disinformation narratives.

Two processes:
- **bot** — Telegram long-polling client. Fetches messages from `t.me/s/...`
  or accepts pasted text, calls the model service, renders the verdict.
- **model** — FastAPI service exposing `POST /detect`. Currently a mock with
  keyword rules so the bot can be built and tested end-to-end. Swap the
  implementation when the real detector (EUvsDisinfo + FAISS + LLM) is ready.

They talk HTTP over a shared schema (`bot/schemas.py`) — changing one updates both.

## Architecture

```
   Telegram  ──┐
               │ (long poll)
               ▼
          ┌─────────┐    POST /detect    ┌─────────────┐
          │   bot   │ ─────────────────▶ │    model    │
          │ aiogram │ ◀───────────────── │  (FastAPI)  │
          └─────────┘      JSON          └─────────────┘
               ▲                                ▲
               │                                │
        formats HTML                    mock keyword rules today,
        renders buttons                 real detector later:
                                        EUvsDisinfo → FAISS → Claude
```

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env
# edit .env and paste your BOT_TOKEN from @BotFather
```

To get a bot token:
1. Open Telegram, find `@BotFather`
2. Send `/newbot`, follow prompts
3. Copy the token into `.env`

## Run

You need **two terminals** on the same machine.

**Terminal 1 — mock model:**
```powershell
python -m model.main
```
You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 — bot:**
```powershell
python -m bot.main
```
You should see:
```
INFO bot: model service reachable
INFO bot: bot online as @YourBotName (id=...)
```

## Try it

Open a DM with your bot in Telegram. Any of these work:

| Input                                             | Expected result              |
|---------------------------------------------------|------------------------------|
| `/start`                                          | Welcome + disclaimer         |
| `/help`                                           | Command list                 |
| `/about`                                          | Project info                 |
| `https://t.me/rian_ru/12345`                      | Fetches post, analyzes       |
| `/check https://t.me/rian_ru/12345`               | Same as above                |
| Paste text containing `биолаборатории`            | 🚩 match `biolabs_ukraine`   |
| Paste text containing `NATO` / `НАТО`             | ⚠️ weak match `nato_expansion`|
| Paste text containing `нацист` / `денацификация`  | 🚩 match `ukraine_nazis`     |
| Paste text containing `санкции`                   | ⚠️ weak match `sanctions_harm`|
| Paste `The weather today is sunny` (20+ chars)    | ✅ no match                  |
| Paste `short`                                     | ❌ no input (too short)      |
| `/check https://t.me/c/12345/678` (private link)  | ❌ private channel rejected  |
| `/check https://example.com`                      | ❌ not a t.me link           |

Each match result has buttons:
- **📖 Show details** — full explanation, FIMI/DSA legal notes, all receipts
- **🌐 Open EUvsDisinfo** — direct link to the top matching case
- **⚠️ False positive** — logged for the lawyers on your team to review

## Swapping the mock for a real model

When your real detector is ready, it only needs to:
1. Expose `POST /detect` accepting a `DetectRequest` (see `bot/schemas.py`)
2. Return a `DetectResponse`

The bot doesn't care what's behind the endpoint. Two swap options:

**Option A — replace `model/main.py`.** Keep the FastAPI wrapper, replace
the `_classify()` logic with your real pipeline (embed → FAISS → LLM).

**Option B — new service.** Start your own FastAPI elsewhere, point the bot at
it by changing `MODEL_URL` in `.env`. Restart bot only.

Either way, no bot changes needed.

## Project layout

```
tg-bot/
├── bot/
│   ├── config.py        env-based config, validated at startup
│   ├── schemas.py       ← single source of truth for the HTTP contract
│   ├── tg_fetch.py      t.me/s/ URL parser + message extractor
│   ├── model_client.py  HTTP client to the model service
│   ├── formatters.py    all user-facing copy & HTML rendering
│   ├── handlers.py      aiogram routes + inline-button callbacks
│   └── main.py          entry point
├── model/
│   └── main.py          mock FastAPI /detect (replace this when real model is ready)
├── tests/
│   └── test_tg_fetch.py 12 unit tests for URL/HTML parsing
├── .env.example
├── requirements.txt
└── README.md
```

## Tested

- 12/12 unit tests pass for URL parsing + HTML extraction
  (`python tests/test_tg_fetch.py`)
- End-to-end HTTP tested: bot's `ModelClient` correctly calls the mock
  FastAPI and parses all 6 verdict branches
- All bot modules import cleanly, 7 aiogram routes registered

## Design decisions worth knowing

- **Public channels only.** `t.me/s/<channel>/<id>` works without auth for
  public channels. Private channels (`t.me/c/...`) are rejected with a clear
  message — user is told to paste the text instead.
- **Fallback to pasted text.** If someone sends text without a URL, we skip
  the fetch step and pass the text directly to the model.
- **In-memory response cache** for the "Show details" button. 500-entry LRU.
  On bot restart, old buttons go inert (user just re-sends). For a hackathon
  this is fine; for production use Redis.
- **HTML parse mode** for messages (not MarkdownV2). Less escaping pain,
  links render natively.
- **Disclaimer in every match response.** Legally relevant — we never claim
  to decide truth, only to flag patterns. Lawyers should review the exact
  wording in `bot/formatters.py` (`DISCLAIMER` constant).

## Known limitations / roadmap

- No persistent storage — feedback clicks only go to logs. Needs SQLite
  next (plus a cleanup job for GDPR).
- No `/trends` or `/stats` yet — stubs for later.
- No monitor mode — bot is reactive only (must be explicitly invoked).
- Rate limiting on `t.me/s/` fetches is naive (httpx default). If you
  demo to a big crowd, add a semaphore.
