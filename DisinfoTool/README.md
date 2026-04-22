# DisInfoTracer OSS 🔍
**Trace disinformation back to its first web mention — 100% open-source, zero paid APIs.**

---

## Tech Stack (all free/open-source)

| Component | Library / API | Key needed? |
|---|---|---|
| LLM reasoning | **Ollama** (llama3/mistral/phi3) — local | ❌ No |
| LLM fallback | **HuggingFace** public inference | ❌ No |
| Semantic similarity | **sentence-transformers** `all-MiniLM-L6-v2` | ❌ No |
| Archive dating | **Wayback Machine CDX API** | ❌ No |
| Web search | **DuckDuckGo Instant API** | ❌ No |
| Web archive | **Common Crawl Index API** | ❌ No |
| News search | **Bing News RSS** (no key) | ❌ No |
| Scraping | **trafilatura** + BeautifulSoup | ❌ No |
| Backend | **FastAPI** + uvicorn | ❌ No |

---

## Quick Start

### 1. Install Python dependencies
```bash
pip install fastapi uvicorn trafilatura requests aiohttp \
            beautifulsoup4 sentence-transformers numpy \
            scikit-learn python-multipart
```

### 2. (Optional but recommended) Install Ollama for LLM reasoning
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3        # ~4GB, best quality
# OR lighter alternatives:
ollama pull mistral       # ~4GB
ollama pull phi3          # ~2GB, fastest
ollama serve              # starts on localhost:11434
```

### 3. Run the backend
```bash
python backend.py
# Server starts at http://localhost:8000
```

### 4. Open the UI
```
http://localhost:8000
```

---



### Why startup may appear stuck

On first run, `sentence-transformers` can take significant time to initialize/download model assets.
That can delay FastAPI startup enough to fail short health checks.

### Recommended smoke test on Windows

```powershell
cd disinfo
.\.venv\Scripts\python.exe backend.py
```

Then wait until Uvicorn prints its running banner before opening:

```
http://localhost:8000
```

If startup remains too slow, you can still validate the code path with:

```powershell
cd disinfo
.\.venv\Scripts\python.exe -c "import backend; print('Import successful')"
```

---

## How It Works

```
Claim Input
    │
    ▼
[LLM / Rules] Decompose into 3-5 atomic search queries
    │
    ├──▶ Wayback Machine CDX API   (archived pages, date-sorted)
    ├──▶ DuckDuckGo Instant API    (no key, no rate limit)
    ├──▶ Common Crawl Index API    (petabyte web archive)
    └──▶ Bing News RSS             (no key needed)
    │
    ▼
Scrape each candidate URL (trafilatura)
    │
    ▼
[sentence-transformers] Compute cosine similarity to claim
    │
    ▼
[Ollama / Rules] Verify + classify each source
    │
    ▼
[Ollama / HuggingFace / Rules] Origin analysis + mutation narrative
    │
    ▼
Timeline + Mutation Chain + Earliest Source UI
```

---

## LLM Modes

The system auto-detects and uses the best available LLM:

| Mode | When used | Quality |
|---|---|---|
| `ollama+embeddings` | Ollama running locally | ★★★ Best |
| `embeddings+rules` | No Ollama (fallback) | ★★ Good |
| HuggingFace inference | Secondary fallback | ★★ Good |

Even without Ollama, the **embedding-based verification** (sentence-transformers cosine similarity) gives solid relevance scoring with no LLM required.

---

## Configuration

Set environment variables to customize:

```bash
OLLAMA_URL=http://localhost:11434   # Ollama server URL
OLLAMA_MODEL=llama3                  # Model to use (llama3, mistral, phi3)
```

---

## Changing the Ollama Model

```bash
# Faster / smaller
ollama pull phi3
OLLAMA_MODEL=phi3 python backend.py

# More reasoning
ollama pull llama3:70b
OLLAMA_MODEL=llama3:70b python backend.py

# Multilingual
ollama pull aya
OLLAMA_MODEL=aya python backend.py
```

---

## Project Structure

```
disinfotracer-oss/
├── backend.py      # FastAPI server, all pipeline logic
├── index.html      # Single-file frontend (dark terminal UI)
├── cache_oss.db    # SQLite cache (auto-created)
└── README.md
```

---

## Extending

### Add more search sources
In `backend.py`, add a new function following the pattern of `wayback_search()` and call it in the `trace_claim()` endpoint.

### Use a different embedding model
Change `"all-MiniLM-L6-v2"` in `get_embedder()` to any HuggingFace sentence-transformer, e.g. `"all-mpnet-base-v2"` for higher accuracy.

### Add date-range binary search
The Wayback CDX API supports `from` and `to` params — implement a binary search to pinpoint the earliest date a claim appeared within a narrowing date window.
