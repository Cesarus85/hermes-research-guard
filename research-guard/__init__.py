"""Research Guard plugin for Hermes.

When a local/small model is used for factual/general-knowledge questions, this
plugin performs a lightweight web search before the LLM call and injects compact
source context into the user message.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

CACHE_PATH = Path.home() / ".hermes" / "cache" / "research-guard-cache.json"
DEFAULT_LOCAL_MODEL_PATTERNS = (
    "qwen", "ollama", "llama", "mistral", "gemma", "phi", "deepseek",
    "yi-", "codellama", "local", "lmstudio", "mlx", "gguf",
)

QUESTION_RE = re.compile(
    r"\b(wer|was|wann|wo|warum|wie|welche|welcher|welches|wieviel|wie viel|"
    r"who|what|when|where|why|how|which|compare|vergleich|unterschied|"
    r"aktuell|current|latest|neueste|version|release|stimmt es|is it true)\b",
    re.IGNORECASE,
)
SKIP_RE = re.compile(
    r"\b(schreib|formuliere|übersetze|translate|rewrite|korrigiere|code|"
    r"python|javascript|typescript|regex|sql|datei|file|ordner|folder|"
    r"git|commit|diff|log|terminal|ssh|server|meine|mein|unser|unsere|"
    r"erinnerung|kalender|todo|notiz|memory|vorhin|gesagt)\b",
    re.IGNORECASE,
)
CURRENT_RE = re.compile(
    r"\b(aktuell|heute|jetzt|derzeit|neueste|latest|current|news|202[4-9]|"
    r"version|release|preis|price|ceo|präsident|president|minister)\b",
    re.IGNORECASE,
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(name, str(default)))))
    except Exception:
        return default


def _is_local_or_small_model(model: str | None) -> bool:
    if not model:
        return False
    if not _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True):
        return True
    patterns = os.getenv("RESEARCH_GUARD_LOCAL_PATTERNS")
    needles = tuple(p.strip().lower() for p in patterns.split(",")) if patterns else DEFAULT_LOCAL_MODEL_PATTERNS
    m = str(model).lower()
    return any(p and p in m for p in needles)


def _should_research(message: str) -> tuple[bool, str]:
    text = (message or "").strip()
    if not text:
        return False, "empty"
    lowered = text.lower()
    if "#no-research" in lowered or "/no-research" in lowered:
        return False, "opt-out"
    if "#research" in lowered or "/research" in lowered:
        return True, "explicit"
    if len(text) < 12:
        return False, "too-short"
    if SKIP_RE.search(text) and not CURRENT_RE.search(text):
        return False, "looks-local-or-writing-coding"
    if CURRENT_RE.search(text):
        return True, "current-facts"
    if QUESTION_RE.search(text) and text.endswith(("?", "？")):
        return True, "factual-question"
    if QUESTION_RE.search(text) and len(text) < 220:
        return True, "general-knowledge"
    return False, "no-trigger"


def _load_cache() -> dict[str, Any]:
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Could not read research cache", exc_info=True)
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        items = sorted(cache.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)[:200]
        CACHE_PATH.write_text(json.dumps(dict(items), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.debug("Could not write research cache", exc_info=True)


def _clean_duckduckgo_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return url


def _strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _duckduckgo_search(query: str, limit: int) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Hermes Research Guard/0.1)"})
    with urlopen(req, timeout=_env_int("RESEARCH_GUARD_TIMEOUT", 8, 2, 20)) as resp:
        body = resp.read(250_000).decode("utf-8", "ignore")

    results: list[dict[str, str]] = []
    # DuckDuckGo HTML keeps result title/snippet in predictable classes. Use a
    # tolerant pairwise parser rather than assuming exact block nesting.
    title_matches = list(re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.S))
    for idx, match in enumerate(title_matches):
        start = match.end()
        end = title_matches[idx + 1].start() if idx + 1 < len(title_matches) else min(len(body), start + 5000)
        block = body[start:end]
        href = _clean_duckduckgo_url(html.unescape(match.group(1)))
        title = _strip_tags(match.group(2))
        snip_m = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, flags=re.S)
        snippet = _strip_tags(snip_m.group(1)) if snip_m else ""
        if title and href:
            results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def _search(query: str, limit: int) -> dict[str, Any]:
    cache_ttl = _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400)
    key = f"{limit}:{query.strip().lower()}"
    cache = _load_cache()
    now = time.time()
    if cache_ttl and key in cache and now - float(cache[key].get("ts", 0)) < cache_ttl:
        payload = dict(cache[key]["payload"])
        payload["cached"] = True
        return payload

    errors: list[str] = []
    try:
        from tools.web_tools import web_search_tool
        raw = web_search_tool(query, limit=limit)
        data = json.loads(raw)
        if data.get("success") and data.get("data", {}).get("web"):
            results = []
            for item in data["data"]["web"][:limit]:
                results.append({
                    "title": item.get("title") or item.get("name") or "Untitled",
                    "url": item.get("url") or item.get("link") or "",
                    "snippet": item.get("description") or item.get("snippet") or "",
                })
            payload = {"success": True, "provider": "hermes-web", "query": query, "results": results, "cached": False}
            cache[key] = {"ts": now, "payload": payload}
            _save_cache(cache)
            return payload
        if isinstance(data, dict) and data.get("error"):
            errors.append(str(data.get("error")))
    except Exception as exc:
        errors.append(f"hermes-web: {exc}")

    try:
        results = _duckduckgo_search(query, limit)
        payload = {"success": bool(results), "provider": "duckduckgo-html", "query": query, "results": results, "cached": False}
        if not results:
            payload["error"] = "No search results parsed"
        if errors:
            payload["fallback_errors"] = errors[-2:]
        cache[key] = {"ts": now, "payload": payload}
        _save_cache(cache)
        return payload
    except Exception as exc:
        return {"success": False, "provider": "none", "query": query, "results": [], "error": str(exc), "fallback_errors": errors[-2:]}


def _format_context(payload: dict[str, Any], reason: str, model: str | None) -> str:
    if not payload.get("success"):
        return ""
    lines = [
        "[Research Guard: automatische Webrecherche vor Antwort]",
        f"Auslöser: {reason}; Modell: {model or 'unknown'}; Provider: {payload.get('provider')}; Query: {payload.get('query')}",
        "Nutze die Quellen unten für faktische Aussagen. Wenn sie nicht reichen oder widersprüchlich sind, sag das klar. Erfinde keine Details.",
        "",
        "Quellen:",
    ]
    max_results = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    for idx, item in enumerate(payload.get("results", [])[:max_results], 1):
        title = item.get("title", "Untitled")[:180]
        url = item.get("url", "")[:240]
        snippet = item.get("snippet", "")[:500]
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Auszug: {snippet}")
    return "\n".join(lines)


def research_guard_search(args: dict, **kwargs) -> str:
    """Manual tool: run the same research search used by the hook."""
    del kwargs
    query = str(args.get("query") or "").strip()
    limit = int(args.get("limit") or _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10))
    if not query:
        return json.dumps({"error": "query is required"}, ensure_ascii=False)
    return json.dumps(_search(query, max(1, min(limit, 10))), ensure_ascii=False, indent=2)


def pre_llm_research_guard(session_id: str, user_message: str, model: str, platform: str, **kwargs):
    del session_id, platform, kwargs
    if not _env_bool("RESEARCH_GUARD_ENABLED", True):
        return None
    if not _is_local_or_small_model(model):
        return None
    should, reason = _should_research(user_message)
    if not should:
        return None
    limit = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    payload = _search(user_message, limit)
    context = _format_context(payload, reason, model)
    if not context:
        logger.info("research-guard search skipped/failed: %s", payload.get("error"))
        return None
    return {"context": context}


TOOL_SCHEMA = {
    "name": "research_guard_search",
    "description": "Run a lightweight web search and return compact source metadata. Useful for checking factual/general-knowledge claims before answering.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results, 1-10", "default": 5},
        },
        "required": ["query"],
    },
}


def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_research_guard)
    ctx.register_tool(
        name="research_guard_search",
        toolset="research_guard",
        schema=TOOL_SCHEMA,
        handler=research_guard_search,
        emoji="🛡️",
        max_result_size_chars=50_000,
    )
