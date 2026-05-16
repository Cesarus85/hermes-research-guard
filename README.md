# Hermes Research Guard

**Beta release:** `v0.8.0-beta.21`

Hermes Research Guard is a lightweight pre-answer research plugin for the **Hermes Agent**. It runs a web search before Hermes lets a local or small model answer factual or current-information questions, ranks the sources, and injects a compact evidence block into the current Hermes prompt.

This package is **not a standalone application** and is not meant to be installed independently of Hermes. It requires a Hermes Agent installation with plugin support. The two supported installation paths are:

1. Hermes-initiated installation from this GitHub repository.
2. Manual command-line installation into the Hermes plugin directory.

It is designed for Hermes setups using models such as Qwen, Llama, Mistral, Gemma, Phi, Ollama-hosted models, LM Studio, vLLM, TGI, llama.cpp, MLX, or other local providers that reason well but may lack fresh facts.

## Beta Status

This repository is ready for a first public beta of the Hermes Agent plugin. The core behavior is implemented and covered by dependency-free tests, but the plugin should still be treated as experimental in production-like Hermes setups.

What is considered beta-stable:

- automatic research for local/small models
- manual `/research` and `/no-research` controls
- provider chain: optional `web_search_plus`, Brave, Hermes web search, SearXNG, DuckDuckGo HTML
- provider-aware cache keys and cache cleanup
- source scoring with official, municipal, documentation, vendor, project, package registry, release-note, pricing, standards, and reference signals
- weak-source demotion for aggregators, forums/social pages, scraper-like results, paywall/snippet-only pages, listicles, coupons, duplicate URLs, and repeated same-domain evidence
- structured deep fetch for tracklists, tables, release notes, prices, benchmarks, population facts, and other detail-heavy prompts
- optional Google Maps route context for rough route prompts, with EV charging-station and fuel-stop candidates only when requested or implied
- route follow-up handling that reuses the last route context or refreshes Google for return/recalculate requests
- `research_guard_route_test` to validate the Google Routes API key and inspect raw route diagnostics
- context follow-up handling for questions such as "Where did you get that from?" or "What do you think about it?"
- `research_guard_status` and `research_guard_diagnostics` diagnostics
- `research_guard_config` for persistent plugin configuration without editing service environment variables
- compact status explanations showing why Research Guard ran or skipped
- tests passing locally

Known beta limitations:

- Research Guard improves grounding, but it cannot guarantee truth.
- Local models can still ignore or misread injected sources.
- Trigger detection is heuristic and will never be perfect.
- High-stakes handling for medical, legal, financial, and safety-critical prompts is not finished.
- Hermes injects plugin context into the current user message, not the system prompt.
- The no-research boundary is disabled by default because some local model UIs expose injected skip-context as visible reasoning.
- There is no standalone runtime; Hermes is required for automatic operation.
- Optional Google Maps route planning is not a full EV/fuel planner and does not guarantee charger availability, fuel availability, prices, optimal stops, or vehicle-specific charge/fuel times.

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
9. Optionally fetches Google Maps Routes/Places context for route, EV charging, and fuel-stop prompts when explicitly enabled.
10. Injects a compact Research Guard context block into the current user turn.
11. Records the decision in an in-memory status buffer.

The plugin intentionally does not modify the system prompt.

## Installation

Research Guard is a Hermes Agent plugin. Do not install it as a generic Python package. Install it either through Hermes itself or manually into Hermes' plugin directory.

### Option 1: Hermes-Initiated Install

If your Hermes setup supports installing or updating plugins from a GitHub repository, give Hermes this repository URL and ask it to install or replace the `research-guard` plugin:

```text
https://github.com/Cesarus85/hermes-research-guard
```

After Hermes finishes the installation, restart the Hermes gateway if your setup does not do that automatically, then verify the installed manifest:

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
```

Expected:

```text
version: 0.8.0-beta.21
```

### Option 2: Manual Command-Line Install

Fresh manual install from GitHub:

```bash
git clone https://github.com/Cesarus85/hermes-research-guard.git
cd hermes-research-guard
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/
hermes plugins enable research-guard
hermes gateway restart
```

Manual update of an existing Hermes installation:

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
version: 0.8.0-beta.21
```

If you manage plugins manually, make sure `~/.hermes/config.yaml` contains:

```yaml
plugins:
  enabled:
    - research-guard
```

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

Research Guard can be configured in two ways:

1. Preferred for normal Hermes use: `research_guard_config`, which writes `~/.hermes/research-guard.json`.
2. Optional advanced override: environment variables.

To enable route planning through Hermes, ask the local model to call the config tool:

```text
Use research_guard_config to enable route planning.
Set google_maps_api_key to <your-google-maps-platform-key>.
Keep include_fuel_options false.
```

The persistent config file looks like this:

```json
{
  "route_planning": {
    "enabled": true,
    "google_maps_api_key": "your-google-maps-platform-key",
    "include_fuel_options": false,
    "max_charger_searches": 5,
    "max_chargers": 6,
    "max_fuel_stops": 6,
    "charger_radius_meters": 8000,
    "timeout_seconds": 8
  }
}
```

Environment variables are still supported and override config-file values when set:

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
| `RESEARCH_GUARD_ENABLE_ROUTE_PLANNING` | `false` | Enable optional Google Maps route, EV charging, and fuel-stop context for route-planning prompts |
| `GOOGLE_MAPS_API_KEY` / `RESEARCH_GUARD_GOOGLE_MAPS_API_KEY` | empty | Google Maps Platform key for the optional route-planning datasource |
| `RESEARCH_GUARD_ROUTE_TIMEOUT` | `8` | Timeout for Google Routes/Places requests in seconds |
| `RESEARCH_GUARD_ROUTE_MAX_CHARGER_SEARCHES` | `5` | Number of sampled route points to query for EV chargers, clamped 1-5 |
| `RESEARCH_GUARD_ROUTE_MAX_CHARGERS` | `6` | Maximum EV charger candidates to inject, clamped 1-12 |
| `RESEARCH_GUARD_ROUTE_MAX_FUEL_STOPS` | `6` | Maximum fuel-stop candidates to inject, clamped 1-12 |
| `RESEARCH_GUARD_ROUTE_CHARGER_RADIUS_METERS` | `8000` | Nearby-search radius for route stop candidates, clamped 1000-50000 |
| `RESEARCH_GUARD_ROUTE_INCLUDE_FUEL_OPTIONS` | `false` | Opt-in only: request `fuelOptions` fields from Places API, which may use higher-cost Places SKUs |

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

## Optional Route Planning

Hermes Research Guard can optionally use Google Maps Platform as a specialized datasource for route, traffic-duration, EV charging, and fuel-stop prompts. This is disabled by default because Google Maps Platform requires an API key and a billing-enabled project.

Enable it only after setting quotas or budgets in Google Cloud. The easiest path is the plugin config tool:

```text
Use research_guard_config with action set_route_planning, enabled true, and google_maps_api_key <your-key>.
```

Advanced service-level configuration is still possible through environment variables:

```bash
export RESEARCH_GUARD_ENABLE_ROUTE_PLANNING=true
export GOOGLE_MAPS_API_KEY="your-google-maps-platform-key"
```

One Google Maps Platform API key is enough if the key belongs to a billing-enabled Google Cloud project where both **Routes API** and **Places API (New)** are enabled. Separate keys are optional for security or quota isolation, but Hermes Research Guard only needs one configured key.

The feature currently uses:

- Routes API for driving distance, duration, traffic-aware route data, and route polyline
- Places API Nearby Search for `electric_vehicle_charging_station` candidates near sampled route points
- Places API Nearby Search for `gas_station` candidates near sampled route points

It intentionally injects guardrails into Hermes: the model is told to treat the result as a rough route and stop-candidate basis, not as a guaranteed EV or fuel planner. It must not invent exact state-of-charge curves, charger availability, fuel availability, prices, or charge/refuel times unless the user supplied enough vehicle data and the source data actually supports it.

Route/Places payloads are not written to Research Guard's persistent web-search cache. This keeps the Hermes plugin conservative with Google Maps Platform caching and storage policies. Cost control comes from explicit opt-in, per-request timeouts, a small number of sampled route points, capped EV charger candidates, capped fuel-stop candidates, and opt-in-only fuel price fields.

Stop candidates are balanced across sampled route points before they are injected. If Google only returns candidates from one sampled route area, Research Guard tells the model to say that explicitly and not to supplement missing along-route stops from training knowledge.

### Route Follow-Ups

Research Guard keeps a small in-memory snapshot of the last route result. Follow-ups such as these reuse that snapshot without a fresh Google request:

```text
Welche Ladestation würdest du bevorzugen?
```

```text
Kannst du die zweite Etappe kürzer machen?
```

```text
Was ändert sich, wenn ich nur bis 10% Akku runterfahren will?
```

Follow-ups that clearly need new route data can refresh Google Maps. Currently this includes return/reverse or explicit recalculation requests such as:

```text
Und zurück?
```

```text
Berechne die Route nochmal neu.
```

### Route Diagnostics

If a route looks implausible, validate the Google Routes API directly:

```text
Use research_guard_route_test with origin Forchheim and destination Riva del Garda.
```

The tool returns whether the configured key worked, the Routes API distance/duration, and route-shape diagnostics such as decoded polyline point count, sample coordinates, and a bounding box. If this tool fails, the key, billing, or enabled APIs are the likely issue. If this tool succeeds but the chat answer invents a strange route, the model ignored or over-interpreted the injected context.

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
