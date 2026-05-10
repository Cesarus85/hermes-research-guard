# Hermes Research Guard

A lightweight Hermes Agent plugin that automatically performs web research before local/small models answer factual or current-information questions.

It is meant for setups where models like Qwen, Llama, Mistral, Gemma, Phi, or Ollama-hosted models are excellent at reasoning but may hallucinate or lack fresh facts.

## What it does

- Registers a `pre_llm_call` hook.
- Detects local/small models by model and provider heuristics, including local providers such as Ollama, LM Studio, vLLM, TGI, llama.cpp, MLX, and Goliath.
- Skips explicit cloud markers such as Ollama `:cloud` unless manually forced or configured otherwise.
- Detects factual, general-knowledge, and current-information questions.
- Skips likely local, personal, coding, file, terminal, and writing tasks.
- Skips local infrastructure prompts such as IP addresses, hosts, ports, SSH, ping, Tailscale, reachability, and service-status questions.
- Cleans common speech/STT wrappers such as `Audio:`, `Voice:`, `Transkript:`, and `Sprachnachricht:` before classification and search query building.
- Searches the web before the model answers.
- Scores sources before injection: official, municipal, government, documentation, vendor/project, and reference sources are preferred; aggregators, forums/social pages, paywalls, listicles, duplicates, and repeated same-domain hits are downgraded.
- Injects compact source context into the user message, not the system prompt.
- Adds a compact confidence/evidence-diversity summary to the injected context.
- Tells the model to cite Research Guard sources when context was injected.
- Keeps a small in-memory decision buffer so source follow-ups such as `Wo hast du die Info her?` can be answered from the previous Research Guard decision instead of triggering a fresh search for the follow-up itself.
- Detects context/opinion follow-ups such as `Was hältst du davon?` and reuses the last Research Guard topic instead of searching the literal follow-up phrase.
- Carries a prior subject from Hermes `conversation_history`, `messages`, or `history` into pronoun/demonstrative follow-up search queries such as `Was ist mit ihm danach passiert?`.
- Exposes manual `research_guard_search`, `research_guard_status`, and `research_guard_diagnostics` tools for debugging/manual use. Status v2 includes cache stats, config snapshot, decision categories, visible effect, evidence strings, source-quality fields, and redacted query-building diagnostics.
- Detects direct status requests such as `Zeig mir den Research Guard Status` and injects the same diagnostics even when Hermes does not trigger the status tool call itself.

This keeps system prompts stable and preserves prompt-cache efficiency.

## Install

For a fresh install, copy the plugin folder into your Hermes user plugin directory:

```bash
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/
```

For an update from an older version, remove the old plugin directory first. This matters because copying over an existing `~/.hermes/plugins/research-guard` directory can leave the old `plugin.yaml` in place or create a nested `research-guard/research-guard` folder on some systems:

```bash
hermes plugins disable research-guard
rm -rf ~/.hermes/plugins/research-guard
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/
hermes plugins enable research-guard
hermes gateway restart
```

After installing, verify the manifest that Hermes should read:

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
```

Expected for this release:

```text
version: 0.6.2
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
| `RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS` | `false` | Allow automatic research for cloud models when a prompt would otherwise trigger research |
| `RESEARCH_GUARD_LOCAL_PATTERNS` | built-in list | Comma-separated model-name patterns |
| `RESEARCH_GUARD_MAX_RESULTS` | `5` | Search results to inject, clamped 1-10 |
| `RESEARCH_GUARD_TIMEOUT` | `8` | DuckDuckGo fallback timeout in seconds |
| `RESEARCH_GUARD_CACHE_TTL_SECONDS` | `3600` | Query cache TTL |
| `RESEARCH_GUARD_PREFERRED_DOMAINS` | empty | Comma-separated domains to boost, e.g. `forchheim.de,bayern.de` |
| `RESEARCH_GUARD_BLOCKED_DOMAINS` | empty | Comma-separated domains to exclude from injected sources |
| `RESEARCH_GUARD_MIN_CONFIDENCE` | `low` | Minimum source confidence required for injection: `low`, `medium`, or `high` |
| `RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES` | `false` | Downgrade confidence when fewer than two usable/unique source domains pass scoring |
| `RESEARCH_GUARD_DEEP_FETCH` | `true` | Fetch readable excerpts for structured/detail prompts such as tracklists, tables, release notes, and population facts |
| `RESEARCH_GUARD_DEEP_FETCH_MAX_PAGES` | `2` | Number of top scored sources to fetch, clamped 1-3 |
| `RESEARCH_GUARD_DEEP_FETCH_MAX_CHARS` | `3500` | Characters per fetched source excerpt, clamped 800-8000 |
| `RESEARCH_GUARD_DEEP_FETCH_TIMEOUT` | `5` | Timeout per fetched source in seconds |

Built-in local model patterns include:

```text
qwen, ollama, llama, mistral, gemma, phi, deepseek, yi-, codellama, local,
lmstudio, mlx, gguf, vllm, tgi, kimi-k2, minimax-m2
```

Built-in local provider patterns include:

```text
ollama, lmstudio, lm-studio, mlx, llama.cpp, local, vllm, tgi, goliath
```

Cloud provider/model patterns such as `openai`, `anthropic`, `gemini`, `openrouter`, `perplexity`, `gpt-`, and `claude` are skipped by default. Manual `/research` still overrides the model gate.

## Source quality

Research Guard now ranks and annotates search results before injecting them. The goal is to give Hermes the best available evidence first, not just the first search results.

Boosted signals include:

```text
preferred-domain, government-source, municipal-source, documentation-source,
primary-project-source, vendor-source, reference-source, official-context
```

Warnings include:

```text
Forum or social source, Likely aggregator or SEO-heavy source,
Possible paywall or snippet-only source, Commercial or listicle-style source,
Undated source for current-information query, Possibly stale source
```

The injected context includes a `Quellenbewertung:` line with confidence, score, usable-source count, evidence diversity, unique domains, and duplicate hints. For local/municipal questions such as mayors or population, city/municipal pages are preferred when their title or snippet indicates an official administration source.

For location questions such as `Wo liegt Forchheim?`, the context now explicitly tells the model to answer only the location/administrative classification and avoid extra rivers, traffic routes, population numbers, distances, or unrelated details unless the user asked and the sources support them.

## Structured Deep Fetch

For structured prompts such as tracklists, song lists, tables, release notes, prices, benchmarks, and population facts, Research Guard fetches readable excerpts from the top scored sources and injects them under `[Research Guard: Vertiefte Quellen-Auszüge]`.

Deep fetch now runs the top-page fetches in parallel, records fetched-source counts in diagnostics, and includes the deep-fetch profile in cache keys so snippet-only and fetched-source runs do not collide.

Tracklist prompts have an extra rule: the model must not synthesize a list from search snippets, streaming catalog mixes, or anniversary/bonus editions. It should use only a clearly source-backed standard/original tracklist from the fetched excerpts, or say that the sources are insufficient. Research Guard also extracts simple numbered tracklist candidates from fetched pages and surfaces them separately in the context.

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

If Hermes does not surface that tool name clearly, `research_guard_diagnostics` is registered as an alias with the same output.

That tool returns the recent decision buffer as JSON.

`research_guard_status` uses status v2. Each decision includes:

```text
category, visible_effect, evidence, query_debug, confidence, score,
usable_result_count, blocked_result_count, evidence_diversity, warnings
```

Categories include `researched_and_injected`, `manual_research`, `researched_but_not_injected`, `checked_and_skipped`, and `failed`. The `query_debug` object shows the redacted original prompt preview, cleaned prompt, carried subject, final query, and whether Hermes history was available. Prompt previews redact emails, phone-like values, and long token-like strings.

The status payload also includes cache statistics and a compact configuration snapshot so you can verify model-gate, confidence, preferred-domain, and blocked-domain behavior during real Hermes runs.

## Context and opinion follow-ups

Short follow-ups such as:

```text
Was hältst du davon?
Was sagst du dazu?
Wie findest du das?
```

are usually about the previous topic, not standalone search queries. Research Guard therefore skips literal web searches for those phrases and injects a `[Research Guard: Kontext-Follow-up]` block instead. The block points the model at the last Research Guard query and stored URLs, and tells it to separate source-backed facts from its own opinion or assessment.

If the Hermes process was restarted or no previous Research Guard decision exists, the model is told to answer from visible conversation context only and not invent web sources.

For factual follow-up questions that still require search, Research Guard can reuse a prior subject from Hermes history. If Hermes passes `conversation_history`, `messages`, or `history`, prompts such as:

```text
Wer ist Wal Timmy?
Was ist mit ihm danach passiert?
```

build a search query like:

```text
Wal Timmy Was ist mit ihm danach passiert?
```

This is a deterministic v1 carryover. It is intentionally conservative and only activates for pronoun/demonstrative follow-ups such as `ihm`, `sie`, `es`, `dort`, `dazu`, `davon`, `darüber`, `danach`, `it`, `this`, or `that`.

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

The query cache key includes provider, result count, a reserved deep-fetch flag, and normalized query text so fallback-provider results do not collide with Hermes-provider results.

## Development notes

The plugin intentionally avoids modifying the system prompt. Hermes injects hook context into the user-message context via `pre_llm_call`, which is friendlier to prompt caching and safer than dynamically rewriting system instructions.

Run the current dependency-free tests with:

```bash
python3 -m unittest discover -s test -p 'test_*.py'
```

## License

MIT
