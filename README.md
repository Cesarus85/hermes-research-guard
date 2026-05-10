# Hermes Research Guard

A lightweight Hermes Agent plugin that automatically performs web research before local/small models answer factual or current-information questions.

It is meant for setups where models like Qwen, Llama, Mistral, Gemma, Phi, or Ollama-hosted models are excellent at reasoning but may hallucinate or lack fresh facts.

## What it does

- Registers a `pre_llm_call` hook.
- Detects local/small models by model name heuristics.
- Detects factual, general-knowledge, and current-information questions.
- Skips likely local, personal, coding, file, terminal, and writing tasks.
- Skips local infrastructure prompts such as IP addresses, hosts, ports, SSH, ping, Tailscale, reachability, and service-status questions.
- Cleans common speech/STT wrappers such as `Audio:`, `Voice:`, `Transkript:`, and `Sprachnachricht:` before classification and search query building.
- Searches the web before the model answers.
- Injects compact source context into the user message, not the system prompt.
- Tells the model to cite Research Guard sources when context was injected.
- Keeps a small in-memory decision buffer so source follow-ups such as `Wo hast du die Info her?` can be answered from the previous Research Guard decision instead of triggering a fresh search for the follow-up itself.
- Detects context/opinion follow-ups such as `Was hältst du davon?` and reuses the last Research Guard topic instead of searching the literal follow-up phrase.
- Exposes manual `research_guard_search` and `research_guard_status` tools for debugging/manual use.

This keeps system prompts stable and preserves prompt-cache efficiency.

## Install

Copy the plugin folder into your Hermes user plugin directory:

```bash
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/research-guard
```

Enable it:

```bash
hermes plugins enable research-guard
hermes gateway restart
```

Or edit `~/.hermes/config.yaml` manually:

```yaml
plugins:
  enabled:
    - research-guard
```

## Configuration

Optional environment variables:

| Variable | Default | Description |
|---|---:|---|
| `RESEARCH_GUARD_ENABLED` | `true` | Master on/off switch |
| `RESEARCH_GUARD_ONLY_LOCAL` | `true` | Only trigger for local/small model names |
| `RESEARCH_GUARD_LOCAL_PATTERNS` | built-in list | Comma-separated model-name patterns |
| `RESEARCH_GUARD_MAX_RESULTS` | `5` | Search results to inject, clamped 1-10 |
| `RESEARCH_GUARD_TIMEOUT` | `8` | DuckDuckGo fallback timeout in seconds |
| `RESEARCH_GUARD_CACHE_TTL_SECONDS` | `3600` | Query cache TTL |

Built-in local model patterns include:

```text
qwen, ollama, llama, mistral, gemma, phi, deepseek, yi-, codellama, local, lmstudio, mlx, gguf
```

## Manual opt-in / opt-out

Force research:

```text
#research Wer ist aktuell Präsident von Frankreich?
/research Wer ist aktuell Präsident von Frankreich?
```

Skip research:

```text
#no-research Wer ist aktuell Präsident von Frankreich?
/no-research Wer ist aktuell Präsident von Frankreich?
```

Other slash commands, such as `/status` or `/help`, are skipped by default unless `/research` explicitly forces research.

## Source follow-ups

Hermes injects plugin context only ephemerally into the current user message. That means the raw Research Guard source block is not persisted in the normal conversation history. To make follow-up questions reliable, Research Guard now stores recent decisions in memory.

When the next user turn asks where an answer came from, for example:

```text
Wo hast du die Info her?
Was waren deine Quellen?
Wie kam die Antwort zustande?
```

Research Guard does not search those follow-up words. Instead, it injects a compact `[Research Guard: Quellenstatus]` block with the last research action, query, provider, and stored URLs. The model is told not to claim the previous factual answer came only from training data when Research Guard context was injected.

You can also ask the model to call:

```text
research_guard_status
```

That tool returns the recent decision buffer as JSON.

## Context and opinion follow-ups

Short follow-ups such as:

```text
Was hältst du davon?
Was sagst du dazu?
Wie findest du das?
```

are usually about the previous topic, not standalone search queries. Research Guard therefore skips literal web searches for those phrases and injects a `[Research Guard: Kontext-Follow-up]` block instead. The block points the model at the last Research Guard query and stored URLs, and tells it to separate source-backed facts from its own opinion or assessment.

If the Hermes process was restarted or no previous Research Guard decision exists, the model is told to answer from visible conversation context only and not invent web sources.

## Privacy boundaries

Research Guard should not send local/private operational questions to external web search. Prompts about internal machines, IP addresses, hostnames, SSH, ping, Tailscale, local reachability, service status, files, terminal commands, memory, notes, calendars, or personal context are deliberately skipped unless the user explicitly forces research.

Examples that should skip web search:

```text
Welche Tailscale-IP hat Goliath?
Was ist der SSH-Port von Ares?
Hast du Zugriff auf Ares?
Wie ist der Status der Verbindung zu Goliath?
```

## Search backend

Research Guard first tries Hermes' built-in `tools.web_tools.web_search_tool`.

If that is unavailable or misconfigured, it falls back to DuckDuckGo's HTML endpoint and parses compact result metadata.

## Development notes

The plugin intentionally avoids modifying the system prompt. Hermes injects hook context into the user-message context via `pre_llm_call`, which is friendlier to prompt caching and safer than dynamically rewriting system instructions.

Run the current dependency-free tests with:

```bash
python3 -m unittest discover -s test -p 'test_*.py'
```

## License

MIT
