"""
DisInfoTracer OSS — 100% open-source disinformation provenance engine
LLM: Ollama (local) with llama3 / mistral / phi3 — fallback to rule-based
Embeddings: sentence-transformers (all-MiniLM-L6-v2) — local, free
Search: Wayback CDX + DuckDuckGo + Common Crawl — all free, no keys
Scraper: trafilatura + BeautifulSoup
"""

import asyncio, json, re, time, sqlite3, hashlib, os, math
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse
from typing import Optional
import warnings
import requests
import trafilatura
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import numpy as np

# ─── Semantic similarity — tries sentence-transformers, falls back to TF-IDF ──
_embedder = None
_USE_TFIDF = False

STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "are", "was", "were", "have", "has",
    "from", "they", "their", "been", "will", "its", "not", "but", "can", "all", "more",
    "which", "would", "could", "should", "into", "about", "after", "before", "where", "when",
    "what", "who", "whom", "your", "you", "than", "then", "also", "just", "some", "such"
}

RELIABILITY_PRIOR = {
    "official": 0.95,
    "debunker": 0.9,
    "mainstream": 0.78,
    "social": 0.5,
    "unknown": 0.42,
    "fringe": 0.18,
    "satire": 0.25,
}

SOURCE_BASE_PRIOR = {
    "wayback": 0.72,
    "commoncrawl": 0.65,
    "bing_news": 0.7,
    "duckduckgo": 0.55,
    "ddg_web": 0.58,
    "reddit": 0.48,
    "twitter": 0.45,
    "archive_is": 0.62,
    "google_scholar": 0.74,
}

def get_embedder():
    global _embedder, _USE_TFIDF
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
        print("[INFO] Loading sentence-transformer (all-MiniLM-L6-v2)…")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        print("[INFO] Sentence-transformer ready.")
        _USE_TFIDF = False
    except Exception as e:
        print(f"[INFO] sentence-transformers unavailable ({e}). Using TF-IDF fallback.")
        _embedder = "tfidf"
        _USE_TFIDF = True
    return _embedder

def _tfidf_vec(text: str) -> np.ndarray:
    """Lightweight bag-of-words vector for offline similarity."""
    import re, hashlib
    from collections import Counter
    tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    stops = {'the','and','for','that','with','this','are','was','were','have','has',
             'from','they','their','been','will','its','not','but','can','all','more'}
    tokens = [t for t in tokens if t not in stops]
    counts = Counter(tokens)
    vec = np.zeros(512)
    for word, cnt in counts.items():
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % 512
        vec[idx] += cnt
    norm = np.linalg.norm(vec)
    return vec / (norm + 1e-9)

def embed(text: str) -> np.ndarray:
    emb = get_embedder()
    if _USE_TFIDF:
        return _tfidf_vec(text)
    return emb.encode(text)

def cosine_sim(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def clean_claim_text(claim: str) -> str:
    text = normalize_ws(claim)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"\bpls\b|\bplease\b|\bgive me\b", "", text, flags=re.IGNORECASE)
    text = normalize_ws(text)
    return text

def extract_named_entities(text: str) -> list[str]:
    # Heuristic NER for prototype: proper nouns / acronyms / years.
    ents = set()
    for m in re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,}(?:\s+[A-Z]{2,})*)\b", text):
        if len(m) >= 3:
            ents.add(normalize_ws(m))
    for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text):
        ents.add(y)
    return sorted(ents)[:12]

def extract_noun_phrases(text: str) -> list[str]:
    tokens = [t for t in re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", text.lower()) if t not in STOPWORDS]
    phrases = []
    for n in (2, 3):
        for i in range(0, max(0, len(tokens) - n + 1)):
            chunk = tokens[i:i+n]
            if any(len(x) > 4 for x in chunk):
                phrases.append(" ".join(chunk))
    # Keep unique by order.
    seen = set()
    out = []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:12]

def claim_features(claim: str) -> dict:
    cleaned = clean_claim_text(claim)
    return {
        "cleaned_claim": cleaned,
        "named_entities": extract_named_entities(cleaned),
        "noun_phrases": extract_noun_phrases(cleaned),
    }

def canonicalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        scheme = p.scheme.lower() if p.scheme else "https"
        host = (p.netloc or "").lower()
        host = re.sub(r"^www\.", "", host)
        path = re.sub(r"/+", "/", p.path or "/")
        path = path.rstrip("/") or "/"
        return f"{scheme}://{host}{path}"
    except Exception:
        return url

def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        return re.sub(r"^www\.", "", host)
    except Exception:
        return ""

def timestamp_to_date(ts: str) -> str:
    if not ts or ts.startswith("9999"):
        return "unknown"
    try:
        return datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return "unknown"

def time_prior(timestamp: str) -> float:
    if not timestamp or timestamp.startswith("9999"):
        return 0.35
    try:
        y = int(timestamp[:4])
        now_y = datetime.utcnow().year
        age = max(0, now_y - y)
        return min(1.0, 0.35 + (age / 30.0))
    except Exception:
        return 0.4

def parse_llm_json_object(raw: str) -> Optional[dict]:
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    body = match.group().strip()
    try:
        return json.loads(body)
    except Exception:
        # Light cleanup for common invalid JSON emissions.
        body2 = body.replace("'", '"')
        body2 = re.sub(r",\s*([}\]])", r"\1", body2)
        try:
            return json.loads(body2)
        except Exception:
            return None

def build_query_variants(claim: str, features: dict) -> list[str]:
    queries = llm_decompose(claim)
    fallback = rule_based_queries(claim)
    seeds = []
    seeds.extend(queries)
    seeds.extend(fallback)
    seeds.extend(features.get("noun_phrases", [])[:3])
    # include one entity anchored query for provenance
    if features.get("named_entities"):
        seeds.append(" ".join(features["named_entities"][:2]) + " first mention")

    out = []
    seen = set()
    for q in seeds:
        qn = normalize_ws(q)
        if not qn:
            continue
        key = qn.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(qn)
    return out[:5]

# ─── Ollama (local LLM) ───────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def ollama_chat(prompt: str, system: str = "", max_tokens: int = 600) -> str:
    """Call local Ollama LLM. Returns text or raises."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.2}
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("response", "").strip()

# ─── HuggingFace Inference API (free tier fallback, no key for public models) ──
HF_API = "https://api-inference.huggingface.co/models"

def hf_inference(prompt: str, model: str = "mistralai/Mistral-7B-Instruct-v0.1") -> str:
    """HuggingFace free inference — rate limited but no key needed for public models."""
    try:
        r = requests.post(
            f"{HF_API}/{model}",
            json={"inputs": prompt, "parameters": {"max_new_tokens": 400, "temperature": 0.2}},
            timeout=60
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
                # Strip the prompt from the response
                if prompt in text:
                    text = text[len(prompt):].strip()
                return text
    except Exception as e:
        print(f"[HF] Error: {e}")
    return ""

# ─── Rule-based fallback (no LLM needed) ─────────────────────────────────────
DISINFO_PATTERNS = {
    "5g": {"queries": ["5G coronavirus health effects", "5G towers COVID", "5G radiation immune"], "type": "manufactured"},
    "microchip": {"queries": ["vaccine microchip tracking", "Bill Gates vaccine chip", "microchip vaccine conspiracy"], "type": "manufactured"},
    "bleach": {"queries": ["bleach cure coronavirus", "disinfectant COVID treatment", "bleach drink cure"], "type": "satire_taken_literally"},
    "climate": {"queries": ["NASA climate data fake", "climate data fabricated", "global warming hoax NASA"], "type": "manufactured"},
    "election": {"queries": ["election fraud evidence", "voter fraud machines", "stolen election"], "type": "manufactured"},
    "soros": {"queries": ["Soros funding protest", "George Soros conspiracy"], "type": "manufactured"},
    "flat earth": {"queries": ["flat earth NASA lies", "earth flat proof"], "type": "manufactured"},
    "chemtrail": {"queries": ["chemtrails poison population", "chemtrail government spray"], "type": "manufactured"},
}

def rule_based_queries(claim: str) -> list[str]:
    claim_lower = claim.lower()
    for key, val in DISINFO_PATTERNS.items():
        if key in claim_lower:
            return val["queries"]
    # Generic extraction: pull noun phrases / key terms
    words = re.findall(r'\b[A-Za-z]{4,}\b', claim)
    stopwords = {"that","this","with","have","from","they","will","been","were","their","what","said","about","which"}
    keywords = [w for w in words if w.lower() not in stopwords][:8]
    queries = []
    if len(keywords) >= 4:
        queries.append(" ".join(keywords[:4]))
        queries.append(" ".join(keywords[2:6]))
        queries.append(" ".join(keywords[:3]) + " origin")
    elif keywords:
        queries.append(" ".join(keywords))
        queries.append(" ".join(keywords) + " first report")
    return queries[:5] or ["disinformation " + claim[:50]]

def rule_based_origin(claim: str, hits: list) -> dict:
    claim_lower = claim.lower()
    origin_type = "unclear"
    for key, val in DISINFO_PATTERNS.items():
        if key in claim_lower:
            origin_type = val["type"]
            break

    sorted_hits = sorted(hits, key=lambda x: x.get("timestamp", "99999999"))
    earliest = sorted_hits[0] if sorted_hits else None

    narrative_map = {
        "manufactured": "This claim appears to have been deliberately created and spread through fringe online communities before reaching mainstream social media.",
        "satire_taken_literally": "Evidence suggests this originated as satire or parody content that was subsequently shared without the original satirical context.",
        "legitimate_distorted": "A legitimate concern or report appears to have been distorted and amplified beyond its original scope.",
        "unclear": "The origin of this claim could not be definitively determined from available archived sources."
    }

    return {
        "origin_type": origin_type,
        "earliest_known_source": earliest["url"] if earliest else "",
        "origin_date": earliest["date"] if earliest else "unknown",
        "narrative": narrative_map.get(origin_type, narrative_map["unclear"]),
        "mutation_summary": "The claim appears to have been rephrased and amplified as it spread across different platforms.",
        "confidence": "medium" if hits else "low"
    }

# ─── LLM dispatch: tries Ollama → HuggingFace → rule-based ──────────────────
def llm_decompose(claim: str) -> list[str]:
    prompt = f"""Generate 3-5 short web search queries (3-7 words each) to find the EARLIEST online mentions of this claim.
Focus on unique phrases that would appear in the original source.
Claim: "{claim}"
Respond with ONLY a JSON array. Example: ["query one", "query two", "query three"]
JSON:"""

    # Try Ollama first
    if ollama_available():
        try:
            raw = ollama_chat(prompt, system="You are a disinformation researcher. Output only valid JSON arrays.")
            raw = re.sub(r"```json|```", "", raw).strip()
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            print(f"[Ollama decompose] {e}")

    # Try HuggingFace
    try:
        raw = hf_inference(prompt)
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[HF decompose] {e}")

    # Fallback: rule-based
    return rule_based_queries(claim)

def llm_verify(claim: str, page_text: str, url: str, date: str) -> dict:
    if not page_text or len(page_text.strip()) < 50:
        return {"contains_claim": False, "relevance_score": 0,
                "version_of_claim": None, "source_type": "unrelated",
                "key_differences": "", "credibility_signals": "unknown"}

    # Embedding-based verification (always available, no LLM needed)
    get_embedder()
    claim_vec = embed(claim)
    page_vec = embed(page_text[:1000])
    sim = cosine_sim(claim_vec, page_vec)
    relevance = round(sim * 10, 1)

    base_result = {
        "contains_claim": sim > 0.25,
        "relevance_score": min(10, relevance),
        "version_of_claim": None,
        "source_type": "reshare" if sim > 0.4 else ("unrelated" if sim < 0.25 else "mutation"),
        "key_differences": "",
        "credibility_signals": _infer_credibility(url)
    }

    if not base_result["contains_claim"]:
        return base_result

    # If Ollama available, enrich with LLM analysis
    if ollama_available() and sim > 0.25:
        snippet = page_text[:800]
        prompt = f"""Analyze this webpage snippet for the claim below.
Claim: "{claim}"
Snippet: {snippet}
Respond ONLY with JSON:
{{"contains_claim": true/false, "relevance_score": 0-10, "version_of_claim": "how claim is stated here or null", "source_type": "original_source|reshare|mutation|debunking|unrelated", "key_differences": "what changed", "credibility_signals": "satire|fringe|mainstream|official|unknown"}}
JSON:"""
        try:
            raw = ollama_chat(prompt, max_tokens=300)
            result = parse_llm_json_object(raw)
            if result:
                result["relevance_score"] = min(10, float(result.get("relevance_score", relevance)))
                return result
        except Exception as e:
            print(f"[Ollama verify] {e}")

    return base_result

def _infer_credibility(url: str) -> str:
    url_lower = url.lower()
    if any(x in url_lower for x in [".gov", ".edu", "reuters", "bbc", "apnews", "npr"]):
        return "official"
    if any(x in url_lower for x in ["snopes", "factcheck", "politifact", "fullfact"]):
        return "debunker"
    if any(x in url_lower for x in ["nytimes", "theguardian", "wsj", "washingtonpost", "ft.com", "economist"]):
        return "mainstream"
    if any(x in url_lower for x in ["4chan", "8kun", "gab", "parler", "telegram", "infowars", "naturalnews"]):
        return "fringe"
    if any(x in url_lower for x in ["reddit", "twitter", "facebook", "youtube"]):
        return "social"
    return "unknown"

def llm_origin_summary(claim: str, hits: list) -> dict:
    if not hits:
        return rule_based_origin(claim, hits)

    hits_text = "\n".join([
        f"- {h['date']} | {h.get('analysis',{}).get('source_type','?')} | {h['url'][:80]} | {h.get('analysis',{}).get('version_of_claim','')}"
        for h in hits[:8]
    ])

    prompt = f"""You are a disinformation analyst. Given these chronologically sorted sources for a claim, determine its origin.
Claim: "{claim}"
Sources:
{hits_text}
Respond ONLY with JSON:
{{"origin_type": "satire_taken_literally|manufactured|legitimate_distorted|true_but_miscontextualized|unclear", "earliest_known_source": "url", "origin_date": "YYYY-MM-DD", "narrative": "2-3 sentence explanation", "mutation_summary": "how wording changed", "confidence": "high|medium|low"}}
JSON:"""

    if ollama_available():
        try:
            raw = ollama_chat(prompt, max_tokens=500)
            match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            print(f"[Ollama origin] {e}")

    try:
        raw = hf_inference(prompt)
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[HF origin] {e}")

    return rule_based_origin(claim, hits)

# ─── Database ─────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect("cache_oss.db")
    db.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY, value TEXT, created_at REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS traces (
        id TEXT PRIMARY KEY, claim TEXT, result TEXT, created_at REAL)""")
    db.commit()
    return db

def cache_get(key: str, ttl=3600):
    db = get_db()
    row = db.execute("SELECT value FROM cache WHERE key=? AND created_at > ?",
                     (key, time.time() - ttl)).fetchone()
    return json.loads(row[0]) if row else None

def cache_set(key: str, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)",
               (key, json.dumps(value), time.time()))
    db.commit()

# ─── Search Engines (all free, no keys) ───────────────────────────────────────
def wayback_search(query: str, max_results=15) -> list[dict]:
    ck = f"wb_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        # Strategy 1: URL pattern match
        r = requests.get("http://web.archive.org/cdx/search/cdx", params={
            "url": f"*{query.replace(' ','+')}*",
            "matchType": "domain", "output": "json",
            "fl": "timestamp,original,statuscode,mimetype",
            "filter": ["statuscode:200", "mimetype:text/html"],
            "limit": max_results, "from": "20080101", "collapse": "urlkey"
        }, timeout=15)
        rows = r.json() if r.status_code == 200 else []

        # Strategy 2: If few results, try text search via cdx
        if len(rows) <= 2:
            r2 = requests.get("http://web.archive.org/cdx/search/cdx", params={
                "url": "*", "output": "json", "limit": max_results,
                "fl": "timestamp,original", "from": "20080101",
                "filter": f"original:.*{query.split()[0].lower()}.*"
            }, timeout=15)
            try:
                rows2 = r2.json()
                rows = rows + rows2[1:]
            except Exception:
                pass

        for row in rows[1:]:
            if len(row) >= 2:
                ts, orig = row[0], row[1]
                try:
                    dt = datetime.strptime(ts[:8], "%Y%m%d")
                    results.append({
                        "url": f"https://web.archive.org/web/{ts}/{orig}",
                        "original_url": orig,
                        "date": dt.strftime("%Y-%m-%d"),
                        "timestamp": ts,
                        "source": "wayback"
                    })
                except Exception:
                    continue
        results.sort(key=lambda x: x["timestamp"])
        cache_set(ck, results)
    except Exception as e:
        print(f"[Wayback] {e}")
    return results

def ddg_search(query: str) -> list[dict]:
    ck = f"ddg_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        r = requests.get("https://api.duckduckgo.com/", params={
            "q": query, "format": "json", "no_redirect": "1",
            "no_html": "1", "skip_disambig": "1"
        }, headers={"User-Agent": "DisInfoTracer-OSS/1.0"}, timeout=10)
        data = r.json()
        for item in data.get("RelatedTopics", [])[:6]:
            if "FirstURL" in item and item.get("FirstURL"):
                results.append({
                    "url": item["FirstURL"], "original_url": item["FirstURL"],
                    "date": "unknown", "timestamp": "00000000000000",
                    "snippet": item.get("Text", ""), "source": "duckduckgo"
                })
        if data.get("AbstractURL"):
            results.append({
                "url": data["AbstractURL"], "original_url": data["AbstractURL"],
                "date": "unknown", "timestamp": "00000000000000",
                "snippet": data.get("Abstract", ""), "source": "duckduckgo"
            })
        cache_set(ck, results)
    except Exception as e:
        print(f"[DDG] {e}")
    return results

def ddg_web_search(query: str, max_results: int = 8) -> list[dict]:
    """DuckDuckGo HTML results parser for generic web links."""
    ck = f"ddgweb_{hashlib.md5((query + str(max_results)).encode()).hexdigest()}"
    if c := cache_get(ck):
        return c

    results = []
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a.result__a")[:max_results]:
            href = (a.get("href") or "").strip()
            if not href:
                continue

            # DuckDuckGo wraps outbound links in /l/?uddg=... redirect URLs.
            if "duckduckgo.com/l/?" in href and "uddg=" in href:
                try:
                    qs = parse_qs(urlparse(href).query)
                    href = unquote(qs.get("uddg", [href])[0])
                except Exception:
                    pass

            results.append({
                "url": href,
                "original_url": href,
                "date": "unknown",
                "timestamp": "99999999999999",
                "snippet": a.get_text(" ", strip=True),
                "source": "ddg_web",
            })

        cache_set(ck, results)
    except Exception as e:
        print(f"[DDGWeb] {e}")
    return results

def commoncrawl_search(query: str) -> list[dict]:
    ck = f"cc_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    indexes = ["CC-MAIN-2023-50", "CC-MAIN-2021-25", "CC-MAIN-2019-09", "CC-MAIN-2017-13"]
    try:
        for index in indexes[:2]:
            r = requests.get(
                f"https://index.commoncrawl.org/{index}-index",
                params={"url": f"*{query.replace(' ','+')}*", "output": "json", "limit": 5},
                timeout=12
            )
            for line in r.text.strip().split("\n"):
                if line.strip():
                    try:
                        item = json.loads(line)
                        if item.get("url"):
                            ts = item.get("timestamp", "20200101000000")
                            try:
                                dt = datetime.strptime(ts[:8], "%Y%m%d")
                                date_str = dt.strftime("%Y-%m-%d")
                            except Exception:
                                date_str = "unknown"
                            results.append({
                                "url": item["url"], "original_url": item["url"],
                                "date": date_str, "timestamp": ts,
                                "source": "commoncrawl"
                            })
                    except Exception:
                        continue
            time.sleep(0.4)
        results.sort(key=lambda x: x["timestamp"])
        cache_set(ck, results)
    except Exception as e:
        print(f"[CommonCrawl] {e}")
    return results

def bing_news_free(query: str) -> list[dict]:
    """Scrape Bing News without API key — HTML scraping."""
    ck = f"bing_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        r = requests.get("https://www.bing.com/news/search", params={
            "q": query, "format": "rss"
        }, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        }, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item")[:6]:
            link = item.find("link")
            pubdate = item.find("pubdate")
            if link:
                url = link.text.strip() if link.text else ""
                date = "unknown"
                if pubdate:
                    try:
                        dt = datetime.strptime(pubdate.text[:16], "%a, %d %b %Y")
                        date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                if url:
                    results.append({
                        "url": url, "original_url": url,
                        "date": date, "timestamp": date.replace("-","") + "000000",
                        "source": "bing_news"
                    })
        cache_set(ck, results)
    except Exception as e:
        print(f"[BingNews] {e}")
    return results

def reddit_search(query: str) -> list[dict]:
    """Search Reddit discussions via web search."""
    ck = f"reddit_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        for item in ddg_web_search(f"site:reddit.com {query}", max_results=6):
            item["source"] = "reddit"
            results.append(item)
        cache_set(ck, results)
    except Exception as e:
        print(f"[Reddit] {e}")
    return results

def google_scholar_search(query: str) -> list[dict]:
    """Search Google Scholar for academic and credible sources."""
    ck = f"scholar_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        for item in ddg_web_search(f"site:scholar.google.com {query}", max_results=4):
            item["source"] = "google_scholar"
            results.append(item)
        cache_set(ck, results)
    except Exception as e:
        print(f"[Google Scholar] {e}")
    return results

def archive_is_search(query: str) -> list[dict]:
    """Search Archive.is (Archivetoday) for alternative archives."""
    ck = f"archiveo_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        for item in ddg_web_search(f"site:archive.is OR site:archive.today {query}", max_results=5):
            item["source"] = "archive_is"
            results.append(item)
        cache_set(ck, results)
    except Exception as e:
        print(f"[Archive.is] {e}")
    return results

def twitter_search(query: str) -> list[dict]:
    """Search Twitter/X discussions via DuckDuckGo."""
    ck = f"twitter_{hashlib.md5(query.encode()).hexdigest()}"
    if c := cache_get(ck): return c

    results = []
    try:
        for item in ddg_web_search(f"site:twitter.com OR site:x.com {query}", max_results=6):
            item["source"] = "twitter"
            results.append(item)
        cache_set(ck, results)
    except Exception as e:
        print(f"[Twitter] {e}")
    return results

def scrape_url(url: str) -> str:
    try:
        html = trafilatura.fetch_url(url)
        if html:
            text = trafilatura.extract(html, include_comments=False, include_tables=False)
            return text or ""
    except Exception:
        pass
    # Fallback: BeautifulSoup
    try:
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception:
        return ""

# ─── Mutation chain ───────────────────────────────────────────────────────────
def score_evidence(hit: dict) -> dict:
    analysis = hit.get("analysis", {})
    rel = max(0.0, min(1.0, float(analysis.get("relevance_score", 0)) / 10.0))
    cred = RELIABILITY_PRIOR.get(analysis.get("credibility_signals", "unknown"), 0.42)
    src = SOURCE_BASE_PRIOR.get(hit.get("source", ""), 0.5)
    tprior = time_prior(hit.get("timestamp", ""))

    score = 0.55 * rel + 0.25 * cred + 0.10 * src + 0.10 * tprior
    score = round(max(0.0, min(1.0, score)), 3)

    why = (
        f"semantic={rel:.2f}, reliability={cred:.2f}, source_prior={src:.2f}, "
        f"time_prior={tprior:.2f}"
    )
    return {
        "evidence_score": score,
        "semantic_score": round(rel, 3),
        "reliability_prior": round(cred, 3),
        "source_prior": round(src, 3),
        "time_prior": round(tprior, 3),
        "why_this_source": why,
    }

def pick_earliest_high_confidence(hits: list) -> Optional[dict]:
    if not hits:
        return None
    filtered = [h for h in hits if h.get("evidence", {}).get("evidence_score", 0) >= 0.58]
    if not filtered:
        return None
    filtered.sort(key=lambda x: (x.get("timestamp", "99999999999999"), -x.get("evidence", {}).get("evidence_score", 0)))
    return filtered[0]

def assign_mutation_clusters(hits: list, sim_threshold: float = 0.84) -> list[dict]:
    ordered = sorted(hits, key=lambda x: x.get("timestamp", "99999999999999"))
    centroids = []
    clustered = []

    for hit in ordered:
        snippet = (hit.get("analysis", {}).get("version_of_claim") or hit.get("text_snippet") or "")[:500]
        if not snippet.strip():
            hit["cluster_id"] = len(centroids) + 1
            v = embed(hit.get("claim", "") + " " + hit.get("url", ""))
            centroids.append(v)
            clustered.append(hit)
            continue

        vec = embed(snippet)
        best_idx = -1
        best_sim = -1.0
        for i, c in enumerate(centroids):
            s = cosine_sim(vec, c)
            if s > best_sim:
                best_sim = s
                best_idx = i

        if best_idx >= 0 and best_sim >= sim_threshold:
            hit["cluster_id"] = best_idx + 1
            centroids[best_idx] = (np.array(centroids[best_idx]) + np.array(vec)) / 2.0
        else:
            centroids.append(vec)
            hit["cluster_id"] = len(centroids)
        clustered.append(hit)

    return clustered

def build_mutation_chain(hits: list) -> list:
    verified = [h for h in hits if h.get("analysis", {}).get("contains_claim")]
    verified = assign_mutation_clusters(verified)
    verified.sort(key=lambda x: x.get("timestamp", "99999999999999"))
    chain = []
    prev_version = None
    prev_cluster = None
    for i, hit in enumerate(verified[:10]):
        version = hit.get("analysis", {}).get("version_of_claim")
        cluster_id = hit.get("cluster_id")
        chain.append({
            "step": i + 1,
            "url": hit["url"],
            "date": hit["date"],
            "source_type": hit.get("analysis", {}).get("source_type", "unknown"),
            "version": version,
            "cluster_id": cluster_id,
            "changed_from_prev": bool((version and prev_version and version != prev_version) or (prev_cluster and cluster_id != prev_cluster)),
            "credibility": hit.get("analysis", {}).get("credibility_signals", "unknown"),
            "relevance": hit.get("analysis", {}).get("relevance_score", 0),
            "evidence_score": hit.get("evidence", {}).get("evidence_score", 0),
            "why_this_source": hit.get("evidence", {}).get("why_this_source", ""),
        })
        if version:
            prev_version = version
        prev_cluster = cluster_id
    return chain

# ─── API ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="DisInfoTracer OSS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TraceRequest(BaseModel):
    claim: str

@app.get("/status")
async def status():
    ollama_ok = ollama_available()
    return {
        "ollama": ollama_ok,
        "ollama_model": OLLAMA_MODEL if ollama_ok else None,
        "embedder": "all-MiniLM-L6-v2",
        "mode": "ollama+embeddings" if ollama_ok else "embeddings+rules",
        "free_apis": ["wayback_cdx", "duckduckgo", "commoncrawl", "bing_news_rss", 
                      "reddit", "twitter", "archive_is", "google_scholar"]
    }

@app.post("/trace")
async def trace_claim(req: TraceRequest):
    if not req.claim.strip():
        raise HTTPException(400, "Claim cannot be empty")

    claim = req.claim.strip()
    features = claim_features(claim)
    cleaned_claim = features["cleaned_claim"]
    trace_id = hashlib.md5(f"{claim}{time.time()}".encode()).hexdigest()[:12]

    # Step 1: Decompose
    queries = build_query_variants(cleaned_claim, features)
    print(f"[Trace] Queries: {queries}")

    # Step 2: Search all sources (with fallback chain)
    all_hits, seen_urls, seen_domains = [], set(), set()
    source_counter = {}

    def add_hit(hit: dict):
        url = hit.get("original_url") or hit.get("url") or ""
        canon = canonicalize_url(url)
        dom = domain_of(canon)
        if not canon:
            return
        # Deduplicate by canonical URL and soft-dedupe by domain density.
        if canon in seen_urls:
            return
        if dom in seen_domains and len([h for h in all_hits if h.get("domain") == dom]) >= 3:
            return
        seen_urls.add(canon)
        if dom:
            seen_domains.add(dom)
        hit["url"] = canon
        hit["original_url"] = canon
        hit["domain"] = dom
        if hit.get("date") == "unknown":
            hit["timestamp"] = hit.get("timestamp") or "99999999999999"
        hit["date"] = hit.get("date") or timestamp_to_date(hit.get("timestamp", ""))
        source = hit.get("source", "unknown")
        source_counter[source] = source_counter.get(source, 0) + 1
        all_hits.append(hit)

    for query in queries[:4]:
        # Primary searches (fast, reliable)
        for hit in ddg_search(query):
            add_hit(hit)
        for hit in ddg_web_search(query, max_results=8):
            add_hit(hit)
        
        # Archive searches (with short timeout tolerance)
        for hit in wayback_search(query, max_results=6):
            add_hit(hit)
        
        # Fallback searches (when primary sources timeout)
        for hit in reddit_search(query):
            add_hit(hit)
        
        for hit in twitter_search(query):
            add_hit(hit)
        
        # Try academic sources
        for hit in google_scholar_search(query):
            add_hit(hit)
        
        # Alternative archives
        for hit in archive_is_search(query):
            add_hit(hit)
        
        # Try Common Crawl with timeout protection
        try:
            for hit in commoncrawl_search(query):
                add_hit(hit)
        except Exception as e:
            print(f"[Trace] Common Crawl timeout, continuing with other sources: {e}")
        
        for hit in bing_news_free(query):
            add_hit(hit)
        
        time.sleep(0.1)  # Reduce sleep time since we have fallbacks

    all_hits.sort(key=lambda x: x.get("timestamp", "99999999999999"))
    candidates = all_hits[:24]
    print(f"[Trace] {len(candidates)} candidates to verify")

    # Step 3: Scrape + verify with embeddings
    verified_hits = []
    for hit in candidates:
        text = scrape_url(hit["url"])
        analysis = llm_verify(cleaned_claim, text, hit["url"], hit["date"])
        hit["text_snippet"] = text[:300] if text else ""
        hit["analysis"] = analysis
        hit["claim"] = cleaned_claim
        hit["evidence"] = score_evidence(hit)
        if analysis.get("relevance_score", 0) >= 2.5:
            verified_hits.append(hit)
        time.sleep(0.15)

    verified_hits.sort(key=lambda x: (x.get("timestamp", "99999999999999"), -x.get("evidence", {}).get("evidence_score", 0)))
    print(f"[Trace] {len(verified_hits)} verified hits")

    # Step 4: Origin analysis
    origin = llm_origin_summary(cleaned_claim, verified_hits)
    mutation_chain = build_mutation_chain(verified_hits)
    earliest_best = pick_earliest_high_confidence(verified_hits)

    timeline = [{
        "date": h["date"], "url": h["url"], "source": h["source"],
        "domain": h.get("domain", ""),
        "source_type": h.get("analysis", {}).get("source_type", "unknown"),
        "relevance": h.get("analysis", {}).get("relevance_score", 0),
        "credibility": h.get("analysis", {}).get("credibility_signals", "unknown"),
        "snippet": h.get("text_snippet", "")[:200],
        "evidence_score": h.get("evidence", {}).get("evidence_score", 0),
        "why_this_source": h.get("evidence", {}).get("why_this_source", ""),
        "cluster_id": h.get("cluster_id"),
    } for h in verified_hits[:15]]

    earliest = earliest_best
    if not earliest and origin.get("confidence") != "high":
        origin["origin_type"] = "unclear"
        origin["confidence"] = "low"
        origin["narrative"] = "No high-confidence evidence node was found. The claim remains unresolved with available open-web sources."

    result = {
        "trace_id": trace_id,
        "claim": claim,
        "cleaned_claim": cleaned_claim,
        "claim_features": features,
        "queries": queries,
        "retrieval_stats": {
            "sources_scanned": source_counter,
            "candidate_count": len(candidates),
            "verified_count": len(verified_hits),
            "unique_domains": len({h.get("domain", "") for h in all_hits if h.get("domain")}),
        },
        "hits": timeline,
        "earliest": {
            "url": earliest["url"], "date": earliest["date"],
            "source": earliest["source"],
            "snippet": earliest.get("text_snippet", "")[:400],
            "analysis": earliest.get("analysis", {}),
            "evidence": earliest.get("evidence", {}),
            "why_this_source": earliest.get("evidence", {}).get("why_this_source", ""),
        } if earliest else None,
        "origin_analysis": origin,
        "mutation_chain": mutation_chain,
        "timeline": timeline,
        "llm_mode": "ollama" if ollama_available() else "embeddings+rules",
        "hackathon_plan": {
            "day1": [
                "Implement retrieval adapters across search, archives, social, and news",
                "Canonical URL/domain deduplication",
                "Evidence scoring (semantic + reliability + source prior + time prior)",
                "Timeline API with earliest high-confidence node selection"
            ]
        }
    }

    db = get_db()
    db.execute("INSERT OR REPLACE INTO traces VALUES (?,?,?,?)",
               (trace_id, claim, json.dumps(result), time.time()))
    db.commit()
    return result

@app.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    db = get_db()
    row = db.execute("SELECT result FROM traces WHERE id=?", (trace_id,)).fetchone()
    if not row: raise HTTPException(404, "Trace not found")
    return json.loads(row[0])

@app.get("/")
async def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    print("[Startup] Initializing embedder…")
    get_embedder()
    print(f"[Startup] Embedder mode: {'TF-IDF (offline)' if _USE_TFIDF else 'sentence-transformers'}")
    print(f"[Startup] Ollama: {'✓ available (' + OLLAMA_MODEL + ')' if ollama_available() else '✗ not found — using embeddings+rules fallback'}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
