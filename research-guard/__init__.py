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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

CACHE_PATH = Path.home() / ".hermes" / "cache" / "research-guard-cache.json"
MAX_DECISIONS = 30
DECISIONS: list[dict[str, Any]] = []
DEFAULT_LOCAL_MODEL_PATTERNS = (
    "qwen", "ollama", "llama", "mistral", "gemma", "phi", "deepseek",
    "yi-", "codellama", "local", "lmstudio", "mlx", "gguf",
)

RESEARCH_PREFIX_RE = re.compile(r"^\s*(?:#|/)research\b\s*", re.IGNORECASE)
NO_RESEARCH_PREFIX_RE = re.compile(r"^\s*(?:#|/)no-research\b\s*", re.IGNORECASE)
SLASH_COMMAND_RE = re.compile(r"^\s*/(?!research\b|no-research\b)\S+", re.IGNORECASE)
SOURCE_FOLLOWUP_RE = re.compile(
    r"\b(woher|wo hast du|wo habt ihr|quelle|quellen|beleg|belege|"
    r"info her|information her|zustande|recherchiert|gesucht|research[-_\s]*guard|"
    r"source|sources|where.*source|how.*answer)\b",
    re.IGNORECASE,
)

QUESTION_RE = re.compile(
    r"\b(wer|was|wann|wo|warum|wie|welche|welcher|welches|wieviel|wie viel|"
    r"who|what|when|where|why|how|which|compare|vergleich|unterschied|"
    r"aktuell|current|latest|neueste|version|release|stimmt es|is it true|"
    r"bürgermeister|oberbürgermeister|landrat|präsident|president|minister)\b",
    re.IGNORECASE,
)
LOCAL_OR_PRIVATE_RE = re.compile(
    r"\b(schreib|formuliere|übersetze|translate|rewrite|korrigiere|code|"
    r"python|javascript|typescript|regex|sql|datei|file|ordner|folder|"
    r"workspace|repo|repository|git|commit|diff|log|terminal|shell|bash|zsh|"
    r"meine|mein|unser|unsere|kalender|todo|notiz|memory|erinner|vorhin|"
    r"vorher|gesagt|erwähnt|persönlich|bei mir|meine mails)\b",
    re.IGNORECASE,
)
CURRENT_RE = re.compile(
    r"\b(aktuell|heute|jetzt|derzeit|neueste|latest|current|news|202[4-9]|"
    r"version|release|preis|price|ceo|präsident|president|minister)\b",
    re.IGNORECASE,
)
LOCAL_INFRA_RE = re.compile(
    r"\b(zugriff|verbindung|connect|verbinden|erreichbar|erreichen|ping|pingen|ssh)\s+"
    r"(?:auf|zu|mit)\b"
    r"|\b(?:hast du|haben wir|kannst du|kommst du|besteht|gibt es)\b[\s\S]*\b"
    r"(zugriff|verbindung|connect|verbinden|erreichbar|erreichen|ping|pingen|ssh)\b"
    r"|\b(status|zustand|health)\b[\s\S]*\b(verbindung|server|host|dienst|service|ssh|ping)\b"
    r"|\bwie\s+(?:ist|is|sind)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9_-]{2,}\s+"
    r"(?:erreichbar|verbunden|angebunden|zugänglich|zugaenglich)\b"
    r"|\bwie\s+(?:erreiche|erreichen|komme|kommen|connecte|verbinde)\s+"
    r"(?:ich|wir|du)?\s*(?:auf|zu|mit)?\s*[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9_-]{2,}\b"
    r"|\b(?:ip|ip-adresse|adresse|host|hostname|server|port|tailscale|tailscale-ip|lan|lokal|local)\b"
    r"[\s\S]{0,80}\b(?:von|zu|auf|für|fuer|mit)\b"
    r"|\b(?:wie|was|welche|welcher|welches|wie lautet|wie ist|wie is)\b"
    r"[\s\S]{0,80}\b(?:ip|ip-adresse|adresse|host|hostname|server|port|tailscale|tailscale-ip|lan|lokal|local)\b"
    r"|\b(?:ip|ip-adresse|adresse|host|hostname|server|port|tailscale|tailscale-ip)\b"
    r"[\s\S]{0,40}\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9_-]{2,}\b",
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


def _strip_speech_wrapper(text: str) -> str:
    current = text.strip()
    for _ in range(3):
        next_text = re.sub(
            r'^\s*(?:audio|voice|speech|stt|transcript|transkript|sprachnachricht)\s*[:：-]\s*["“”„]*([\s\S]*?)["“”„]*\s*$',
            r"\1",
            current,
            flags=re.IGNORECASE,
        )
        next_text = re.sub(
            r'^\s*(?:audio|voice|speech|stt|transcript|transkript|sprachnachricht)\s+'
            r'(?:message|nachricht|input)\s*[:：-]\s*["“”„]*([\s\S]*?)["“”„]*\s*$',
            r"\1",
            next_text,
            flags=re.IGNORECASE,
        ).strip()
        if next_text == current:
            break
        current = next_text
    return current


def _clean_message_for_research(message: str) -> str:
    text = (message or "").strip()
    text = _strip_speech_wrapper(text)
    text = re.sub(r"\n\s*\[Research Guard:[\s\S]*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _build_search_query(message: str) -> str:
    text = _clean_message_for_research(message)
    text = RESEARCH_PREFIX_RE.sub("", text)
    text = NO_RESEARCH_PREFIX_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()[:240]


def _is_source_followup(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text:
        return False
    return bool(SOURCE_FOLLOWUP_RE.search(text))


def _should_research(message: str) -> tuple[bool, str]:
    text = _clean_message_for_research(message)
    if not text:
        return False, "empty"
    if NO_RESEARCH_PREFIX_RE.match(text):
        return False, "opt-out"
    if RESEARCH_PREFIX_RE.match(text):
        return True, "explicit"
    if _is_source_followup(text):
        return False, "source-followup"
    if SLASH_COMMAND_RE.match(text):
        return False, "slash-command"
    if len(text) < 12:
        return False, "too-short"
    if LOCAL_INFRA_RE.search(text):
        return False, "local-infrastructure"
    if LOCAL_OR_PRIVATE_RE.search(text) and not CURRENT_RE.search(text):
        return False, "looks-local-personal-writing-coding"
    if CURRENT_RE.search(text):
        return True, "current-facts"
    if QUESTION_RE.search(text) and text.endswith(("?", "？")):
        return True, "factual-question"
    if QUESTION_RE.search(text) and len(text) < 220:
        return True, "general-knowledge"
    return False, "no-trigger"


def _record_decision(action: str, reason: str, **details: Any) -> dict[str, Any]:
    decision = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "reason": reason,
        **details,
    }
    DECISIONS.append(decision)
    del DECISIONS[:-MAX_DECISIONS]
    return decision


def _recent_decisions(limit: int = 5) -> list[dict[str, Any]]:
    limit = max(1, min(20, int(limit or 5)))
    return list(reversed(DECISIONS[-limit:]))


def _last_research_decision() -> dict[str, Any] | None:
    for decision in reversed(DECISIONS):
        if decision.get("action") in {"injected", "manual_search"}:
            return decision
    return None


def _source_summaries(results: list[dict[str, Any]], limit: int = 5) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for item in results[:limit]:
        summaries.append({
            "title": str(item.get("title") or "Untitled")[:180],
            "url": str(item.get("url") or "")[:300],
            "snippet": str(item.get("snippet") or "")[:300],
        })
    return summaries


def _format_source_followup_context() -> str:
    decision = _last_research_decision()
    if not decision:
        return "\n".join([
            "[Research Guard: Quellenstatus]",
            "Der Nutzer fragt nach der Herkunft einer früheren Antwort.",
            "Es liegt in diesem Hermes-Prozess keine gespeicherte Research-Guard-Entscheidung mit Quellen vor.",
            "Antworte transparent, dass du keine Research-Guard-Quellen im aktuellen Statuspuffer findest. Behaupte keine neuen Webquellen.",
            "[/Research Guard: Quellenstatus]",
        ])

    source_lines = []
    for idx, item in enumerate(decision.get("sources") or [], 1):
        source_lines.append(f"{idx}. {item.get('title') or 'Untitled'}")
        source_lines.append(f"   URL: {item.get('url') or ''}")
        snippet = item.get("snippet")
        if snippet:
            source_lines.append(f"   Auszug: {snippet}")
    if not source_lines:
        source_lines.append("Keine Quellen im Statuspuffer gespeichert.")

    return "\n".join([
        "[Research Guard: Quellenstatus]",
        "Der Nutzer fragt nach der Herkunft oder den Quellen der vorherigen Antwort.",
        "Beantworte diese aktuelle Frage anhand dieses Research-Guard-Status. Suche nicht neu.",
        "Wenn action=injected oder manual_search ist, behaupte NICHT, die vorherige Antwort sei nur aus Trainingswissen entstanden.",
        f"Letzte Research-Guard-Aktion: {decision.get('action')}",
        f"Grund: {decision.get('reason')}",
        f"Provider: {decision.get('provider') or 'unknown'}",
        f"Query: {decision.get('query') or 'unknown'}",
        "Quellen der letzten Research-Guard-Recherche:",
        *source_lines,
        "Antworte kurz und nenne Research Guard sowie 1-2 passende URLs.",
        "[/Research Guard: Quellenstatus]",
    ])


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
        "Diese Quellen wurden automatisch durch Research Guard für die aktuelle Nutzerfrage recherchiert.",
        "Nutze die Quellen unten für faktische Aussagen. Antworte nicht nur aus Trainingswissen, wenn diese Quellen passen.",
        "Wenn der Nutzer später fragt, woher die Info stammt oder wie die Antwort zustande kam, nenne Research Guard und die URLs aus diesem Kontext.",
        "Wenn die Quellen nicht reichen oder widersprüchlich sind, sag das klar. Erfinde keine Details.",
        "Füge am Ende eine kurze Zeile `Quellen (Research Guard): <URL 1>, <URL 2>` an, außer der Nutzer verlangt ausdrücklich keine Quellen.",
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
    payload = _search(query, max(1, min(limit, 10)))
    _record_decision(
        "manual_search",
        "manual research_guard_search tool call",
        provider=payload.get("provider"),
        query=payload.get("query") or query,
        success=bool(payload.get("success")),
        sources=_source_summaries(payload.get("results") or []),
        error=payload.get("error"),
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def research_guard_status(args: dict, **kwargs) -> str:
    """Manual tool: show recent Research Guard decisions."""
    del kwargs
    limit = int(args.get("limit") or 5)
    return json.dumps(
        {
            "plugin": "research-guard",
            "decisions": _recent_decisions(limit),
            "note": (
                "Injected Research Guard context is ephemeral in Hermes. "
                "Use this status to explain whether the previous factual answer used Research Guard sources."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def pre_llm_research_guard(session_id: str, user_message: str, model: str, platform: str, **kwargs):
    del session_id, platform, kwargs
    if not _env_bool("RESEARCH_GUARD_ENABLED", True):
        _record_decision("skipped", "plugin disabled", model=model)
        return None
    if not _is_local_or_small_model(model):
        _record_decision("skipped", "non-local model gate", model=model)
        return None
    if _is_source_followup(user_message):
        return {"context": _format_source_followup_context()}
    should, reason = _should_research(user_message)
    if not should:
        _record_decision("skipped", reason, model=model, prompt=_clean_message_for_research(user_message)[:180])
        return None
    query = _build_search_query(user_message)
    if not query:
        _record_decision("skipped", "empty query after cleanup", model=model)
        return None
    limit = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    payload = _search(query, limit)
    context = _format_context(payload, reason, model)
    if not context:
        _record_decision(
            "failed",
            "search failed or returned no injectable context",
            model=model,
            provider=payload.get("provider"),
            query=payload.get("query") or query,
            error=payload.get("error"),
        )
        logger.info("research-guard search skipped/failed: %s", payload.get("error"))
        return None
    _record_decision(
        "injected",
        reason,
        model=model,
        provider=payload.get("provider"),
        query=payload.get("query") or query,
        cached=payload.get("cached"),
        sources=_source_summaries(payload.get("results") or []),
    )
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

STATUS_TOOL_SCHEMA = {
    "name": "research_guard_status",
    "description": "Show recent Research Guard decisions, including whether context was injected, the query, provider, and stored sources. Use this when the user asks where a factual answer came from or how it was produced.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max recent decisions, 1-20", "default": 5},
        },
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
    ctx.register_tool(
        name="research_guard_status",
        toolset="research_guard",
        schema=STATUS_TOOL_SCHEMA,
        handler=research_guard_status,
        emoji="🧭",
        max_result_size_chars=50_000,
    )
