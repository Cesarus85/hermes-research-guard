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

__version__ = "0.5.1"
CACHE_PATH = Path.home() / ".hermes" / "cache" / "research-guard-cache.json"
MAX_DECISIONS = 30
DECISIONS: list[dict[str, Any]] = []
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
DEFAULT_LOCAL_MODEL_PATTERNS = (
    "qwen", "ollama", "llama", "mistral", "gemma", "phi", "deepseek",
    "yi-", "codellama", "local", "lmstudio", "mlx", "gguf", "vllm", "tgi",
    "kimi-k2", "minimax-m2",
)
LOCAL_PROVIDER_PATTERNS = (
    "ollama", "lmstudio", "lm-studio", "mlx", "llama.cpp", "local",
    "vllm", "tgi", "goliath",
)
CLOUD_PROVIDER_PATTERNS = (
    "openai", "openai-codex", "anthropic", "gemini", "google", "openrouter",
    "perplexity", "moonshot", "kimi", "minimax", "synthetic", "zai",
)
CLOUD_MODEL_PATTERNS = (
    "gpt-", "claude", "sonnet", "opus", "haiku", "gemini", "openrouter",
    "anthropic", "openai", "moonshot", "perplexity",
)
EXPLICIT_CLOUD_MODEL_MARKERS = (":cloud",)

RESEARCH_PREFIX_RE = re.compile(r"^\s*(?:#|/)research\b\s*", re.IGNORECASE)
NO_RESEARCH_PREFIX_RE = re.compile(r"^\s*(?:#|/)no-research\b\s*", re.IGNORECASE)
SLASH_COMMAND_RE = re.compile(r"^\s*/(?!research\b|no-research\b)\S+", re.IGNORECASE)
SOURCE_FOLLOWUP_RE = re.compile(
    r"\b(woher|wo hast du|wo habt ihr|quelle|quellen|beleg|belege|"
    r"info her|information her|zustande|recherchiert|gesucht|research[-_\s]*guard|"
    r"source|sources|where.*source|how.*answer)\b",
    re.IGNORECASE,
)
CONTEXT_FOLLOWUP_RE = re.compile(
    r"^\s*(?:"
    r"was\s+hältst\s+du\s+(?:davon|darüber|dazu)"
    r"|was\s+sagst\s+du\s+(?:dazu|darüber|davon)"
    r"|wie\s+findest\s+du\s+(?:das|es|die\s+sache)"
    r"|was\s+meinst\s+du(?:\s+(?:dazu|darüber|davon))?"
    r"|deine\s+meinung(?:\s+(?:dazu|darüber|davon))?"
    r"|was\s+ist\s+deine\s+meinung(?:\s+(?:dazu|darüber|davon))?"
    r"|what\s+do\s+you\s+think(?:\s+(?:about\s+(?:it|that|this)))?"
    r"|thoughts(?:\s+(?:on\s+(?:it|that|this)))?"
    r"|your\s+opinion(?:\s+(?:on\s+(?:it|that|this)))?"
    r")\s*[?.!]*\s*$",
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


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    items = [_normalize_hostname(part) for part in value.split(",")]
    return [item for item in items if item]


def _is_local_or_small_model(model: str | None, provider: str | None = None) -> bool:
    provider_text = str(provider or "").lower()
    bare_model = str(model or "").lower()
    combined = f"{provider_text} {bare_model}".strip()
    if not combined:
        return False
    if not _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True):
        return True
    patterns = os.getenv("RESEARCH_GUARD_LOCAL_PATTERNS")
    needles = tuple(p.strip().lower() for p in patterns.split(",")) if patterns else DEFAULT_LOCAL_MODEL_PATTERNS
    if any(marker in bare_model for marker in EXPLICIT_CLOUD_MODEL_MARKERS):
        return False
    if any(pattern in provider_text for pattern in LOCAL_PROVIDER_PATTERNS):
        return True
    if any(pattern in provider_text for pattern in CLOUD_PROVIDER_PATTERNS):
        return False
    if any(p and p in combined for p in needles):
        return True
    if any(pattern in combined for pattern in CLOUD_MODEL_PATTERNS):
        return False
    return "/" not in bare_model and 0 < len(bare_model) < 24


def _should_skip_for_model_gate(model: str | None, provider: str | None, should_research: bool, reason: str) -> bool:
    if not _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True):
        return False
    if _is_local_or_small_model(model, provider):
        return False
    if reason == "explicit":
        return False
    if _env_bool("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS", False) and should_research:
        return False
    return True


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


def _build_search_query(message: str, messages: list[Any] | None = None) -> str:
    text = _clean_message_for_research(message)
    text = RESEARCH_PREFIX_RE.sub("", text)
    text = NO_RESEARCH_PREFIX_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    subject = _extract_prior_subject(messages, cleaned)
    return f"{subject} {cleaned}".strip()[:240] if subject else cleaned[:240]


def _is_subject_followup(message: str) -> bool:
    return bool(re.search(
        r"\b(es|sie|er|ihn|ihm|dort|da|dazu|davon|darüber|darueber|hierzu|damit|danach|später|spaeter|"
        r"it|there|this|that|about\s+(?:it|that|this))\b",
        message,
        flags=re.IGNORECASE,
    ))


def _message_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    content = message.get("content") or message.get("text") or message.get("prompt") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return " ".join(parts)
    return ""


def _message_role(message: Any) -> str | None:
    if isinstance(message, dict) and isinstance(message.get("role"), str):
        return message["role"].lower()
    return None


def _trim_subject(value: str) -> str | None:
    subject = re.sub(r"[?!.:,;]+$", "", value)
    subject = re.sub(r"\b(und|oder|and|or|mit|in|im|am|an|bei|hat|ist|liegt)\b[\s\S]*$", "", subject, flags=re.IGNORECASE)
    subject = subject.strip()
    return subject if len(subject) >= 3 else None


def _extract_subject_from_text(text: str) -> str | None:
    cleaned = re.sub(r"[#/](no-)?research\b", " ", text, flags=re.IGNORECASE)
    patterns = [
        r"\b(?:bürgermeister|oberbürgermeister|landrat|mayor)\s+(?:von|in|for)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})",
        r"\b(?:wer\s+oder\s+was|who\s+or\s+what)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,4})\s+(?:ist|war|is|was)\b",
        r"\b(?:wer|was|who|what)\s+(?:ist|war|is|was)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,4})",
        r"\b(?:wo liegt|wo ist|wo befindet sich|where is)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            subject = _trim_subject(match.group(1))
            if subject:
                return subject
    match = re.search(r"\b([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})\b", cleaned)
    return _trim_subject(match.group(1)) if match else None


def _extract_prior_subject(messages: list[Any] | None, prompt: str) -> str | None:
    if not messages or not _is_subject_followup(prompt):
        return None
    candidates = list(reversed(messages))
    for message in candidates:
        if _message_role(message) != "user":
            continue
        text = _message_text(message)
        if not text or text.strip() == prompt.strip():
            continue
        subject = _extract_subject_from_text(text)
        if subject:
            return subject
    for message in candidates:
        text = _message_text(message)
        if not text or text.strip() == prompt.strip():
            continue
        subject = _extract_subject_from_text(text)
        if subject:
            return subject
    return None


def _query_debug(message: str, messages: list[Any] | None = None) -> dict[str, Any]:
    cleaned = _clean_message_for_research(message)
    stripped = RESEARCH_PREFIX_RE.sub("", cleaned)
    stripped = NO_RESEARCH_PREFIX_RE.sub("", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    carried_subject = _extract_prior_subject(messages, stripped)
    final_query = f"{carried_subject} {stripped}".strip()[:240] if carried_subject else stripped[:240]
    return {
        "original_preview": _redact_prompt_preview(message),
        "cleaned_prompt": _redact_prompt_preview(stripped, 240),
        "carried_subject": carried_subject,
        "final_query": final_query,
        "history_available": bool(messages),
    }


def _is_source_followup(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text:
        return False
    return bool(SOURCE_FOLLOWUP_RE.search(text))


def _is_context_followup(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text or len(text) > 140:
        return False
    return bool(CONTEXT_FOLLOWUP_RE.match(text))


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
    if _is_context_followup(text):
        return False, "context-followup"
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
    if "prompt" in details:
        details["prompt_preview"] = _redact_prompt_preview(str(details.pop("prompt") or ""))
    if isinstance(details.get("query_debug"), dict):
        details["query_debug"] = _redact_query_debug(details["query_debug"])
    decision = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "reason": reason,
        **details,
    }
    DECISIONS.append(decision)
    del DECISIONS[:-MAX_DECISIONS]
    return decision


def _redact_prompt_preview(text: str, limit: int = 180) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text or "")
    value = re.sub(r"\b(?:\+?\d[\d\s()./-]{7,}\d)\b", "[redacted-phone]", value)
    value = re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "[redacted-token]", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _redact_query_debug(value: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(value)
    for key in ("original_preview", "cleaned_prompt", "final_query"):
        if redacted.get(key) is not None:
            redacted[key] = _redact_prompt_preview(str(redacted[key]), 240)
    return redacted


def _decision_category(decision: dict[str, Any]) -> str:
    action = decision.get("action")
    reason = str(decision.get("reason") or "")
    if action == "injected":
        return "researched_and_injected"
    if action == "manual_search":
        return "manual_research"
    if action == "failed" and ("confidence" in reason or "quality" in reason or "usable" in reason):
        return "researched_but_not_injected"
    if action == "failed":
        return "failed"
    if action == "skipped":
        return "checked_and_skipped"
    return str(action or "unknown")


def _visible_effect(decision: dict[str, Any]) -> str:
    action = decision.get("action")
    if action == "injected":
        return "sources_injected"
    if action == "manual_search":
        return "manual_tool_result"
    if action == "failed":
        return "error_or_no_context"
    return "none"


def _diagnose_decision(decision: dict[str, Any]) -> dict[str, Any]:
    diagnostic = dict(decision)
    diagnostic["category"] = _decision_category(decision)
    diagnostic["visible_effect"] = _visible_effect(decision)
    evidence = [f"action={decision.get('action')}", f"reason={decision.get('reason')}"]
    for field, label in (
        ("provider", "provider"),
        ("query", "query"),
        ("confidence", "confidence"),
        ("score", "score"),
        ("usable_result_count", "usable"),
        ("blocked_result_count", "blocked"),
        ("evidence_diversity", "diversity"),
        ("cached", "cache"),
        ("cache_key", "cacheKey"),
        ("model", "model"),
        ("provider_gate", "providerGate"),
    ):
        if field in decision and decision.get(field) is not None:
            evidence.append(f"{label}={decision.get(field)}")
    diagnostic["evidence"] = evidence
    return diagnostic


def _recent_decisions(limit: int = 5) -> list[dict[str, Any]]:
    limit = max(1, min(20, int(limit or 5)))
    return list(reversed(DECISIONS[-limit:]))


def _last_research_decision() -> dict[str, Any] | None:
    for decision in reversed(DECISIONS):
        if decision.get("action") in {"injected", "manual_search"}:
            return decision
    return None


def _source_summaries(results: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in results[:limit]:
        summary = {
            "title": str(item.get("title") or "Untitled")[:180],
            "url": str(item.get("url") or "")[:300],
            "snippet": str(item.get("snippet") or "")[:300],
        }
        quality = item.get("quality")
        if isinstance(quality, dict):
            summary["quality"] = {
                "score": quality.get("score"),
                "confidence": quality.get("confidence"),
                "domain": quality.get("domain"),
                "signals": quality.get("signals") or [],
                "warnings": quality.get("warnings") or [],
            }
        summaries.append(summary)
    return summaries


def _normalize_hostname(value: str) -> str:
    return (
        value.lower()
        .replace("https://", "")
        .replace("http://", "")
        .removeprefix("www.")
        .split("/")[0]
        .strip()
    )


def _domain_matches_any(domain: str, candidates: list[str]) -> bool:
    return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)


def _confidence_from_score(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _parse_confidence(value: str | None, default: str = "low") -> str:
    value = (value or "").strip().lower()
    return value if value in CONFIDENCE_RANK else default


def _meets_min_confidence(confidence: str, minimum: str) -> bool:
    return CONFIDENCE_RANK.get(confidence, 1) >= CONFIDENCE_RANK.get(minimum, 1)


def _source_site_key(domain: str) -> str:
    parts = [part for part in domain.split(".") if part]
    if len(parts) <= 2:
        return domain
    last_two = ".".join(parts[-2:])
    last_three = ".".join(parts[-3:])
    if re.match(r"^(co|com|gov|ac|org|net)\.[a-z]{2}$", last_two, flags=re.IGNORECASE):
        return last_three
    return last_two


def _canonical_source_key(value: str) -> str:
    try:
        parsed = urlparse(value)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
    except Exception:
        return value.strip().rstrip("/").lower()


def _content_signature(item: dict[str, Any]) -> str:
    text = f"{item.get('title') or ''} {item.get('snippet') or ''}".lower()
    text = re.sub(r"\b(?:the|a|an|und|oder|der|die|das|ein|eine|von|zu|im|in|am|auf|for|with|about)\b", " ", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split()[:12])


def _is_government_domain(domain: str) -> bool:
    return (
        domain.endswith(".gov")
        or domain.endswith(".gov.uk")
        or domain.endswith(".gov.au")
        or domain.endswith(".gouv.fr")
        or domain.endswith(".bund.de")
        or domain.endswith(".deutschland.de")
        or ".bund." in f".{domain}."
        or ".bundesregierung." in f".{domain}."
    )


def _is_forum_or_social_domain(domain: str) -> bool:
    return _domain_matches_any(domain, [
        "reddit.com", "quora.com", "stackoverflow.com", "stackexchange.com",
        "x.com", "twitter.com", "facebook.com", "instagram.com", "tiktok.com",
    ])


def _is_weak_aggregator_domain(domain: str, text: str) -> bool:
    if re.search(r"\b(scraper|mirror|download free|apk|alternatives? to|top alternatives)\b", text, flags=re.IGNORECASE):
        return True
    return _domain_matches_any(domain, [
        "softonic.com", "alternativeto.net", "filehippo.com", "uptodown.com",
        "justwatch.com", "bild.de",
    ])


def _is_documentation_source(domain: str, text: str) -> bool:
    return (
        bool(re.search(r"(^|\.)docs?\.|(^|\.)developer\.|(^|\.)dev\.|(^|\.)api\.|(^|\.)learn\.", domain))
        or bool(re.search(r"\b(documentation|docs|api reference|developer guide|changelog|release notes?)\b", text, flags=re.IGNORECASE))
    )


def _is_primary_project_source(domain: str, text: str) -> bool:
    return (
        domain in {"github.com", "gitlab.com", "npmjs.com", "pypi.org"}
        or bool(re.search(r"\b(official|offiziell|project page|homepage)\b", text, flags=re.IGNORECASE))
    )


def _is_municipal_source(domain: str, text: str, query: str) -> bool:
    local_fact_query = re.search(
        r"\b(bürgermeister|oberbürgermeister|landrat|einwohner|einwohnerzahl|bevölkerung|rathaus|gemeinde|stadt|landkreis|mayor|population)\b",
        query,
        flags=re.IGNORECASE,
    )
    if not local_fact_query or _is_forum_or_social_domain(domain) or _is_weak_aggregator_domain(domain, text):
        return False
    return bool(re.search(r"\b(stadt|gemeinde|landkreis|rathaus|verwaltung|official city|city hall|municipal|bürgermeister|oberbürgermeister)\b", text, flags=re.IGNORECASE))


def _is_vendor_or_project_source(domain: str, text: str, query: str) -> bool:
    software_query = re.search(r"\b(release|changelog|version|pricing|preise|preis|available|verfügbar|docs?|api|software|package|npm|pypi)\b", query, flags=re.IGNORECASE)
    if not software_query or _is_weak_aggregator_domain(domain, text) or _is_forum_or_social_domain(domain):
        return False
    return _is_documentation_source(domain, text) or _is_primary_project_source(domain, text) or bool(
        re.search(r"\b(official|offiziell|vendor|pricing|release notes?|changelog|documentation|download)\b", text, flags=re.IGNORECASE)
    )


def _is_freshness_sensitive_query(query: str) -> bool:
    return bool(re.search(
        r"\b(aktuell|aktuelle|heute|neuigkeiten|news|latest|recent|update|release|changelog|version|preis|preise|pricing|verfügbar|bürgermeister|oberbürgermeister|landrat|präsident|ministerpräsident|mayor|president|prime minister|einwohner|einwohnerzahl|bevölkerung|population)\b",
        query,
        flags=re.IGNORECASE,
    ))


def _parse_source_date(value: str | None) -> datetime | None:
    if not value:
        return None
    numeric = re.search(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", value)
    if numeric:
        return datetime(int(numeric.group(1)), int(numeric.group(2)), int(numeric.group(3)), tzinfo=timezone.utc)
    german = re.search(r"\b(0?[1-9]|[12]\d|3[01])\.\s*(0?[1-9]|1[0-2])\.\s*(20\d{2})\b", value)
    if german:
        return datetime(int(german.group(3)), int(german.group(2)), int(german.group(1)), tzinfo=timezone.utc)
    return None


def _score_freshness(item: dict[str, Any], text: str) -> tuple[int, list[str], list[str]]:
    published_at = _parse_source_date(str(item.get("age") or "")) or _parse_source_date(text)
    if not published_at:
        return -8, [], ["Undated source for current-information query."]
    age_days = max(0, int((datetime.now(timezone.utc) - published_at).total_seconds() // 86_400))
    if age_days <= 120:
        return 12, ["fresh-source"], []
    if age_days <= 548:
        return 5, ["recent-source"], []
    return -14, [], ["Possibly stale source for current-information query."]


def _score_research_result(item: dict[str, Any], query: str, preferred_domains: list[str], blocked_domains: list[str]) -> dict[str, Any]:
    signals: list[str] = []
    warnings: list[str] = []
    url = str(item.get("url") or "")
    parsed = urlparse(url)
    domain = _normalize_hostname(parsed.netloc)
    if not parsed.scheme.startswith("http") or not domain:
        return {"score": 0, "confidence": "low", "domain": domain or "invalid-url", "signals": ["invalid-url"], "warnings": ["Invalid or unsupported source URL."]}
    if _domain_matches_any(domain, blocked_domains):
        return {"score": 0, "confidence": "low", "domain": domain, "signals": ["blocked-domain"], "warnings": [f"Blocked domain: {domain}."]}

    text = f"{item.get('title') or ''} {item.get('snippet') or ''}".lower()
    score = 50
    if _domain_matches_any(domain, preferred_domains):
        score += 35
        signals.append("preferred-domain")
    if _is_government_domain(domain):
        score += 25
        signals.append("government-source")
    if _is_municipal_source(domain, text, query):
        score += 24
        signals.append("municipal-source")
    if _is_documentation_source(domain, text):
        score += 20
        signals.append("documentation-source")
    if _is_primary_project_source(domain, text):
        score += 15
        signals.append("primary-project-source")
    if _is_vendor_or_project_source(domain, text, query):
        score += 14
        signals.append("vendor-source")
    if domain.endswith("wikipedia.org") or domain.endswith("wikidata.org"):
        score += 15 if domain.endswith("wikidata.org") else 10
        signals.append("reference-source")
    if re.search(r"\b(official|offiziell|official site|homepage|documentation|docs|changelog|release notes?|pricing|preise)\b", text, flags=re.IGNORECASE):
        score += 8
        signals.append("official-context")

    if not str(item.get("snippet") or "").strip():
        score -= 8
        warnings.append("Missing snippet.")
    if _is_forum_or_social_domain(domain):
        score -= 18
        warnings.append("Forum or social source.")
    if _is_weak_aggregator_domain(domain, text):
        score -= 20
        warnings.append("Likely aggregator or SEO-heavy source.")
    if re.search(r"\b(subscribe|subscription|paywall|sign in to continue|members only|premium)\b", text, flags=re.IGNORECASE):
        score -= 15
        warnings.append("Possible paywall or snippet-only source.")
    if re.search(r"\b(top\s+\d+|best\b|coupon|deals?|buy now|vergleich der besten|testsieger)\b", text, flags=re.IGNORECASE):
        score -= 12
        warnings.append("Commercial or listicle-style source.")
    if _is_freshness_sensitive_query(query):
        delta, fresh_signals, fresh_warnings = _score_freshness(item, text)
        score += delta
        signals.extend(fresh_signals)
        warnings.extend(fresh_warnings)

    score = max(1, min(100, round(score)))
    return {
        "score": score,
        "confidence": _confidence_from_score(score),
        "domain": domain,
        "signals": sorted(set(signals)),
        "warnings": sorted(set(warnings)),
    }


def _score_research_results(results: list[dict[str, Any]], query: str) -> dict[str, Any]:
    preferred_domains = _env_list("RESEARCH_GUARD_PREFERRED_DOMAINS")
    blocked_domains = _env_list("RESEARCH_GUARD_BLOCKED_DOMAINS")
    scored = []
    blocked = []
    for item in results:
        quality = _score_research_result(item, query, preferred_domains, blocked_domains)
        result = {**item, "quality": quality}
        if quality["score"] <= 0:
            blocked.append(result)
        else:
            scored.append(result)

    canonical_urls: set[str] = set()
    signatures: set[str] = set()
    site_counts: dict[str, int] = {}
    duplicate_count = 0
    for result in scored:
        quality = dict(result["quality"])
        penalty = 0
        canonical = _canonical_source_key(str(result.get("url") or ""))
        signature = _content_signature(result)
        site = _source_site_key(str(quality.get("domain") or ""))
        if canonical in canonical_urls:
            penalty += 45
            duplicate_count += 1
            quality["signals"].append("duplicate-source")
            quality["warnings"].append("Duplicate source URL.")
        else:
            canonical_urls.add(canonical)
        if signature and signature in signatures:
            penalty += 28
            duplicate_count += 1
            quality["signals"].append("near-duplicate-source")
            quality["warnings"].append("Likely duplicate title or snippet.")
        elif signature:
            signatures.add(signature)
        same_site_count = site_counts.get(site, 0)
        if same_site_count > 0:
            penalty += min(30, 12 * same_site_count)
            quality["signals"].append("same-domain-duplicate")
            quality["warnings"].append("Additional source from the same domain.")
        site_counts[site] = same_site_count + 1
        if penalty:
            quality["score"] = max(1, quality["score"] - penalty)
            quality["confidence"] = _confidence_from_score(quality["score"])
        quality["signals"] = sorted(set(quality["signals"]))
        quality["warnings"] = sorted(set(quality["warnings"]))
        result["quality"] = quality

    usable = sorted(scored, key=lambda item: item["quality"]["score"], reverse=True)
    top_scores = [item["quality"]["score"] for item in usable[:3]]
    score = round(sum(top_scores) / len(top_scores)) if top_scores else 0
    unique_domain_count = len(site_counts)
    evidence_diversity = "high" if unique_domain_count >= 3 and duplicate_count == 0 else "medium" if unique_domain_count >= 2 else "low"
    confidence = "high" if top_scores and top_scores[0] >= 80 and score >= 55 else _confidence_from_score(score)
    if evidence_diversity == "low" and confidence == "high":
        confidence = "medium"
    require_multiple = _env_bool("RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES", False)
    warnings = sorted(set(
        warning
        for result in [*usable, *blocked]
        for warning in result["quality"].get("warnings", [])
    ))
    if blocked:
        warnings.append(f"{len(blocked)} result(s) excluded by blocked-domain or invalid-source rules.")
    if not usable:
        warnings.append("No usable research sources passed quality scoring.")
        confidence = "low"
    if require_multiple and len(usable) < 2:
        warnings.append("Configuration requires multiple usable sources, but fewer than two passed quality scoring.")
        confidence = "low"
    if require_multiple and unique_domain_count < 2:
        warnings.append("Configuration requires multiple usable sources, but fewer than two unique source domains passed quality scoring.")
        confidence = "low"
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate or near-duplicate source signal(s) detected.")
    if len(usable) > 1 and unique_domain_count < 2:
        warnings.append("Low evidence diversity: usable sources come from fewer than two unique domains.")

    return {
        "confidence": confidence,
        "score": score,
        "warnings": sorted(set(warnings)),
        "result_count": len(results),
        "usable_result_count": len(usable),
        "blocked_result_count": len(blocked),
        "unique_domain_count": unique_domain_count,
        "duplicate_cluster_count": duplicate_count,
        "evidence_diversity": evidence_diversity,
        "results": usable,
    }


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


def _format_context_followup_context() -> str:
    decision = _last_research_decision()
    if not decision:
        return "\n".join([
            "[Research Guard: Kontext-Follow-up]",
            "Der Nutzer stellt eine kontextabhängige Anschlussfrage, vermutlich zum vorherigen Thema.",
            "Es liegt in diesem Hermes-Prozess keine gespeicherte Research-Guard-Recherche mit Quellen vor.",
            "Suche nicht nach dem Wortlaut der Anschlussfrage. Nutze nur den sichtbaren Gesprächskontext und behaupte keine neuen Webquellen.",
            "Wenn du eine Meinung formulierst, trenne sie klar von belegten Fakten.",
            "[/Research Guard: Kontext-Follow-up]",
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
        "[Research Guard: Kontext-Follow-up]",
        "Der Nutzer stellt eine kontextabhängige Anschlussfrage, wahrscheinlich zum vorherigen Research-Guard-Thema.",
        "Suche NICHT nach dem Wortlaut dieser Anschlussfrage und behaupte nicht, Research Guard habe danach gesucht.",
        "Wenn die Frage nach einer Meinung oder Einordnung fragt, antworte als Einordnung auf Basis des bisherigen Gesprächs.",
        "Trenne belegte Fakten aus den Quellen von deiner Bewertung. Erfinde keine zusätzlichen aktuellen Details.",
        f"Letzte Research-Guard-Aktion: {decision.get('action')}",
        f"Grund: {decision.get('reason')}",
        f"Provider: {decision.get('provider') or 'unknown'}",
        f"Query des vorherigen Themas: {decision.get('query') or 'unknown'}",
        "Quellen der letzten Research-Guard-Recherche:",
        *source_lines,
        "Antworte direkt auf die Anschlussfrage und nenne Quellen nur, wenn sie für Fakten in der Einordnung relevant sind.",
        "[/Research Guard: Kontext-Follow-up]",
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
    cache = _load_cache()
    now = time.time()
    def cache_key(provider: str) -> str:
        return f"provider={provider}:limit={limit}:deep=0:query={query.strip().lower()}"

    for provider in ("hermes-web", "duckduckgo-html"):
        key = cache_key(provider)
        if cache_ttl and key in cache and now - float(cache[key].get("ts", 0)) < cache_ttl:
            payload = dict(cache[key]["payload"])
            payload["cached"] = True
            payload["cache_key"] = key
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
            key = cache_key("hermes-web")
            payload = {"success": True, "provider": "hermes-web", "query": query, "results": results, "cached": False, "cache_key": key}
            cache[key] = {"ts": now, "payload": payload}
            _save_cache(cache)
            return payload
        if isinstance(data, dict) and data.get("error"):
            errors.append(str(data.get("error")))
    except Exception as exc:
        errors.append(f"hermes-web: {exc}")

    try:
        results = _duckduckgo_search(query, limit)
        key = cache_key("duckduckgo-html")
        payload = {"success": bool(results), "provider": "duckduckgo-html", "query": query, "results": results, "cached": False, "cache_key": key}
        if not results:
            payload["error"] = "No search results parsed"
        if errors:
            payload["fallback_errors"] = errors[-2:]
        cache[key] = {"ts": now, "payload": payload}
        _save_cache(cache)
        return payload
    except Exception as exc:
        return {"success": False, "provider": "none", "query": query, "results": [], "error": str(exc), "fallback_errors": errors[-2:]}


def _format_context(payload: dict[str, Any], reason: str, model: str | None, quality: dict[str, Any] | None = None, current_prompt: str | None = None) -> str:
    if not payload.get("success"):
        return ""
    results = quality.get("results") if quality else payload.get("results", [])
    if quality and not results:
        return ""
    lines = [
        "[Research Guard: automatische Webrecherche vor Antwort]",
        f"Auslöser: {reason}; Modell: {model or 'unknown'}; Provider: {payload.get('provider')}; Query: {payload.get('query')}",
        "Diese Quellen wurden automatisch durch Research Guard für die aktuelle Nutzerfrage recherchiert.",
        "Beantworte ausschließlich die aktuelle Nutzerfrage. Wiederhole keine frühere Antwort, außer der Nutzer fordert das ausdrücklich.",
        "Nutze die Quellen unten für faktische Aussagen. Antworte nicht nur aus Trainingswissen, wenn diese Quellen passen.",
        "Wenn der Nutzer später fragt, woher die Info stammt oder wie die Antwort zustande kam, nenne Research Guard und die URLs aus diesem Kontext.",
        "Beachte die Quellenbewertung. Bei niedriger Confidence antworte vorsichtig und markiere Unsicherheit ausdrücklich.",
        "Wenn die Quellen nicht reichen oder widersprüchlich sind, sag das klar. Erfinde keine Details oder Quellen.",
        "Füge keine unaufgeforderten Zusatzfakten hinzu. Bei Ortsfragen wie `Wo liegt ...?` nenne keine Flüsse, Verkehrsachsen, Einwohnerzahlen oder Entfernungen, außer sie wurden gefragt und stehen ausdrücklich in den Quellen.",
        "Füge am Ende eine kurze Zeile `Quellen (Research Guard): <URL 1>, <URL 2>` an, außer der Nutzer verlangt ausdrücklich keine Quellen.",
    ]
    if quality:
        lines.append(
            "Quellenbewertung: "
            f"{quality.get('confidence')} ({quality.get('score')}/100, "
            f"{quality.get('usable_result_count')}/{quality.get('result_count')} nutzbare Quelle(n), "
            f"Quellenvielfalt: {quality.get('evidence_diversity')}, "
            f"{quality.get('unique_domain_count')} Domain(s), "
            f"{quality.get('duplicate_cluster_count')} Duplicate-Hinweis(e))."
        )
        if quality.get("warnings"):
            lines.append(f"Bewertungshinweise: {' '.join(quality.get('warnings') or [])}")
    if current_prompt:
        lines.append(f"Aktuelle Nutzerfrage: {current_prompt}")
    lines.extend(["", "Quellen:"])
    max_results = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    for idx, item in enumerate(results[:max_results], 1):
        title = item.get("title", "Untitled")[:180]
        url = item.get("url", "")[:240]
        snippet = item.get("snippet", "")[:500]
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Auszug: {snippet}")
        item_quality = item.get("quality") or {}
        if item_quality:
            signals = ", ".join(item_quality.get("signals") or [])
            warnings = " ".join(item_quality.get("warnings") or [])
            signal_text = f"; {signals}" if signals else ""
            warning_text = f"; Warnung: {warnings}" if warnings else ""
            lines.append(
                "   Qualität: "
                f"{item_quality.get('confidence')} ({item_quality.get('score')}/100; "
                f"{item_quality.get('domain')}{signal_text}{warning_text})"
            )
    return "\n".join(lines)


def _conversation_history_from_kwargs(kwargs: dict[str, Any]) -> list[Any] | None:
    for key in ("conversation_history", "messages", "history"):
        value = kwargs.get(key)
        if isinstance(value, list):
            return value
    return None


def _provider_from_context(platform: str | None, kwargs: dict[str, Any]) -> str | None:
    for key in ("provider", "provider_id", "providerId", "model_provider"):
        value = kwargs.get(key)
        if value:
            return str(value)
    return platform


def _cache_stats() -> dict[str, Any]:
    cache = _load_cache()
    now = time.time()
    provider_counts: dict[str, int] = {}
    valid_entries = 0
    expired_entries = 0
    for key, item in cache.items():
        provider = "unknown"
        match = re.search(r"(?:^|:)provider=([^:]+)", key)
        if match:
            provider = match.group(1)
        else:
            payload = item.get("payload") if isinstance(item, dict) else {}
            if isinstance(payload, dict):
                provider = str(payload.get("provider") or "unknown")
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        ts = float(item.get("ts", 0)) if isinstance(item, dict) else 0
        ttl = _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400)
        if ttl and now - ts < ttl:
            valid_entries += 1
        else:
            expired_entries += 1
    return {
        "entries": len(cache),
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "ttl_seconds": _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400),
        "provider_counts": provider_counts,
        "path": str(CACHE_PATH),
    }


def _config_snapshot() -> dict[str, Any]:
    return {
        "enabled": _env_bool("RESEARCH_GUARD_ENABLED", True),
        "only_local": _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True),
        "allow_cloud_research_triggers": _env_bool("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS", False),
        "max_results": _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10),
        "min_confidence": _parse_confidence(os.getenv("RESEARCH_GUARD_MIN_CONFIDENCE"), "low"),
        "require_multiple_sources": _env_bool("RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES", False),
        "preferred_domains": _env_list("RESEARCH_GUARD_PREFERRED_DOMAINS"),
        "blocked_domains": _env_list("RESEARCH_GUARD_BLOCKED_DOMAINS"),
    }


def research_guard_search(args: dict, **kwargs) -> str:
    """Manual tool: run the same research search used by the hook."""
    del kwargs
    query = str(args.get("query") or "").strip()
    limit = int(args.get("limit") or _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10))
    if not query:
        return json.dumps({"error": "query is required"}, ensure_ascii=False)
    payload = _search(query, max(1, min(limit, 10)))
    quality = _score_research_results(payload.get("results") or [], str(payload.get("query") or query)) if payload.get("success") else None
    if quality:
        payload = {**payload, "results": quality["results"], "quality": quality}
    _record_decision(
        "manual_search",
        "manual research_guard_search tool call",
        provider=payload.get("provider"),
        query=payload.get("query") or query,
        success=bool(payload.get("success")),
        confidence=quality.get("confidence") if quality else None,
        score=quality.get("score") if quality else None,
        usable_result_count=quality.get("usable_result_count") if quality else None,
        blocked_result_count=quality.get("blocked_result_count") if quality else None,
        evidence_diversity=quality.get("evidence_diversity") if quality else None,
        cache_key=payload.get("cache_key"),
        cached=payload.get("cached"),
        sources=_source_summaries(payload.get("results") or []),
        error=payload.get("error"),
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def research_guard_status(args: dict, **kwargs) -> str:
    """Manual tool: show recent Research Guard decisions."""
    del kwargs
    limit = int(args.get("limit") or 5)
    decisions = [_diagnose_decision(decision) for decision in _recent_decisions(limit)]
    categories: dict[str, int] = {}
    for decision in decisions:
        category = str(decision.get("category") or "unknown")
        categories[category] = categories.get(category, 0) + 1
    return json.dumps(
        {
            "plugin": "research-guard",
            "status_version": 2,
            "config": _config_snapshot(),
            "cache": _cache_stats(),
            "categories": categories,
            "decisions": decisions,
            "diagnostics": {
                "decision_fields": [
                    "category", "visible_effect", "evidence", "query_debug",
                    "confidence", "score", "usable_result_count", "blocked_result_count",
                    "evidence_diversity", "warnings",
                ],
                "prompt_preview_redaction": "emails, phone-like values, and long token-like strings are redacted",
            },
            "note": (
                "Injected Research Guard context is ephemeral in Hermes. "
                "Use this status to explain whether the previous factual answer used Research Guard sources."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def pre_llm_research_guard(session_id: str, user_message: str, model: str, platform: str, **kwargs):
    del session_id
    provider = _provider_from_context(platform, kwargs)
    messages = _conversation_history_from_kwargs(kwargs)
    query_debug = _query_debug(user_message, messages)
    if not _env_bool("RESEARCH_GUARD_ENABLED", True):
        _record_decision("skipped", "plugin disabled", model=model, provider=provider, query_debug=query_debug)
        return None
    should, reason = _should_research(user_message)
    if _should_skip_for_model_gate(model, provider, should, reason):
        _record_decision(
            "skipped",
            "non-local model gate",
            model=model,
            provider=provider,
            provider_gate={
                "only_local": _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True),
                "allow_cloud_research_triggers": _env_bool("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS", False),
                "classification": {"should_research": should, "reason": reason},
            },
            query_debug=query_debug,
            prompt=_clean_message_for_research(user_message)[:180],
        )
        return None
    if reason == "source-followup":
        return {"context": _format_source_followup_context()}
    if reason == "context-followup":
        return {"context": _format_context_followup_context()}
    if not should:
        _record_decision("skipped", reason, model=model, provider=provider, query_debug=query_debug, prompt=_clean_message_for_research(user_message)[:180])
        return None
    query = str(query_debug.get("final_query") or _build_search_query(user_message, messages))
    if not query:
        _record_decision("skipped", "empty query after cleanup", model=model, provider=provider, query_debug=query_debug)
        return None
    limit = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    payload = _search(query, limit)
    quality = _score_research_results(payload.get("results") or [], str(payload.get("query") or query)) if payload.get("success") else None
    min_confidence = _parse_confidence(os.getenv("RESEARCH_GUARD_MIN_CONFIDENCE"), "low")
    if quality and not _meets_min_confidence(str(quality.get("confidence") or "low"), min_confidence):
        _record_decision(
            "failed",
            f"confidence {quality.get('confidence')} below configured minimum {min_confidence}",
            model=model,
            provider=payload.get("provider"),
            query=payload.get("query") or query,
            query_debug=query_debug,
            confidence=quality.get("confidence"),
            score=quality.get("score"),
            usable_result_count=quality.get("usable_result_count"),
            blocked_result_count=quality.get("blocked_result_count"),
            evidence_diversity=quality.get("evidence_diversity"),
            warnings=quality.get("warnings"),
            cache_key=payload.get("cache_key"),
            cached=payload.get("cached"),
        )
        return None
    context = _format_context(payload, reason, model, quality, _clean_message_for_research(user_message))
    if not context:
        _record_decision(
            "failed",
            "search failed or returned no injectable context",
            model=model,
            provider=payload.get("provider"),
            query=payload.get("query") or query,
            query_debug=query_debug,
            confidence=quality.get("confidence") if quality else None,
            score=quality.get("score") if quality else None,
            usable_result_count=quality.get("usable_result_count") if quality else None,
            blocked_result_count=quality.get("blocked_result_count") if quality else None,
            cache_key=payload.get("cache_key"),
            cached=payload.get("cached"),
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
        query_debug=query_debug,
        cached=payload.get("cached"),
        cache_key=payload.get("cache_key"),
        confidence=quality.get("confidence") if quality else None,
        score=quality.get("score") if quality else None,
        usable_result_count=quality.get("usable_result_count") if quality else None,
        blocked_result_count=quality.get("blocked_result_count") if quality else None,
        evidence_diversity=quality.get("evidence_diversity") if quality else None,
        warnings=quality.get("warnings") if quality else None,
        sources=_source_summaries(quality.get("results") if quality else payload.get("results") or []),
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
    "description": "Show recent Research Guard diagnostics only: decisions, categories, visible effects, query debug, source quality, config snapshot, and cache stats. Use this when the user asks where a factual answer came from or why Research Guard did or did not run; do not answer the prior factual question from this tool alone.",
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
