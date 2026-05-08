# Hermes Research Guard

A lightweight Hermes Agent plugin that automatically performs web research before local/small models answer factual or current-information questions.

It is meant for setups where models like Qwen, Llama, Mistral, Gemma, Phi, or Ollama-hosted models are excellent at reasoning but may hallucinate or lack fresh facts.

## What it does

- Registers a `pre_llm_call` hook.
- Detects local/small models by model name heuristics.
- Detects factual, general-knowledge, and current-information questions.
- Skips likely local, personal, coding, file, terminal, and writing tasks.
- Searches the web before the model answers.
- Injects compact source context into the user message, not the system prompt.
- Exposes a manual `research_guard_search` tool for debugging/manual use.

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
```

Skip research:

```text
#no-research Wer ist aktuell Präsident von Frankreich?
```

## Search backend

Research Guard first tries Hermes' built-in `tools.web_tools.web_search_tool`.

If that is unavailable or misconfigured, it falls back to DuckDuckGo's HTML endpoint and parses compact result metadata.

## Development notes

The plugin intentionally avoids modifying the system prompt. Hermes injects hook context into the user-message context via `pre_llm_call`, which is friendlier to prompt caching and safer than dynamically rewriting system instructions.

## License

MIT
