# Hermes Research Guard

**Beta release:** `v0.8.0-beta.1`

Hermes Research Guard is a lightweight pre-answer research plugin for local and small LLM setups. It runs a web search before the model answers factual or current-information questions, ranks the sources, and injects a compact evidence block into the current prompt.

It is designed for agents using models such as Qwen, Llama, Mistral, Gemma, Phi, Ollama-hosted models, LM Studio, vLLM, TGI, llama.cpp, MLX, or other local providers that reason well but may lack fresh facts.

## Beta Status

This repository is ready for a first public beta. The core behavior is implemented and covered by dependency-free tests, but the project should still be treated as experimental in production-like agent setups.

What is considered beta-stable:

- automatic research for local/small models
- manual `/research` and `/no-research` controls
- provider chain: optional `web_search_plus`, Brave, Hermes web search, SearXNG, DuckDuckGo HTML
- provider-aware cache keys and cache cleanup
- source scoring with official, municipal, documentation, vendor, project, package registry, release-note, pricing, standards, and reference signals
- weak-source demotion for aggregators, forums/social pages, scraper-like results, paywall/snippet-only pages, listicles, coupons, duplicate URLs, and repeated same-domain evidence
- structured deep fetch for tracklists, tables, release notes, prices, benchmarks, population facts, and other detail-heavy prompts
- context follow-up handling for questions such as "Where did you get that from?" or "What do you think about it?"
- `research_guard_status` and `research_guard_diagnostics` diagnostics
- compact status explanations showing why Research Guard ran or skipped
- tests passing locally

Known beta limitations:

- Research Guard improves grounding, but it cannot guarantee truth.
- Local models can still ignore or misread injected sources.
- Trigger detection is heuristic and will never be perfect.
- High-stakes handling for medical, legal, financial, and safety-critical prompts is not finished.
- Hermes injects plugin context into the current user message, not the system prompt.
- The no-research boundary is disabled by default because some local model UIs expose injected skip-context as visible reasoning.

## How It Works

Research Guard registers a Hermes `pre_llm_call` hook. For each user message it:

1. Cleans wrappers such as `Audio:`, `Voice:`, `Transcript:`, and `Transkript:`.
2. Checks whether the prompt should trigger research.
3. Skips private, local, coding, file, terminal, memory, and infrastructure prompts.
4. Applies the local/cloud model gate.
5. Rewrites factual prompts into search-friendly queries.
6. Searches through the configured provider chain.
7. Scores and filters sources.
8. Optionally deep-fetches top pages for structured/detail prompts.
9. Injects a compact Research Guard context block into the current user turn.
10. Records the decision in an in-memory status buffer.

The plugin intentionally does not modify the system prompt.

## Install With Hermes

Fresh install from GitHub:

```bash
git clone https://github.com/Cesarus85/hermes-research-guard.git
cd hermes-research-guard
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/
hermes plugins enable research-guard
hermes gateway restart
```

Update an existing Hermes installation:

```bash
git clone https://github.com/Cesarus85/hermes-research-guard.git /tmp/hermes-research-guard
hermes plugins disable research-guard
rm -rf ~/.hermes/plugins/research-guard
mkdir -p ~/.hermes/plugins
cp -R /tmp/hermes-research-guard/research-guard ~/.hermes/plugins/
hermes plugins enable research-guard
hermes gateway restart
```

Verify that Hermes sees the beta manifest:

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
```

Expected:

```text
version: 0.8.0-beta.1
```

If you manage plugins manually, make sure `~/.hermes/config.yaml` contains:

```yaml
plugins:
  enabled:
    - research-guard
```

## Install Without Hermes

Research Guard can also be used without Hermes as a standalone Python module or as a reference implementation for another agent runtime. In this mode there is no automatic pre-LLM hook unless your host application calls it.

Clone and test:

```bash
git clone https://github.com/Cesarus85/hermes-research-guard.git
cd hermes-research-guard
python3 -m unittest discover -s test -p 'test_*.py'
```

Run a manual search from Python:

```bash
python3 - <<'PY'
import importlib.util
import json
from pathlib import Path

module_path = Path("research-guard") / "__init__.py"
spec = importlib.util.spec_from_file_location("research_guard_plugin", module_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

payload = guard.research_guard_search({
    "query": "latest Python version release notes",
    "limit": 3,
    "deep_fetch": False,
})
print(payload)
PY
```

Use the pre-LLM hook from another runtime:

```python
result = guard.pre_llm_research_guard(
    session_id="example-session",
    user_message="Which Python version is current?",
    model="qwen3",
    platform="ollama",
    conversation_history=[],
)

if result and result.get("context"):
    user_message_for_model = result["context"] + "\n\n" + original_user_message
else:
    user_message_for_model = original_user_message
```

Standalone mode is useful for testing the heuristics, source scoring, provider chain, and status output. For full automatic behavior you need Hermes or another host that calls `pre_llm_research_guard` before model inference.

## Quick Verification

After installation, ask a local model:

```text
Who is the mayor of Forchheim?
```

Then ask:

```text
research_guard_status
```

The status should include fields such as:

```text
version
runtime.module_version
category
visible_effect
reason_summary
visible_effect_summary
user_explanation
query_debug
source_profiles
cache
```

For a successful research turn, the answer should include a short source line such as:

```text
Quellen (Research Guard): <url 1>, <url 2>
```

## Configuration

Optional environment variables:

| Variable | Default | Description |
|---|---:|---|
| `RESEARCH_GUARD_ENABLED` | `true` | Master on/off switch |
| `RESEARCH_GUARD_ONLY_LOCAL` | `true` | Only trigger automatically for local/small model names |
| `RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS` | `false` | Allow automatic research for cloud models when a prompt would otherwise trigger |
| `RESEARCH_GUARD_LOCAL_PATTERNS` | built-in list | Comma-separated model-name patterns |
| `RESEARCH_GUARD_MODE` | `balanced` | Trigger sensitivity: `conservative`, `balanced`, or `aggressive` |
| `RESEARCH_GUARD_PROVIDER` | `auto` | Search provider: `auto`, `web_search_plus`, `brave`, `hermes`, `duckduckgo`, or `searxng` |
| `BRAVE_API_KEY` / `RESEARCH_GUARD_BRAVE_API_KEY` | empty | Brave Search API key for the `brave` provider or `auto` chain |
| `RESEARCH_GUARD_SEARXNG_URL` | empty | Base URL for a SearXNG instance |
| `RESEARCH_GUARD_MAX_RESULTS` | `5` | Search results to inject, clamped 1-10 |
| `RESEARCH_GUARD_TIMEOUT` | `8` | Direct HTTP provider timeout in seconds |
| `RESEARCH_GUARD_PROVIDER_TIMEOUT` | `8` | Overall per-provider timeout guard, including Hermes/tool providers |
| `RESEARCH_GUARD_CACHE_TTL_SECONDS` | `3600` | Default query cache TTL; `0` disables cache reads/writes |
| `RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS` | `900` | Shorter cache TTL for current/news/price/release style profiles |
| `RESEARCH_GUARD_CACHE_MAX_ENTRIES` | `200` | Maximum file-cache entries retained after cleanup, clamped 20-5000 |
| `RESEARCH_GUARD_PREFERRED_DOMAINS` | empty | Comma-separated domains to boost, for example `forchheim.de,bayern.de` |
| `RESEARCH_GUARD_BLOCKED_DOMAINS` | empty | Comma-separated domains to exclude |
| `RESEARCH_GUARD_MIN_CONFIDENCE` | `low` | Minimum source confidence required for injection: `low`, `medium`, or `high` |
| `RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES` | `false` | Downgrade confidence when fewer than two usable/unique source domains pass scoring |
| `RESEARCH_GUARD_REQUIRE_SOURCES` | `true` | Require a visible `Quellen (Research Guard):` line when fresh sources were injected |
| `RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY` | `false` | Opt-in only: inject an inactive-turn boundary for skipped/non-research turns |
| `RESEARCH_GUARD_DEEP_FETCH` | `true` | Fetch readable excerpts for structured/detail prompts |
| `RESEARCH_GUARD_DEEP_FETCH_MODE` | `structured` | `structured` or `always` |
| `RESEARCH_GUARD_DEEP_FETCH_MAX_PAGES` | `2` | Number of top scored sources to fetch, clamped 1-3 |
| `RESEARCH_GUARD_DEEP_FETCH_MAX_CHARS` | `3500` | Characters per fetched source excerpt, clamped 800-8000 |
| `RESEARCH_GUARD_DEEP_FETCH_TIMEOUT` | `5` | Timeout per fetched source in seconds |

Built-in local model patterns:

```text
qwen, ollama, llama, mistral, gemma, phi, deepseek, yi-, codellama, local,
lmstudio, mlx, gguf, vllm, tgi, kimi-k2, minimax-m2
```

Built-in local provider patterns:

```text
ollama, lmstudio, lm-studio, mlx, llama.cpp, local, vllm, tgi, goliath
```

Cloud provider/model patterns such as `openai`, `anthropic`, `gemini`, `openrouter`, `perplexity`, `gpt-`, and `claude` are skipped by default. Manual `/research` still overrides the model gate.

## Search Backends

`RESEARCH_GUARD_PROVIDER=auto` tries providers in this order:

1. `web_search_plus`, when installed
2. Brave Search, when `BRAVE_API_KEY` or `RESEARCH_GUARD_BRAVE_API_KEY` is set
3. Hermes built-in `tools.web_tools.web_search_tool`
4. SearXNG, when `RESEARCH_GUARD_SEARXNG_URL` is set
5. DuckDuckGo HTML fallback

All providers are normalized into:

```json
{"title": "...", "url": "...", "snippet": "...", "age": "..."}
```

Cache keys include provider, result count, deep-fetch profile, and normalized query text so fallback-provider results do not collide with Hermes-provider results.

## Source Quality

Research Guard ranks and annotates sources before injection.

Boosted signals include:

```text
preferred-domain, government-source, municipal-source, documentation-source,
primary-project-source, package-registry-source, vendor-source,
release-notes-source, pricing-source, standards-source, reference-source,
official-context
```

Warnings include:

```text
Forum or social source, Likely aggregator or SEO-heavy source,
Possible paywall or snippet-only source, Commercial or listicle-style source,
Undated source for current-information query, Possibly stale source
```

The injected context includes:

- `Quellenbewertung:` with confidence, score, usable-source count, evidence diversity, unique domains, and duplicate hints
- `Quellenprofile:` with active query/source profiles such as `municipal-local`, `tech-software`, `price-product`, or `news-current`
- per-source quality lines with score, confidence, domain, profiles, signals, and warnings

For local/municipal questions, city, municipality, county, government, and official administration pages are preferred. For software, version, release, API, package, or pricing prompts, official docs, project pages, package registries, release notes, vendor pages, standards pages, and pricing pages are ranked ahead of weak aggregators.

## Structured Deep Fetch

For detail-heavy prompts such as tracklists, tables, release notes, prices, benchmarks, and population facts, Research Guard fetches readable excerpts from top scored sources and injects them under:

```text
[Research Guard: Vertiefte Quellen-Auszüge]
```

Tracklist prompts have an extra rule: the model must not synthesize a list from snippets, streaming catalog mixes, anniversary editions, or bonus editions. It should use only a clearly source-backed standard/original tracklist from fetched excerpts, or say that the sources are insufficient.

## Manual Controls

Force research:

```text
#research Who is the current mayor of Forchheim?
/research Who is the current mayor of Forchheim?
```

Skip research:

```text
#no-research Who is the current mayor of Forchheim?
/no-research Who is the current mayor of Forchheim?
```

Other slash commands, such as `/status` or `/help`, are skipped by default unless `/research` explicitly forces research.

## Follow-Ups And Status

Hermes injects plugin context only ephemerally into the current user message. To make follow-up questions reliable, Research Guard stores recent decisions in memory.

Source follow-ups such as:

```text
Where did you get that from?
What were your sources?
How did you come up with that answer?
```

do not trigger a fresh search for those words. Instead, Research Guard injects a compact source-status block with the last research action, query, provider, and stored URLs.

Context/opinion follow-ups such as:

```text
What do you think about it?
What is your impression of my hometown?
```

reuse the previous Research Guard topic without searching the literal follow-up phrase. The model is instructed to separate source-backed facts from its own assessment and not invent personal details about the user.

Manual diagnostics:

```text
research_guard_status
research_guard_diagnostics
```

Status v2 includes:

```text
category, visible_effect, reason_summary, visible_effect_summary,
user_explanation, evidence, query_debug, confidence, score,
usable_result_count, blocked_result_count, evidence_diversity,
query_profiles, source_profiles, profile_coverage, warnings
```

Categories:

```text
researched_and_injected, manual_research, researched_but_not_injected,
checked_and_skipped, failed
```

Prompt previews redact emails, phone-like values, and long token-like strings.

## Privacy Boundaries

Research Guard deliberately skips prompts about:

- internal machines
- IP addresses
- hostnames
- SSH
- ping
- Tailscale
- local reachability
- service status
- files
- terminal commands
- memory
- notes
- calendars
- personal context

These prompts are not sent to external web search unless the user explicitly forces research.

Examples that should skip web search:

```text
What is the Tailscale IP of Goliath?
What is the SSH port of Ares?
Can you reach Ares?
What is the connection status to Goliath?
```

## Development

Run tests:

```bash
python3 -m unittest discover -s test -p 'test_*.py'
```

Current beta test count: `45`.

## Roadmap

The direct feature alignment with the current OpenClaw Research Guard baseline is essentially complete. Remaining work is mostly beta hardening:

- high-stakes mode for medical, legal, financial, and safety-related prompts
- AI-content-farm and shallow-content detection
- richer contradiction hints when top sources disagree
- more provider normalization tests
- optional Hermes slash command such as `/rg-status`
- integration smoke tests once Hermes exposes a stable test harness
- release checklist and public distribution polish

## License

MIT
