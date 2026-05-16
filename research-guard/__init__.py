"""Research Guard plugin for Hermes.

When a local/small model is used for factual/general-knowledge questions, this
plugin performs a lightweight web search before the LLM call and injects compact
source context into the user message.
"""

from __future__ import annotations

import html
import importlib.util
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

__version__ = "0.7.3"
CACHE_PATH = Path.home() / ".hermes" / "cache" / "research-guard-cache.json"
MAX_DECISIONS = 30
DECISIONS: list[dict[str, Any]] = []
STATUS_RESPONSE_POLICY = {
    "mode": "diagnostics_only",
    "instruction": (
        "Answer only with Research Guard status and decision diagnostics. Do not repeat, continue, shorten, "
        "correct, or summarize the previous factual answer unless the user explicitly asks for that separately."
    ),
    "allowed_content": [
        "plugin status",
        "decision categories",
        "whether Research Guard searched, injected, skipped, or failed",
        "provider, query, confidence, cache, deep-fetch, source-quality signals, warnings",
    ],
    "disallowed_content": [
        "a fresh factual answer to the previous user question",
        "a summary of the previous assistant answer",
        "new web-search conclusions outside the returned status data",
    ],
}
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
PACKAGE_REGISTRY_DOMAINS = [
    "npmjs.com", "pypi.org", "crates.io", "rubygems.org", "packagist.org",
    "nuget.org", "central.sonatype.com", "repo.maven.apache.org",
    "plugins.gradle.org", "pub.dev",
]
STANDARDS_DOMAINS = [
    "w3.org", "whatwg.org", "ietf.org", "rfc-editor.org", "iso.org",
    "ecma-international.org", "khronos.org", "unicode.org", "owasp.org",
]
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
    r"info her|information her|zustande|recherchiert|gesucht|"
    r"source|sources|where.*source|how.*answer)\b",
    re.IGNORECASE,
)
STATUS_REQUEST_RE = re.compile(
    r"\b(?:research[-_\s]*guard|research_guard|guard)\b[\s\S]{0,80}"
    r"\b(?:status|diagnos(?:e|tik|tic|tics)?|debug|zustand|health)\b"
    r"|"
    r"\b(?:status|diagnos(?:e|tik|tic|tics)?|debug|zustand|health)\b[\s\S]{0,80}"
    r"\b(?:research[-_\s]*guard|research_guard|guard)\b"
    r"|"
    r"\bresearch_guard_(?:status|diagnostics)\b",
    re.IGNORECASE,
)
INTERNAL_NOTE_RE = re.compile(
    r"^\s*(?:"
    r"\[[^\]]*(?:note|model\s+switch|gateway|restart|system|internal|status)[^\]]*\]"
    r"|"
    r"(?:accomplished|completed|done|ok|ready)\s+\[[^\]]*(?:gateway|restart|note|system|internal)[^\]]*\]"
    r"|"
    r"(?:gateway|plugin|model)\s+(?:restart|switch|reload|note)\b"
    r")",
    re.IGNORECASE,
)
CONTEXT_FOLLOWUP_RE = re.compile(
    r"^\s*(?:"
    r"was\s+hältst\s+du\s+(?:davon|darüber|dazu)"
    r"|was\s+sagst\s+du\s+(?:dazu|darüber|davon)"
    r"|wie\s+findest\s+du\s+(?:das|es|die\s+sache)"
    r"|wie\s+ist\s+dein\s+eindruck\s+(?:davon|darüber|dazu|von\s+[\s\S]{1,80})"
    r"|welchen\s+eindruck\s+hast\s+du\s+(?:davon|darüber|dazu|von\s+[\s\S]{1,80})"
    r"|wie\s+wirkt\s+(?:das|es|die\s+sache|[\s\S]{1,80})\s+auf\s+dich"
    r"|was\s+meinst\s+du(?:\s+(?:dazu|darüber|davon))?"
    r"|was\s+hältst\s+du\s+von\s+(?:meiner|unserer|dieser|der)\s+heimatstadt"
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
    r"bürgermeister|oberbürgermeister|landrat|präsident|president|minister|"
    r"einwohner|einwohnerzahl|bevölkerung|population|preise|preis|pricing|changelog)\b",
    re.IGNORECASE,
)
FACTUAL_RISK_RE = re.compile(
    r"\b(bürgermeister|oberbürgermeister|landrat|präsident|president|ministerpräsident|"
    r"mayor|president|prime minister|einwohner|einwohnerzahl|bevölkerung|population|"
    r"release|version|changelog|release notes?|preis|preise|pricing|price|compare|vergleich|unterschied)\b",
    re.IGNORECASE,
)
LOCAL_OR_PRIVATE_RE = re.compile(
    r"\b(schreib|formuliere|übersetze|translate|rewrite|korrigiere|code|"
    r"python|javascript|typescript|regex|sql|datei|file|ordner|folder|"
    r"workspace|repo|repository|git|commit|diff|log|terminal|shell|bash|zsh|"
    r"mein(?:e|er|em|en|es)?|unser(?:e|er|em|en|es)?|kalender|todo|notiz|memory|erinner|vorhin|"
    r"vorher|gesagt|erwähnt|persönlich|bei mir|meine mails)\b",
    re.IGNORECASE,
)
CURRENT_RE = re.compile(
    r"\b(aktuell|heute|jetzt|derzeit|neueste|latest|current|news|202[4-9]|"
    r"version|release|preis|price|ceo|präsident|president|minister)\b",
    re.IGNORECASE,
)
DEEP_FETCH_RE = re.compile(
    r"\b(tracklist|trackliste|tracks?|songs?|songliste|titelliste|albumtitel|lyrics?|"
    r"tabelle|liste|auflistung|alle|vollständig|komplett|details?|detailliert|"
    r"release notes?|changelog|versionen|versions?|preise|pricing|benchmarks?|"
    r"einwohner|einwohnerzahl|bevölkerung|population)\b",
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


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    return value if value in allowed else default


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
    return _query_plan(message, messages)["final_query"]


def _query_plan(message: str, messages: list[Any] | None = None) -> dict[str, Any]:
    text = _clean_message_for_research(message)
    manual_research = bool(RESEARCH_PREFIX_RE.match(text))
    text = RESEARCH_PREFIX_RE.sub("", text)
    text = NO_RESEARCH_PREFIX_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    subject = _extract_prior_subject(messages, cleaned)
    base_query = f"{subject} {cleaned}".strip()[:240] if subject else cleaned[:240]
    if manual_research:
        rewritten_query, strategy = base_query, "manual-exact"
    else:
        rewritten_query, strategy = _rewrite_search_query(base_query)
    return {
        "cleaned_prompt": cleaned,
        "carried_subject": subject,
        "base_query": base_query,
        "final_query": rewritten_query[:240],
        "rewrite_strategy": strategy,
    }


def _dedupe_query_terms(value: str) -> str:
    words = []
    seen = set()
    for word in re.split(r"\s+", value.strip()):
        key = word.lower().strip(".,;:!?()[]{}\"'")
        if not key or key in seen:
            continue
        seen.add(key)
        words.append(word)
    return " ".join(words)


def _extract_query_subject(query: str) -> str:
    cleaned = re.sub(r"[?!.]+$", "", query or "").strip()
    patterns = [
        r"\b(?:von|in|for|of)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,4})",
        r"\b(?:version|release|changelog|pricing|preise|preis|cost|kosten|kostet)\s+(?:von|for|of)?\s*([A-ZÄÖÜA-Za-z0-9][\wÄÖÜäöüß.'+-]*(?:\s+[A-ZÄÖÜA-Za-z0-9][\wÄÖÜäöüß.'+-]*){0,4})",
        r"\b(?:was\s+kostet|what\s+does|how\s+much\s+is)\s+([A-ZÄÖÜA-Za-z0-9][\wÄÖÜäöüß.'+-]*(?:\s+[A-ZÄÖÜA-Za-z0-9][\wÄÖÜäöüß.'+-]*){0,5})",
        r"^([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            subject = _trim_subject(match.group(1))
            if subject:
                if subject.lower() in {"wer", "was", "wann", "wo", "wie", "welche", "welcher", "welches", "what", "who", "how"}:
                    continue
                return subject
    return cleaned[:120]


def _extract_local_fact_subject(query: str) -> str:
    cleaned = re.sub(r"[?!.]+$", "", query or "").strip()
    prefix = re.match(r"^(.+?)\s+(?:wie\s+viele|wieviele|wie\s+viel|einwohner|bevölkerung|population)\b", cleaned, flags=re.IGNORECASE)
    if prefix:
        subject = _trim_subject(prefix.group(1))
        if subject:
            return subject
    patterns = [
        r"^([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})\s+(?:wie|wieviel|wie viele|einwohner|bevölkerung|population)",
        r"\b(?:hat|haben|in|von|for|of)\s+([A-ZÄÖÜ][\wÄÖÜäöüß.'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.'-]*){0,3})",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            subject = _trim_subject(match.group(1))
            if subject:
                return subject
    return _extract_query_subject(cleaned)


def _rewrite_search_query(query: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", query or "").strip()
    cleaned = re.sub(r"[?？]+$", "", cleaned).strip()
    lower = cleaned.lower()
    if not cleaned:
        return "", "empty"
    subject = _extract_query_subject(cleaned)
    if re.search(r"\b(bürgermeister|oberbürgermeister|mayor|landrat)\b", lower):
        return _dedupe_query_terms(f"{subject} Bürgermeister Oberbürgermeister Rathaus offizielle Stadt Verwaltung"), "municipal-office"
    if re.search(r"\b(einwohner|einwohnerzahl|bevölkerung|population|inhabitants|residents)\b", lower):
        subject = _extract_local_fact_subject(cleaned)
        return _dedupe_query_terms(f"{subject} Einwohner Einwohnerzahl Bevölkerung Statistik offizielle Stadt"), "municipal-population"
    if re.search(r"\b(release notes?|changelog|änderungsprotokoll|aenderungsprotokoll)\b", lower):
        return _dedupe_query_terms(f"{subject} official changelog release notes"), "software-changelog"
    if re.search(r"\b(version|latest version|aktuelle version|neueste version|release)\b", lower):
        return _dedupe_query_terms(f"{subject} official latest version release notes"), "software-version"
    if re.search(r"\b(preis|preise|pricing|price|kosten|kostet|cost|subscription|abo)\b", lower):
        return _dedupe_query_terms(f"{subject} official pricing price"), "pricing"
    if re.search(r"\b(compare|vergleich|unterschied|difference|vs\b|versus)\b", lower):
        return _dedupe_query_terms(f"{cleaned} official comparison documentation"), "comparison"
    if re.search(r"\b(aktuell|aktuelle|current|latest|heute|derzeit)\b", lower):
        return _dedupe_query_terms(f"{cleaned} official current"), "current-official"
    return cleaned[:240], "none"


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
    plan = _query_plan(message, messages)
    return {
        "original_preview": _redact_prompt_preview(message),
        "cleaned_prompt": _redact_prompt_preview(str(plan.get("cleaned_prompt") or ""), 240),
        "carried_subject": plan.get("carried_subject"),
        "base_query": _redact_prompt_preview(str(plan.get("base_query") or ""), 240),
        "final_query": _redact_prompt_preview(str(plan.get("final_query") or ""), 240),
        "rewrite_strategy": plan.get("rewrite_strategy"),
        "history_available": bool(messages),
    }


def _is_source_followup(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text:
        return False
    if _is_status_request(text):
        return False
    return bool(SOURCE_FOLLOWUP_RE.search(text))


def _is_status_request(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text:
        return False
    return bool(STATUS_REQUEST_RE.search(text))


def _is_context_followup(message: str) -> bool:
    text = _clean_message_for_research(message)
    if not text or len(text) > 140:
        return False
    return bool(CONTEXT_FOLLOWUP_RE.match(text))


def _should_research(message: str) -> tuple[bool, str]:
    text = _clean_message_for_research(message)
    if not text:
        return False, "empty"
    mode = _env_choice("RESEARCH_GUARD_MODE", "balanced", {"conservative", "balanced", "aggressive"})
    if NO_RESEARCH_PREFIX_RE.match(text):
        return False, "opt-out"
    if RESEARCH_PREFIX_RE.match(text):
        return True, "explicit"
    if INTERNAL_NOTE_RE.search(text):
        return False, "internal-note"
    if _is_status_request(text):
        return False, "status-request"
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
    if mode == "conservative":
        if FACTUAL_RISK_RE.search(text) and (text.endswith(("?", "？")) or len(text) < 180):
            return True, "factual-risk"
        return False, "conservative-no-trigger"
    if QUESTION_RE.search(text) and text.endswith(("?", "？")):
        return True, "factual-question"
    if QUESTION_RE.search(text) and len(text) < 220:
        return True, "general-knowledge"
    if mode == "aggressive" and text.endswith(("?", "？")) and len(text) > 20:
        return True, "aggressive-question"
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
    for key in ("original_preview", "cleaned_prompt", "base_query", "final_query"):
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
    if action == "failed" and not decision.get("error") and _decision_was_searched(decision):
        return "researched_but_not_injected"
    if action == "failed":
        return "failed"
    if action == "skipped":
        return "checked_and_skipped"
    return str(action or "unknown")


def _decision_was_searched(decision: dict[str, Any]) -> bool:
    if decision.get("action") in {"injected", "manual_search"}:
        return True
    return bool(
        decision.get("query")
        and decision.get("provider")
        and any(decision.get(field) is not None for field in (
            "score", "usable_result_count", "blocked_result_count", "fetched_source_count", "cached", "cache_key",
        ))
    )


def _visible_effect(decision: dict[str, Any]) -> str:
    action = decision.get("action")
    if action == "injected":
        return "sources_injected"
    if action == "manual_search":
        return "manual_tool_result"
    if action == "failed":
        return "error" if decision.get("error") else "none"
    return "none"


def _provider_path(provider: str | None) -> str | None:
    if not provider:
        return None
    if provider == "hermes-web" or provider.startswith("hermes"):
        return f"Hermes Web Search -> {provider}"
    if provider == "web-search-plus":
        return "Hermes web_search_plus -> web-search-plus"
    return f"Research Guard direct fallback -> {provider}"


def _diagnostic_explanation(decision: dict[str, Any], category: str, searched: bool) -> str:
    action = decision.get("action")
    query = decision.get("query") or "the prompt"
    if category == "researched_and_injected":
        return f'Research Guard searched for "{query}" and injected source context before the model answered.'
    if category == "manual_research":
        return f'Research Guard was explicitly called as a manual search tool for "{query}".'
    if category == "researched_but_not_injected":
        return f'Research Guard searched for "{query}" but did not inject context because: {decision.get("reason")}.'
    if category == "failed":
        return f'Research Guard attempted to run and failed: {decision.get("error") or decision.get("reason")}.'
    if action == "skipped" or not searched:
        return f'Research Guard inspected the prompt and skipped research because: {decision.get("reason")}.'
    return f'Research Guard decision category: {category}.'


def _diagnose_decision(decision: dict[str, Any]) -> dict[str, Any]:
    diagnostic = dict(decision)
    category = _decision_category(decision)
    visible_effect = _visible_effect(decision)
    searched = _decision_was_searched(decision)
    manual_tool = decision.get("action") == "manual_search"
    failed = category == "failed"
    nested_diagnostic = {
        "guard_involved": True,
        "category": category,
        "visible_effect": visible_effect,
        "searched": searched,
        "injected_context": decision.get("action") == "injected",
        "manual_tool": manual_tool,
        "skipped": category in {"checked_and_skipped", "researched_but_not_injected"},
        "failed": failed,
        "provider_path": _provider_path(str(decision.get("provider") or "")) if decision.get("provider") else None,
        "explanation": _diagnostic_explanation(decision, category, searched),
    }
    diagnostic["category"] = category
    diagnostic["visible_effect"] = visible_effect
    evidence = [f"action={decision.get('action')}", f"reason={decision.get('reason')}"]
    for field, label in (
        ("provider", "provider"),
        ("provider_chain", "providerChain"),
        ("query", "query"),
        ("fetched_source_count", "fetched"),
        ("confidence", "confidence"),
        ("score", "score"),
        ("usable_result_count", "usable"),
        ("blocked_result_count", "blocked"),
        ("evidence_diversity", "diversity"),
        ("query_profiles", "queryProfiles"),
        ("source_profiles", "sourceProfiles"),
        ("cached", "cache"),
        ("cache_key", "cacheKey"),
        ("model", "model"),
        ("provider_gate", "providerGate"),
    ):
        if field in decision and decision.get(field) is not None:
            evidence.append(f"{label}={decision.get(field)}")
    diagnostic["evidence"] = evidence
    nested_diagnostic["evidence"] = evidence
    diagnostic["diagnostic"] = nested_diagnostic
    return diagnostic


def _summarize_decision_history(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "total": len(decisions),
        "sources_injected": 0,
        "manual_searches": 0,
        "searched_but_not_injected": 0,
        "checked_and_skipped": 0,
        "failed": 0,
    }
    for decision in decisions:
        category = str(decision.get("category") or "")
        if category == "researched_and_injected":
            counts["sources_injected"] += 1
        elif category == "manual_research":
            counts["manual_searches"] += 1
        elif category == "researched_but_not_injected":
            counts["searched_but_not_injected"] += 1
        elif category == "checked_and_skipped":
            counts["checked_and_skipped"] += 1
        elif category == "failed":
            counts["failed"] += 1
    return {
        **counts,
        "latest": decisions[0].get("category") if decisions else None,
        "latest_visible_effect": decisions[0].get("visible_effect") if decisions else None,
    }


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
        if item.get("age"):
            summary["age"] = str(item.get("age"))[:120]
        quality = item.get("quality")
        if isinstance(quality, dict):
            summary["quality"] = {
                "score": quality.get("score"),
                "confidence": quality.get("confidence"),
                "domain": quality.get("domain"),
                "profiles": quality.get("profiles") or [],
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


def _query_source_profiles(query: str) -> list[str]:
    lower = (query or "").lower()
    profiles: list[str] = []
    if re.search(
        r"\b(bürgermeister|oberbürgermeister|landrat|einwohner|einwohnerzahl|bevölkerung|"
        r"rathaus|gemeinde|stadt|landkreis|wo\s+liegt|where\s+is|located|mayor|population)\b",
        lower,
        flags=re.IGNORECASE,
    ):
        profiles.append("municipal-local")
    if re.search(
        r"\b(release notes?|changelog|version(?:en)?|docs?|documentation|api|sdk|software|"
        r"package|npm|pypi|github|gitlab|crate|rubygem|maven|nuget)\b",
        lower,
        flags=re.IGNORECASE,
    ):
        profiles.append("tech-software")
    if re.search(
        r"\b(preis|preise|pricing|price|cost|kosten|kostet|tarif|tarife|plan|plans|"
        r"subscription|abo|store|shop|buy)\b",
        lower,
        flags=re.IGNORECASE,
    ):
        profiles.append("price-product")
    if _is_freshness_sensitive_query(query):
        profiles.append("news-current")
    return sorted(set(profiles))


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


def _is_package_registry_source(domain: str) -> bool:
    return _domain_matches_any(domain, PACKAGE_REGISTRY_DOMAINS)


def _is_standards_source(domain: str, text: str) -> bool:
    return _domain_matches_any(domain, STANDARDS_DOMAINS) or bool(
        re.search(r"\b(rfc\s*\d+|specification|spezifikation|norm|working draft|recommendation)\b", text, flags=re.IGNORECASE)
    )


def _is_release_notes_source(domain: str, text: str, query: str) -> bool:
    release_query = re.search(r"\b(release notes?|changelog|version(?:en)?|latest version|neueste version|aktuelle version)\b", query, flags=re.IGNORECASE)
    if not release_query or _is_weak_aggregator_domain(domain, text) or _is_forum_or_social_domain(domain):
        return False
    return bool(re.search(r"\b(release notes?|changelog|releases?|version history|änderungsprotokoll|aenderungsprotokoll)\b", text, flags=re.IGNORECASE))


def _is_municipal_source(domain: str, text: str, query: str) -> bool:
    local_fact_query = re.search(
        r"\b(bürgermeister|oberbürgermeister|landrat|einwohner|einwohnerzahl|bevölkerung|rathaus|gemeinde|stadt|landkreis|wo\s+liegt|where\s+is|located|mayor|population)\b",
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


def _is_pricing_source(domain: str, text: str, query: str) -> bool:
    price_query = re.search(r"\b(preis|preise|pricing|price|cost|kosten|kostet|tarif|tarife|plans?|subscription|abo)\b", query, flags=re.IGNORECASE)
    if not price_query or _is_weak_aggregator_domain(domain, text) or _is_forum_or_social_domain(domain):
        return False
    return bool(re.search(r"\b(pricing|prices?|preise|tarife?|plans?|subscription|abo|store|shop|official|offiziell|vendor)\b", text, flags=re.IGNORECASE))


def _source_profiles_for_result(domain: str, text: str, query: str) -> list[str]:
    profiles = []
    if _is_government_domain(domain):
        profiles.append("government")
    if _is_municipal_source(domain, text, query):
        profiles.append("municipal")
    if _is_documentation_source(domain, text):
        profiles.append("documentation")
    if _is_primary_project_source(domain, text):
        profiles.append("project")
    if _is_package_registry_source(domain):
        profiles.append("package-registry")
    if _is_vendor_or_project_source(domain, text, query):
        profiles.append("vendor")
    if _is_release_notes_source(domain, text, query):
        profiles.append("release-notes")
    if _is_pricing_source(domain, text, query):
        profiles.append("pricing")
    if _is_standards_source(domain, text):
        profiles.append("standards")
    if domain.endswith("wikipedia.org") or domain.endswith("wikidata.org"):
        profiles.append("reference")
    if _is_forum_or_social_domain(domain):
        profiles.append("weak-forum-social")
    if _is_weak_aggregator_domain(domain, text):
        profiles.append("weak-aggregator")
    if re.search(r"\b(subscribe|subscription|paywall|sign in to continue|members only|premium)\b", text, flags=re.IGNORECASE):
        profiles.append("weak-paywall")
    if re.search(r"\b(top\s+\d+|best\b|coupon|deals?|buy now|vergleich der besten|testsieger)\b", text, flags=re.IGNORECASE):
        profiles.append("weak-commercial")
    return sorted(set(profiles))


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
    profiles = _source_profiles_for_result(domain, text, query)
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
    if "package-registry" in profiles:
        score += 18
        signals.append("package-registry-source")
    if _is_vendor_or_project_source(domain, text, query):
        score += 14
        signals.append("vendor-source")
    if "release-notes" in profiles:
        score += 14
        signals.append("release-notes-source")
    if "pricing" in profiles:
        score += 14
        signals.append("pricing-source")
    if "standards" in profiles:
        score += 18
        signals.append("standards-source")
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
        "profiles": profiles,
        "signals": sorted(set(signals)),
        "warnings": sorted(set(warnings)),
    }


def _score_research_results(results: list[dict[str, Any]], query: str) -> dict[str, Any]:
    preferred_domains = _env_list("RESEARCH_GUARD_PREFERRED_DOMAINS")
    blocked_domains = _env_list("RESEARCH_GUARD_BLOCKED_DOMAINS")
    query_profiles = _query_source_profiles(query)
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
    profile_coverage: dict[str, int] = {}
    for item in usable:
        for profile in item.get("quality", {}).get("profiles") or []:
            profile_coverage[profile] = profile_coverage.get(profile, 0) + 1
    source_profiles = sorted(profile_coverage)
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
        "query_profiles": query_profiles,
        "source_profiles": source_profiles,
        "profile_coverage": profile_coverage,
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


def _format_status_request_context() -> str:
    status_payload = research_guard_status({"limit": 5})
    return "\n".join([
        "[Research Guard: Diagnose-Status]",
        "Der Nutzer fragt ausdrücklich nach dem Research-Guard-Status.",
        "Antworte ausschließlich mit dem folgenden Status-JSON. Gib keine Quellenliste zur vorherigen Antwort aus.",
        "Gib keine freie Zusammenfassung, kein `Alles aktiv`, keine Empfehlungen und keine nachträgliche Interpretation aus.",
        "Benenne Felder nicht um: `decisions` muss `decisions` bleiben, `response_policy` muss sichtbar bleiben.",
        "Wenn du den Inhalt kürzen musst, sage nur: `Research Guard Status ist im Kontext vorhanden, aber zu groß zum vollständigen Ausgeben.`",
        "Status-JSON BEGIN",
        status_payload,
        "Status-JSON END",
        "[/Research Guard: Diagnose-Status]",
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
        "Erfinde keine persönlichen Details über den Nutzer, seine Projekte, Vorlieben oder Beziehung zum Ort.",
        "Gib keine Zeile `Quellen (Research Guard):` aus, weil für diese aktuelle Anschlussfrage keine neue Recherche lief.",
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
        "Erfinde keine persönlichen Details über den Nutzer, seine Projekte, Vorlieben oder Beziehung zum Ort. Nutze nur explizit sichtbaren Gesprächskontext.",
        "Gib keine Zeile `Quellen (Research Guard):` aus, weil diese Anschlussfrage keinen frischen Research-Guard-Webkontext ausgelöst hat.",
        f"Letzte Research-Guard-Aktion: {decision.get('action')}",
        f"Grund: {decision.get('reason')}",
        f"Provider: {decision.get('provider') or 'unknown'}",
        f"Query des vorherigen Themas: {decision.get('query') or 'unknown'}",
        "Quellen der letzten Research-Guard-Recherche:",
        *source_lines,
        "Antworte direkt auf die Anschlussfrage. Wenn du Fakten aus der letzten Recherche nutzt, erwähne sie im Fließtext als frühere Research-Guard-Basis, nicht als neue Quellenzeile.",
        "[/Research Guard: Kontext-Follow-up]",
    ])


def _load_cache() -> dict[str, Any]:
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Could not read research cache", exc_info=True)
    return {}


def _cache_max_entries() -> int:
    return _env_int("RESEARCH_GUARD_CACHE_MAX_ENTRIES", 200, 20, 5000)


def _cache_ttl_for_query(query: str) -> int:
    base_ttl = _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400)
    if base_ttl <= 0:
        return 0
    profiles = set(_query_source_profiles(query))
    if profiles.intersection({"news-current", "price-product"}):
        current_ttl = _env_int("RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS", 900, 0, 86400)
        return min(base_ttl, current_ttl) if current_ttl > 0 else 0
    return base_ttl


def _prune_cache(cache: dict[str, Any], now: float | None = None, query_ttl: int | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    max_entries = _cache_max_entries()
    default_ttl = _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400)
    pruned: dict[str, Any] = {}
    for key, item in cache.items():
        if not isinstance(item, dict):
            continue
        try:
            ts = float(item.get("ts", 0))
        except Exception:
            continue
        query_match = re.search(r"(?:^|:)query=(.*)$", key)
        ttl = query_ttl if query_ttl is not None and query_match else default_ttl
        if query_ttl is None and query_match:
            ttl = _cache_ttl_for_query(query_match.group(1))
        if ttl and now - ts >= ttl:
            continue
        pruned[key] = item
    items = sorted(pruned.items(), key=lambda kv: float(kv[1].get("ts", 0)), reverse=True)[:max_entries]
    return dict(items)


def _save_cache(cache: dict[str, Any]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(_prune_cache(cache), ensure_ascii=False, indent=2), encoding="utf-8")
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


def _html_to_readable_text(value: str) -> str:
    text = re.sub(r"<!--[\s\S]*?-->", " ", value or "")
    text = re.sub(r"<(script|style|noscript|svg|nav|header|footer|aside)\b[\s\S]*?</\1>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|section|article|main|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_html_title(value: str) -> str | None:
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", value or "", flags=re.IGNORECASE)
    title = _strip_tags(match.group(1)) if match else ""
    return title or None


def _should_deep_fetch(prompt: str) -> tuple[bool, str]:
    if not _env_bool("RESEARCH_GUARD_DEEP_FETCH", True):
        return False, "deep fetch disabled"
    mode = os.getenv("RESEARCH_GUARD_DEEP_FETCH_MODE", "structured").strip().lower()
    if mode == "always":
        return True, "deep fetch mode: always"
    if DEEP_FETCH_RE.search(prompt or ""):
        return True, "structured-list/detail prompt"
    return False, "no deep fetch trigger"


def _deep_fetch_profile(enabled: bool) -> str:
    if not enabled:
        return "off"
    return (
        f"pages={_env_int('RESEARCH_GUARD_DEEP_FETCH_MAX_PAGES', 2, 1, 3)},"
        f"chars={_env_int('RESEARCH_GUARD_DEEP_FETCH_MAX_CHARS', 3500, 800, 8000)}"
    )


def _extract_structured_tracklist(text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    items: list[dict[str, Any]] = []
    for line in lines:
        match = re.match(r"^(?:\#?\s*)?(\d{1,2})[\).:-]\s+(.{2,120})$", line)
        if not match:
            match = re.match(r"^(\d{1,2})\s+(.{2,120})$", line)
        if not match:
            continue
        title = re.sub(r"\s+\d{1,2}:\d{2}(?:\s|$).*", "", match.group(2)).strip(" -–—")
        if title:
            items.append({"number": int(match.group(1)), "title": title})
    if len(items) < 3:
        compact = re.findall(r"(?:^|\s)(\d{1,2})[\).]\s*([^0-9]{2,80}?)(?=\s+\d{1,2}[\).]\s*|$)", text or "")
        items = [{"number": int(number), "title": title.strip(" -–—")} for number, title in compact if title.strip()]
    return items[:40]


def _fetch_readable_page(title: str, url: str, max_chars: int) -> dict[str, str] | None:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        req = Request(
            url,
            headers={
                "User-Agent": "Hermes Research Guard/0.6",
                "Accept": "text/html,text/plain;q=0.9,application/xhtml+xml;q=0.8",
            },
        )
        with urlopen(req, timeout=_env_int("RESEARCH_GUARD_DEEP_FETCH_TIMEOUT", 5, 1, 12)) as resp:
            content_type = str(resp.headers.get("content-type") or "").lower()
            if content_type and "html" not in content_type and "text/plain" not in content_type:
                return None
            raw = resp.read(500_000).decode("utf-8", "ignore")
        text = raw if "text/plain" in content_type else _html_to_readable_text(raw)
        text = text[:max(500, max_chars)].strip()
        if not text:
            return None
        source: dict[str, Any] = {
            "title": _extract_html_title(raw) or title or parsed.netloc,
            "url": url,
            "text": text,
        }
        tracklist = _extract_structured_tracklist(text)
        if tracklist:
            source["structured_tracklist"] = tracklist
        return source
    except Exception:
        logger.debug("Could not deep-fetch source: %s", url, exc_info=True)
        return None


def _fetch_top_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_pages = _env_int("RESEARCH_GUARD_DEEP_FETCH_MAX_PAGES", 2, 1, 3)
    max_chars = _env_int("RESEARCH_GUARD_DEEP_FETCH_MAX_CHARS", 3500, 800, 8000)
    candidates = list(enumerate(results[:max_pages]))
    fetched_by_index: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_pages) as executor:
        future_to_index = {
            executor.submit(_fetch_readable_page, str(item.get("title") or ""), str(item.get("url") or ""), max_chars): idx
            for idx, item in candidates
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                source = future.result()
            except Exception:
                source = None
            if source:
                fetched_by_index[idx] = source
    fetched = [fetched_by_index[idx] for idx, _item in candidates if idx in fetched_by_index]
    return fetched


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


def _normalize_search_result(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    title = (
        item.get("title")
        or item.get("name")
        or item.get("headline")
        or item.get("displayTitle")
        or "Untitled"
    )
    url = item.get("url") or item.get("link") or item.get("href") or item.get("uri") or ""
    snippet = (
        item.get("snippet")
        or item.get("description")
        or item.get("desc")
        or item.get("summary")
        or item.get("content")
        or item.get("text")
        or ""
    )
    age = item.get("age") or item.get("published") or item.get("published_at") or item.get("date") or item.get("updated") or ""
    url = str(url).strip()
    if not url:
        return None
    result = {
        "title": _strip_tags(str(title))[:220] or "Untitled",
        "url": url[:500],
        "snippet": _strip_tags(str(snippet))[:600],
    }
    if age:
        result["age"] = str(age)[:120]
    return result


def _normalize_search_results(items: Any, limit: int) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    results: list[dict[str, str]] = []
    for item in items:
        normalized = _normalize_search_result(item)
        if normalized:
            results.append(normalized)
        if len(results) >= limit:
            break
    return results


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _extract_web_results(data: Any, limit: int) -> list[dict[str, str]]:
    data = _parse_jsonish(data)
    if isinstance(data, dict):
        if isinstance(data.get("data"), dict):
            nested = data["data"]
            for key in ("web", "results", "items"):
                results = _normalize_search_results(nested.get(key), limit)
                if results:
                    return results
        for key in ("web", "results", "items"):
            results = _normalize_search_results(data.get(key), limit)
            if results:
                return results
        if isinstance(data.get("result"), dict):
            results = _extract_web_results(data["result"], limit)
            if results:
                return results
        if isinstance(data.get("citations"), list):
            content = str(data.get("content") or data.get("answer") or "")
            return _normalize_search_results(
                [{"title": urlparse(str(url)).netloc or str(url), "url": str(url), "snippet": content} for url in data["citations"]],
                limit,
            )
    if isinstance(data, list):
        return _normalize_search_results(data, limit)
    return []


def _brave_search(query: str, limit: int) -> list[dict[str, str]]:
    api_key = os.getenv("BRAVE_API_KEY") or os.getenv("RESEARCH_GUARD_BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not set")
    url = "https://api.search.brave.com/res/v1/web/search?q=" + quote_plus(query) + f"&count={max(1, min(limit, 10))}"
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "Hermes Research Guard/0.6",
        },
    )
    with urlopen(req, timeout=_env_int("RESEARCH_GUARD_TIMEOUT", 8, 2, 20)) as resp:
        data = json.loads(resp.read(500_000).decode("utf-8", "ignore"))
    return _extract_web_results(data.get("web", {}).get("results") if isinstance(data, dict) else data, limit)


def _searxng_search(query: str, limit: int) -> list[dict[str, str]]:
    base_url = os.getenv("RESEARCH_GUARD_SEARXNG_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("RESEARCH_GUARD_SEARXNG_URL is not set")
    url = f"{base_url}/search?q={quote_plus(query)}&format=json&categories=general"
    req = Request(url, headers={"User-Agent": "Hermes Research Guard/0.6"})
    with urlopen(req, timeout=_env_int("RESEARCH_GUARD_TIMEOUT", 8, 2, 20)) as resp:
        data = json.loads(resp.read(500_000).decode("utf-8", "ignore"))
    return _extract_web_results(data, limit)


def _hermes_web_search(query: str, limit: int) -> list[dict[str, str]]:
    from tools.web_tools import web_search_tool

    raw = web_search_tool(query, limit=limit)
    return _extract_web_results(raw, limit)


def _web_search_plus(query: str, limit: int) -> list[dict[str, str]]:
    try:
        from tools.web_search_plus import web_search_plus
        raw = web_search_plus(query, limit=limit)
    except ImportError:
        from tools.web_search_plus import search
        raw = search(query, limit=limit)
    return _extract_web_results(raw, limit)


def _provider_order() -> list[str]:
    provider = _env_choice("RESEARCH_GUARD_PROVIDER", "auto", {"auto", "web_search_plus", "brave", "hermes", "duckduckgo", "searxng"})
    if provider == "auto":
        order = ["web_search_plus"] if _web_search_plus_available() else []
        if os.getenv("BRAVE_API_KEY") or os.getenv("RESEARCH_GUARD_BRAVE_API_KEY"):
            order.append("brave")
        order.append("hermes")
        if os.getenv("RESEARCH_GUARD_SEARXNG_URL"):
            order.append("searxng")
        order.append("duckduckgo")
        return order
    return [provider]


def _web_search_plus_available() -> bool:
    try:
        return importlib.util.find_spec("tools.web_search_plus") is not None
    except Exception:
        return False


def _provider_slug(provider: str) -> str:
    return {
        "web_search_plus": "web-search-plus",
        "brave": "brave",
        "hermes": "hermes-web",
        "duckduckgo": "duckduckgo-html",
        "searxng": "searxng",
    }.get(provider, provider)


def _run_provider(provider: str, query: str, limit: int) -> list[dict[str, str]]:
    if provider == "web_search_plus":
        return _web_search_plus(query, limit)
    if provider == "brave":
        return _brave_search(query, limit)
    if provider == "hermes":
        return _hermes_web_search(query, limit)
    if provider == "searxng":
        return _searxng_search(query, limit)
    if provider == "duckduckgo":
        return _duckduckgo_search(query, limit)
    raise RuntimeError(f"Unknown provider: {provider}")


def _provider_timeout_seconds() -> int:
    return _env_int("RESEARCH_GUARD_PROVIDER_TIMEOUT", _env_int("RESEARCH_GUARD_TIMEOUT", 8, 2, 20), 1, 30)


def _run_provider_with_timeout(provider: str, query: str, limit: int) -> list[dict[str, str]]:
    timeout = _provider_timeout_seconds()
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run_provider, provider, query, limit)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"provider timed out after {timeout}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _search(query: str, limit: int, deep_profile: str = "off") -> dict[str, Any]:
    now = time.time()
    cache_ttl = _cache_ttl_for_query(query)
    cache = _prune_cache(_load_cache(), now)
    provider_order = _provider_order()
    provider_slugs = [_provider_slug(provider) for provider in provider_order]
    def cache_key(provider: str) -> str:
        return f"provider={provider}:limit={limit}:deep={deep_profile}:query={query.strip().lower()}"

    for provider_slug in provider_slugs:
        key = cache_key(provider_slug)
        if cache_ttl and key in cache and now - float(cache[key].get("ts", 0)) < cache_ttl:
            payload = dict(cache[key]["payload"])
            payload["cached"] = True
            payload["cache_key"] = key
            payload["provider_chain"] = provider_slugs
            return payload

    errors: list[str] = []
    for provider in provider_order:
        slug = _provider_slug(provider)
        try:
            results = _run_provider_with_timeout(provider, query, limit)
            if not results:
                errors.append(f"{slug}: no results")
                continue
            key = cache_key(slug)
            payload = {
                "success": True,
                "provider": slug,
                "provider_chain": provider_slugs,
                "query": query,
                "results": results,
                "cached": False,
                "cache_key": key,
            }
            if errors:
                payload["fallback_errors"] = errors[-4:]
            if cache_ttl:
                cache[key] = {"ts": now, "payload": payload}
                _save_cache(cache)
            return payload
        except Exception as exc:
            errors.append(f"{slug}: {exc}")

    return {
        "success": False,
        "provider": "none",
        "provider_chain": provider_slugs,
        "query": query,
        "results": [],
        "error": "All configured search providers failed",
        "fallback_errors": errors[-6:],
    }


def _format_context(
    payload: dict[str, Any],
    reason: str,
    model: str | None,
    quality: dict[str, Any] | None = None,
    current_prompt: str | None = None,
    fetched_sources: list[dict[str, Any]] | None = None,
) -> str:
    if not payload.get("success"):
        return ""
    results = quality.get("results") if quality else payload.get("results", [])
    if quality and not results:
        return ""
    lines = [
        "[Research Guard aktiv]",
        "Für diese aktuelle Nutzerfrage wurde automatisch Web-Recherche ausgeführt.",
        "Diese Research-Guard-Anweisung gilt nur für diesen aktuellen Turn mit frisch angehängtem `[Research Guard: Web-Recherche-Kontext]`.",
        "Research-Guard-Kontexte, Quellenlisten, Statusdaten oder Diagnoseblöcke aus früheren Turns sind für die aktuelle Antwort ungültig.",
        "Beantworte ausschließlich die aktuelle Nutzerfrage. Wiederhole, aktualisiere oder fasse keine frühere Antwort zusammen, außer der Nutzer fordert das ausdrücklich.",
        "Du MUSST faktische Aussagen auf den folgenden Research-Guard-Kontext stützen, wenn die Quellen die Frage beantworten.",
        "Behaupte niemals, du hättest nicht recherchiert, die Antwort stamme nur aus Trainingswissen oder Websuche sei unnötig, wenn Research-Guard-Quellen vorhanden sind.",
        "[/Research Guard aktiv]",
        "",
        "[Research Guard: Web-Recherche-Kontext]",
        f"Auslöser: {reason}; Modell: {model or 'unknown'}; Provider: {payload.get('provider')}; Query: {payload.get('query')}",
        "Diese Quellen wurden automatisch durch Research Guard für die aktuelle Nutzerfrage recherchiert.",
        "Aktuelle-Frage-Pflicht: Beantworte nur die aktuelle Nutzerfrage. Wiederhole keine vorherige Antwort und beantworte keine frühere Nutzerfrage erneut, außer der Nutzer verlangt es ausdrücklich.",
        "Nutze die Quellen unten für faktische Aussagen. Antworte nicht nur aus Trainingswissen, wenn diese Quellen passen.",
        "Wenn der Nutzer später fragt, woher die Info stammt oder wie die Antwort zustande kam, nenne Research Guard und die URLs aus diesem Kontext.",
        "Beachte die Quellenbewertung. Bei niedriger Confidence antworte vorsichtig und markiere Unsicherheit ausdrücklich.",
        "Wenn die Quellen nicht reichen oder widersprüchlich sind, sag das klar. Erfinde keine Details oder Quellen.",
        "Füge keine unaufgeforderten Zusatzfakten hinzu. Bei Ortsfragen wie `Wo liegt ...?` nenne keine Flüsse, Verkehrsachsen, Einwohnerzahlen oder Entfernungen, außer sie wurden gefragt und stehen ausdrücklich in den Quellen.",
        "Tracklist-Pflicht: Bei Tracklists, Songlisten oder Titellisten darfst du NICHT aus Such-Snippets, Streaming-Katalog-Mischungen oder Anniversary-/Bonus-Editionen synthetisieren. Nutze nur eine klar belegte Standard-/Original-Tracklist aus den vertieften Quellen-Auszügen. Wenn keine solche Liste enthalten ist, sage, dass die Quellen nicht reichen.",
    ]
    if _env_bool("RESEARCH_GUARD_REQUIRE_SOURCES", True):
        lines.append("Quellenpflicht: Füge am Ende eine kurze Zeile `Quellen (Research Guard): <URL 1>, <URL 2>` mit 1-2 passenden URLs aus dieser Liste an, außer der Nutzer verlangt ausdrücklich keine Quellen.")
        lines.append("Sichtbarkeitspflicht: Wenn diese Quellen vorhanden sind, darf die Antwort nicht ohne `Quellen (Research Guard):`-Zeile enden.")
    else:
        lines.append("Nenne Research-Guard-Quellen, wenn sie für die Antwort hilfreich sind oder der Nutzer nach Quellen fragt.")
    if quality:
        lines.append(
            "Quellenbewertung: "
            f"{quality.get('confidence')} ({quality.get('score')}/100, "
            f"{quality.get('usable_result_count')}/{quality.get('result_count')} nutzbare Quelle(n), "
            f"Quellenvielfalt: {quality.get('evidence_diversity')}, "
            f"{quality.get('unique_domain_count')} Domain(s), "
            f"{quality.get('duplicate_cluster_count')} Duplicate-Hinweis(e))."
        )
        if quality.get("query_profiles") or quality.get("source_profiles"):
            query_profiles = ", ".join(quality.get("query_profiles") or ["none"])
            source_profiles = ", ".join(quality.get("source_profiles") or ["none"])
            lines.append(f"Quellenprofile: Anfrage={query_profiles}; Treffer={source_profiles}.")
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
            profiles = ", ".join(item_quality.get("profiles") or [])
            signals = ", ".join(item_quality.get("signals") or [])
            warnings = " ".join(item_quality.get("warnings") or [])
            profile_text = f"; Profile: {profiles}" if profiles else ""
            signal_text = f"; {signals}" if signals else ""
            warning_text = f"; Warnung: {warnings}" if warnings else ""
            lines.append(
                "   Qualität: "
                f"{item_quality.get('confidence')} ({item_quality.get('score')}/100; "
                f"{item_quality.get('domain')}{profile_text}{signal_text}{warning_text})"
            )
    if fetched_sources:
        lines.extend(["", "[Research Guard: Vertiefte Quellen-Auszüge]"])
        for idx, source in enumerate(fetched_sources, 1):
            lines.append(f"{idx}. {source.get('title') or 'Untitled'}")
            lines.append(f"   URL: {source.get('url') or ''}")
            tracklist = source.get("structured_tracklist") or []
            if tracklist:
                lines.append("   Strukturierte Tracklist-Kandidaten:")
                for item in tracklist:
                    lines.append(f"   {item.get('number')}. {item.get('title')}")
            lines.append(f"   Inhalt: {source.get('text') or ''}")
        lines.append("[/Research Guard: Vertiefte Quellen-Auszüge]")
    lines.append("[/Research Guard: Web-Recherche-Kontext]")
    return "\n".join(lines)


def _format_no_research_context(reason: str, current_prompt: str | None = None, model: str | None = None, provider: str | None = None) -> str:
    lines = [
        "[Research Guard inaktiv für aktuelle Frage]",
        "Für diese aktuelle Nutzerfrage wurde KEIN neuer Research-Guard-Webkontext injiziert.",
        "Ignoriere alle `[Research Guard: Web-Recherche-Kontext]`, `[Research Guard: Vertiefte Quellen-Auszüge]`, `[Research Guard: Quellenstatus]`, `[Research Guard: Diagnose-Status]` und `Quellen (Research Guard):`-Angaben aus früheren Turns vollständig.",
        "Sie gelten nur für die jeweilige frühere Nutzerfrage und dürfen für diese Antwort nicht als aktuelle Quellen wiederverwendet werden.",
        "Beantworte ausschließlich die aktuelle Nutzerfrage. Wiederhole, aktualisiere oder fasse keine frühere Antwort zusammen, außer der Nutzer fordert das ausdrücklich.",
        "Gib keine Zeile `Quellen (Research Guard):` aus, solange in diesem aktuellen Turn kein frischer Research-Guard-Kontext angehängt ist.",
        "Behaupte nicht, Research Guard habe für diese aktuelle Frage recherchiert.",
        "Wenn die aktuelle Frage lokale Infrastruktur, IPs, Hosts, SSH, Tailscale oder interne Verbindungen betrifft, nutze nur lokalen Kontext oder verfügbare lokale Tools, nicht Webquellen.",
        f"Grund: {reason}",
    ]
    if model or provider:
        lines.append(f"Modell/Provider: {model or 'unknown'} / {provider or 'unknown'}")
    if current_prompt:
        lines.append(f"Aktuelle Nutzerfrage: {current_prompt}")
    lines.append("[/Research Guard inaktiv für aktuelle Frage]")
    return "\n".join(lines)


def _no_research_response(reason: str, current_prompt: str | None, model: str | None, provider: str | None) -> dict[str, str] | None:
    if not _env_bool("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", False):
        return None
    return {"context": _format_no_research_context(reason, current_prompt, model, provider)}


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
        query_match = re.search(r"(?:^|:)query=(.*)$", key)
        ttl = _cache_ttl_for_query(query_match.group(1)) if query_match else _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400)
        if ttl and now - ts < ttl:
            valid_entries += 1
        else:
            expired_entries += 1
    return {
        "entries": len(cache),
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "ttl_seconds": _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400),
        "current_ttl_seconds": _env_int("RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS", 900, 0, 86400),
        "max_entries": _cache_max_entries(),
        "provider_counts": provider_counts,
        "path": str(CACHE_PATH),
    }


def _config_snapshot() -> dict[str, Any]:
    return {
        "enabled": _env_bool("RESEARCH_GUARD_ENABLED", True),
        "only_local": _env_bool("RESEARCH_GUARD_ONLY_LOCAL", True),
        "allow_cloud_research_triggers": _env_bool("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS", False),
        "provider": _env_choice("RESEARCH_GUARD_PROVIDER", "auto", {"auto", "web_search_plus", "brave", "hermes", "duckduckgo", "searxng"}),
        "provider_chain": [_provider_slug(provider) for provider in _provider_order()],
        "mode": _env_choice("RESEARCH_GUARD_MODE", "balanced", {"conservative", "balanced", "aggressive"}),
        "max_results": _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10),
        "timeout_seconds": _env_int("RESEARCH_GUARD_TIMEOUT", 8, 2, 20),
        "provider_timeout_seconds": _provider_timeout_seconds(),
        "deep_fetch_timeout_seconds": _env_int("RESEARCH_GUARD_DEEP_FETCH_TIMEOUT", 5, 1, 12),
        "cache_max_entries": _cache_max_entries(),
        "cache_ttl_seconds": _env_int("RESEARCH_GUARD_CACHE_TTL_SECONDS", 3600, 0, 86400),
        "cache_ttl_current_seconds": _env_int("RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS", 900, 0, 86400),
        "min_confidence": _parse_confidence(os.getenv("RESEARCH_GUARD_MIN_CONFIDENCE"), "low"),
        "require_multiple_sources": _env_bool("RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES", False),
        "require_sources": _env_bool("RESEARCH_GUARD_REQUIRE_SOURCES", True),
        "inject_no_research_boundary": _env_bool("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", False),
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
    deep_fetch_enabled = bool(args.get("deep_fetch") or args.get("deepFetch"))
    payload = _search(query, max(1, min(limit, 10)), _deep_fetch_profile(deep_fetch_enabled))
    quality = _score_research_results(payload.get("results") or [], str(payload.get("query") or query)) if payload.get("success") else None
    fetched_sources = _fetch_top_sources(quality.get("results") if quality and deep_fetch_enabled else []) if deep_fetch_enabled else []
    if quality:
        payload = {**payload, "results": quality["results"], "quality": quality}
    if fetched_sources:
        payload = {**payload, "fetched_sources": fetched_sources}
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
        query_profiles=quality.get("query_profiles") if quality else None,
        source_profiles=quality.get("source_profiles") if quality else None,
        profile_coverage=quality.get("profile_coverage") if quality else None,
        fetched_source_count=len(fetched_sources),
        provider_chain=payload.get("provider_chain"),
        cache_key=payload.get("cache_key"),
        cached=payload.get("cached"),
        sources=_source_summaries(payload.get("results") or []),
        error=payload.get("error"),
        fallback_errors=payload.get("fallback_errors"),
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def research_guard_status(args: dict, **kwargs) -> str:
    """Manual tool: show recent Research Guard decisions."""
    del kwargs
    limit = int(args.get("limit") or 5)
    include_sources = args.get("include_sources", args.get("includeSources", True)) is not False
    decisions = [_diagnose_decision(decision) for decision in _recent_decisions(limit)]
    if not include_sources:
        decisions = [{key: value for key, value in decision.items() if key != "sources"} for decision in decisions]
    categories: dict[str, int] = {}
    for decision in decisions:
        category = str(decision.get("category") or "unknown")
        categories[category] = categories.get(category, 0) + 1
    return json.dumps(
        {
            "plugin": "research-guard",
            "version": __version__,
            "status_version": 2,
            "runtime": {
                "module_version": __version__,
                "skipped_turns_inject_context_by_default": False,
                "no_research_boundary_env": _env_bool("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", False),
            },
            "config": _config_snapshot(),
            "cache": _cache_stats(),
            "status_buffer": {
                "entries": len(DECISIONS),
                "max_entries": MAX_DECISIONS,
            },
            "legend": {
                "researched_and_injected": "Research Guard searched and injected source context into the model prompt.",
                "manual_research": "Research Guard was explicitly called as a search tool and returned search results.",
                "researched_but_not_injected": "Research Guard searched, but blocked injection because quality, confidence, or result checks failed.",
                "checked_and_skipped": "Research Guard inspected the prompt and deliberately did not search.",
                "failed": "Research Guard tried to run and failed.",
            },
            "categories": categories,
            "summary": _summarize_decision_history(decisions),
            "response_policy": STATUS_RESPONSE_POLICY,
            "decisions": decisions,
            "diagnostics": {
                "decision_fields": [
                    "diagnostic", "category", "visible_effect", "evidence", "query_debug",
                    "confidence", "score", "usable_result_count", "blocked_result_count",
                    "evidence_diversity", "query_profiles", "source_profiles", "profile_coverage",
                    "warnings", "rewrite_strategy",
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
    current_prompt = _clean_message_for_research(user_message)[:240]
    if not _env_bool("RESEARCH_GUARD_ENABLED", True):
        _record_decision("skipped", "plugin disabled", model=model, provider=provider, query_debug=query_debug)
        return None
    should, reason = _should_research(user_message)
    if reason == "status-request":
        return {"context": _format_status_request_context()}
    if reason == "source-followup":
        return {"context": _format_source_followup_context()}
    if reason == "context-followup":
        return {"context": _format_context_followup_context()}
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
            prompt=current_prompt[:180],
        )
        return _no_research_response("non-local model gate", current_prompt, model, provider)
    if not should:
        _record_decision("skipped", reason, model=model, provider=provider, query_debug=query_debug, prompt=current_prompt[:180])
        return _no_research_response(reason, current_prompt, model, provider)
    query = str(query_debug.get("final_query") or _build_search_query(user_message, messages))
    if not query:
        _record_decision("skipped", "empty query after cleanup", model=model, provider=provider, query_debug=query_debug)
        return _no_research_response("empty query after cleanup", current_prompt, model, provider)
    deep_fetch, deep_fetch_reason = _should_deep_fetch(_clean_message_for_research(user_message))
    limit = _env_int("RESEARCH_GUARD_MAX_RESULTS", 5, 1, 10)
    payload = _search(query, limit, _deep_fetch_profile(deep_fetch))
    quality = _score_research_results(payload.get("results") or [], str(payload.get("query") or query)) if payload.get("success") else None
    fetched_sources = _fetch_top_sources(quality.get("results") if quality and deep_fetch else []) if deep_fetch else []
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
            query_profiles=quality.get("query_profiles"),
            source_profiles=quality.get("source_profiles"),
            profile_coverage=quality.get("profile_coverage"),
            warnings=quality.get("warnings"),
            deep_fetch=deep_fetch,
            deep_fetch_reason=deep_fetch_reason,
            fetched_source_count=len(fetched_sources),
            provider_chain=payload.get("provider_chain"),
            cache_key=payload.get("cache_key"),
            cached=payload.get("cached"),
        )
        return _no_research_response(f"confidence {quality.get('confidence')} below configured minimum {min_confidence}", current_prompt, model, provider)
    context = _format_context(payload, reason, model, quality, current_prompt, fetched_sources)
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
            evidence_diversity=quality.get("evidence_diversity") if quality else None,
            query_profiles=quality.get("query_profiles") if quality else None,
            source_profiles=quality.get("source_profiles") if quality else None,
            profile_coverage=quality.get("profile_coverage") if quality else None,
            deep_fetch=deep_fetch,
            deep_fetch_reason=deep_fetch_reason,
            fetched_source_count=len(fetched_sources),
            provider_chain=payload.get("provider_chain"),
            cache_key=payload.get("cache_key"),
            cached=payload.get("cached"),
            error=payload.get("error"),
            fallback_errors=payload.get("fallback_errors"),
        )
        logger.info("research-guard search skipped/failed: %s", payload.get("error"))
        return _no_research_response("search failed or returned no injectable context", current_prompt, model, provider)
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
        query_profiles=quality.get("query_profiles") if quality else None,
        source_profiles=quality.get("source_profiles") if quality else None,
        profile_coverage=quality.get("profile_coverage") if quality else None,
        warnings=quality.get("warnings") if quality else None,
        deep_fetch=deep_fetch,
        deep_fetch_reason=deep_fetch_reason,
        fetched_source_count=len(fetched_sources),
        provider_chain=payload.get("provider_chain"),
        sources=_source_summaries(quality.get("results") if quality else payload.get("results") or []),
        fallback_errors=payload.get("fallback_errors"),
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
            "deep_fetch": {"type": "boolean", "description": "Fetch readable excerpts from top results", "default": False},
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

DIAGNOSTICS_TOOL_SCHEMA = {
    **STATUS_TOOL_SCHEMA,
    "name": "research_guard_diagnostics",
    "description": "Alias for research_guard_status. Show Research Guard diagnostics only: decisions, categories, visible effects, query debug, source quality, config snapshot, and cache stats.",
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
    ctx.register_tool(
        name="research_guard_diagnostics",
        toolset="research_guard",
        schema=DIAGNOSTICS_TOOL_SCHEMA,
        handler=research_guard_status,
        emoji="🧭",
        max_result_size_chars=50_000,
    )
