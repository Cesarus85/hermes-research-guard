# Hermes Research Guard Roadmap

Stand: 2026-05-10

This roadmap tracks which features from `Cesarus85/openclaw-research-guard` can be brought into `Cesarus85/hermes-research-guard`, and where Hermes requires a different implementation.

## Legend

| Mark | Meaning |
|---|---|
| `[x]` | Already present in Hermes Research Guard |
| `[ ] PORT` | Directly portable from the OpenClaw version |
| `[ ] ADAPT` | Portable, but must be adapted to Hermes APIs or behavior |
| `[ ] CHECK` | Needs verification against current Hermes runtime behavior |
| `[ ] LIMIT` | Not portable 1:1 because Hermes does not expose the same surface |

## Hermes Compatibility Notes

Hermes currently supports the most important mechanism for Research Guard: a `pre_llm_call` hook can return `{"context": "..."}` or a plain string, and Hermes injects that text into the current turn's user message.

Important difference from OpenClaw: Hermes intentionally injects plugin context into the user message, not the system prompt. Therefore OpenClaw features based on `appendSystemContext` must be rewritten as strong, explicit instructions inside the injected Research Guard context block.

Hermes also makes injected `pre_llm_call` context ephemeral, so it is not persisted to the session database. This reduces the stale-context problem, but the plugin should still include clear current-turn boundaries in injected context.

## Portability Matrix

| OpenClaw feature | Hermes status | Notes |
|---|---|---|
| Pre-answer research hook | `[x]` | Hermes `pre_llm_call` is the equivalent of OpenClaw `before_prompt_build`, with user-message context injection. |
| Manual `research_guard_search` tool | `[x]` | Present in v0.1, but provider normalization and scoring still need parity. |
| Manual `#research` / `/research` force prefix | `[x]` | Present and consistent. |
| Manual `#no-research` / `/no-research` skip prefix | `[x]` | Present and consistent. |
| Basic local model detection | `[x]` | Present, but OpenClaw has stronger provider-aware logic. |
| Provider-aware local/cloud model gate | `[ ] PORT` | Add local provider patterns, cloud provider patterns, explicit `:cloud` handling, and `allowCloudResearchTriggers`. |
| Brave Search provider | `[ ] PORT` | Add direct Brave API via `BRAVE_API_KEY`. |
| OpenClaw web-search registry integration | `[ ] ADAPT` | Replace with Hermes tool dispatch or built-in `tools.web_tools` / `web_search` path. |
| DuckDuckGo HTML fallback | `[x]` | Present; keep as final fallback. |
| Provider fallback chain | `[ ] ADAPT` | Preferred Hermes order: optional `web_search_plus`, direct Brave, Hermes built-in web search, DuckDuckGo/SearXNG. |
| Query cache with TTL | `[x]` | Present, file-backed. Needs provider-aware keys and cache cleanup. |
| Provider-aware cache keys | `[ ] PORT` | OpenClaw does this better; add provider, result count, deep-fetch flags. |
| Trigger heuristics for factual/current questions | `[x]` | Present in simpler form. Port the expanded German/English rules. |
| Skip rules for code/files/terminal/memory/personal tasks | `[x]` | Present in simpler form. Port the expanded OpenClaw skip list. |
| Local infrastructure skip rules | `[x]` | Skips IP, host, SSH, Tailscale, ping, local reachability, and service-status prompts. |
| Speech wrapper cleanup | `[x]` | Strips `Audio:`, `Voice:`, `Transkript:`, `Sprachnachricht:` before classification and query building. |
| OpenClaw metadata cleanup | `[ ] LIMIT` | OpenClaw-specific metadata is not relevant unless Hermes gains equivalent wrappers. |
| Follow-up subject carryover | `[ ] PORT` | Hermes receives `conversation_history`, so prior subject extraction is portable. |
| Structured deep fetch | `[ ] PORT` | Fetch top-page excerpts for detail-heavy prompts such as tracklists, tables, release notes, prices, and population facts. |
| Source quality scoring | `[ ] PORT` | Port official/docs/government/vendor/project/freshness scoring. |
| Confidence gating | `[ ] PORT` | Add `minConfidence`, `requireMultipleSources`, usable-source count, and injection blocking. |
| Preferred domains | `[ ] PORT` | Add env/config support for boosted domains. |
| Blocked domains | `[ ] PORT` | Add env/config support for excluded domains. |
| Duplicate and same-domain dampening | `[ ] PORT` | Prevent one domain or duplicate snippets from looking like independent evidence. |
| Freshness scoring | `[ ] PORT` | Warn/downgrade stale or undated sources for current-information queries. |
| Strict location-answer grounding | `[ ] ADAPT` | Put this in the injected context block, because Hermes does not expose plugin system-prompt injection. |
| Required Research Guard source line | `[ ] ADAPT` | Add instruction inside context block, optionally controlled by `RESEARCH_GUARD_REQUIRE_SOURCES`. |
| No-research stale-context boundary | `[ ] ADAPT` | Hermes context is ephemeral, but a skipped-turn boundary can still help local models. |
| `research_guard_status` tool | `[x]` | Added in-memory decision buffer with recent actions, reasons, provider, query, cache flag, and stored source summaries. |
| Status response policy | `[ ] ADAPT` | Implement as tool output text and/or context instruction; no system-prompt policy hook. |
| Debug mode | `[ ] PORT` | Add `RESEARCH_GUARD_DEBUG=1` and compact decision explanations. |
| Tests | `[ ] PORT` | Initial dependency-free Python tests exist for the v0.4 privacy-skip port; broader OpenClaw parity coverage remains. |

## v0.2 - Provider And Search Backend Parity

Goal: make Hermes Research Guard search through the best available provider path, while retaining a no-key fallback.

- [ ] PORT Add first-class Brave Search support via `BRAVE_API_KEY`.
- [ ] PORT Add `RESEARCH_GUARD_PROVIDER=auto|brave|hermes|duckduckgo|searxng`.
- [ ] ADAPT Detect and optionally use `web_search_plus` when installed.
- [ ] ADAPT Prefer Hermes built-in web search through safe tool dispatch where available.
- [ ] PORT Keep DuckDuckGo HTML as final fallback.
- [ ] PORT Normalize all provider results into `{title, url, snippet, age}`.
- [ ] PORT Surface provider name, fallback path, and errors in debug/status output.
- [ ] PORT Make cache keys provider-aware.
- [ ] PORT Include search count, deep-fetch state, and provider in cache keys.

## v0.3 - Model Gate And Trigger Parity

Goal: reduce over-searching while making factual-risk prompts more reliable for local models.

- [ ] PORT Port OpenClaw local provider patterns: `ollama`, `lmstudio`, `lm-studio`, `mlx`, `llama.cpp`, `local`, `vllm`, `tgi`, `goliath`.
- [ ] PORT Port cloud provider patterns: `openai`, `anthropic`, `gemini`, `google`, `openrouter`, `perplexity`, `moonshot`, `kimi`, `minimax`, `synthetic`, `zai`.
- [ ] PORT Treat explicit cloud markers such as Ollama `:cloud` as non-local.
- [ ] PORT Add `RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS=true|false`.
- [ ] PORT Add mode setting: `RESEARCH_GUARD_MODE=conservative|balanced|aggressive`.
- [ ] PORT Expand factual/current trigger patterns for German and English prompts.
- [ ] PORT Add explicit triggers for population, mayors, presidents, releases, prices, versions, changelogs, and comparisons.
- [x] Make `/research` and `/no-research` behave the same as `#research` and `#no-research`.

## v0.4 - Skip Rules And Privacy Boundaries

Goal: avoid leaking local/private prompts into web search.

- [x] Skip coding, scripting, repo, file, workspace, terminal, shell, and git tasks.
- [x] Skip personal memory, calendar, mail, notes, and "what did I say earlier" prompts.
- [x] Skip local infrastructure questions: IP address, hostname, host, port, SSH, ping, Tailscale, LAN, local reachability, service status.
- [x] Skip slash-command tasks unless manually forced.
- [x] Strip speech wrappers before classification and query building.
- [ ] ADAPT Add Hermes-specific wrapper cleanup if gateway/transcription text adds stable metadata.
- [ ] PORT Redact prompt previews in diagnostics: emails, phone-like numbers, long tokens.
- [x] Document privacy implications of automatic external search.

## v0.5 - Query Quality

Goal: turn conversational prompts into search-friendly queries without losing user intent.

- [x] Strip manual research prefixes before search.
- [x] Strip stale `[Research Guard: ...]` blocks before search.
- [ ] PORT Carry prior subject into follow-up queries when prompts use pronouns or demonstratives.
- [ ] PORT Add subject extraction for identity, location, and named-entity questions.
- [ ] ADAPT Use Hermes `conversation_history` for follow-up subject extraction.
- [ ] PORT Add deterministic rewrite templates for latest/current/release/version/price prompts.
- [ ] PORT Add official-source hints for docs, changelogs, pricing pages, government/statistics pages, and municipal facts.
- [ ] PORT Expose original prompt, cleaned prompt, carried subject, and final query in debug/status output.

## v0.6 - Source Quality And Confidence

Goal: only inject research context when sources are useful enough to improve the answer.

- [ ] PORT Score every search result before injection.
- [ ] PORT Prefer preferred domains, government domains, municipal sources, documentation pages, vendor/project sources, package registries, GitHub/GitLab, Wikipedia/Wikidata where appropriate.
- [ ] PORT Demote missing snippets, forums/social sources, SEO aggregators, scraper pages, paywalls, listicles, coupons, and weak commercial pages.
- [ ] PORT Add `RESEARCH_GUARD_MIN_CONFIDENCE=low|medium|high`.
- [ ] PORT Add `RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES=true|false`.
- [ ] PORT Add `RESEARCH_GUARD_PREFERRED_DOMAINS=...`.
- [ ] PORT Add `RESEARCH_GUARD_BLOCKED_DOMAINS=...`.
- [ ] PORT Detect duplicate URLs, near-duplicate snippets, and same-domain clusters.
- [ ] PORT Track evidence diversity: `low|medium|high`.
- [ ] PORT Add freshness scoring for current-information prompts.
- [ ] PORT Warn on stale or undated current-information sources.
- [ ] PORT Block injection when no usable sources pass scoring.
- [ ] PORT Block injection when confidence is below the configured minimum.

## v0.7 - Structured Deep Fetch

Goal: give local models enough detail for prompts where snippets are not enough.

- [ ] PORT Add `RESEARCH_GUARD_DEEP_FETCH=true|false`.
- [ ] PORT Add `RESEARCH_GUARD_DEEP_FETCH_MODE=structured|always`.
- [ ] PORT Add `RESEARCH_GUARD_DEEP_FETCH_MAX_PAGES`, clamped 1-3.
- [ ] PORT Add `RESEARCH_GUARD_DEEP_FETCH_MAX_CHARS`, clamped 800-8000.
- [ ] PORT Add `RESEARCH_GUARD_DEEP_FETCH_TIMEOUT_SECONDS`.
- [ ] PORT Trigger deep fetch for tracklists, complete lists, tables, release notes, versions, prices, benchmarks, population, and detailed factual prompts.
- [ ] PORT Fetch top pages in parallel with per-page timeout.
- [ ] PORT Extract readable text from HTML and plain text responses.
- [ ] PORT Keep fetched excerpts only for sources that passed quality scoring.

## v0.8 - Answer Discipline For Hermes Context Injection

Goal: compensate for Hermes user-message injection by making the context block explicit and self-contained.

- [ ] ADAPT Rewrite OpenClaw `buildSystemInstruction()` into a Hermes-safe injected instruction section.
- [ ] ADAPT Rewrite OpenClaw `buildNoResearchSystemInstruction()` into an optional Hermes skipped-turn boundary.
- [ ] ADAPT In injected context, require the model to answer only the current user question.
- [x] In injected context, tell the model that Research Guard sources are evidence and should be cited when present.
- [ ] ADAPT Require uncertainty when sources are missing, weak, stale, or contradictory.
- [x] Add final line instruction: `Quellen (Research Guard): <URL 1>, <URL 2>`.
- [ ] ADAPT Add `RESEARCH_GUARD_REQUIRE_SOURCES=true|false`.
- [ ] ADAPT Add strict location-question rule: no rivers, traffic routes, population, distances, or extra facts unless asked and source-backed.
- [ ] LIMIT Do not attempt true plugin system-prompt injection unless Hermes exposes a supported API for it.

## v0.9 - Observability And Status Tools

Goal: make every Research Guard decision inspectable.

- [x] Add in-memory decision ring buffer.
- [x] Cap decision history, default 30 entries.
- [x] Record action: `injected`, `skipped`, `failed`, and `manual_search`.
- [ ] PORT Record reason, provider, query, model, prompt preview, cache hit, and source summaries; richer confidence/score fields remain for source-scoring work.
- [x] Add `research_guard_status` tool.
- [ ] ADAPT Add optional Hermes slash command `/research_guard_status` or `/rg-status`.
- [ ] PORT Add diagnostic categories: `researched_and_injected`, `manual_research`, `researched_but_not_injected`, `checked_and_skipped`, `failed`.
- [ ] PORT Add visible effect: `sources_injected`, `manual_tool_result`, `none`, `error`.
- [ ] ADAPT Keep status output diagnostic-only through tool text and clear schema description.
- [ ] PORT Add compact non-technical explanation for "why did this run?".

## v0.10 - Cache And Performance Hardening

Goal: keep the hook fast and predictable.

- [x] Basic file-backed query cache with TTL.
- [ ] PORT Add maximum cache size.
- [ ] PORT Add cleanup/eviction of old entries.
- [ ] PORT Keep provider-aware cache keys.
- [ ] PORT Expose cache entries, TTL, hits, and misses through status/debug output.
- [ ] ADAPT Consider shorter TTL for current/news prompts and longer TTL for stable factual prompts.
- [ ] PORT Bound all provider and deep-fetch calls with explicit timeouts.
- [ ] CHECK Verify Hermes hook latency behavior in CLI and gateway sessions.

## v0.11 - Domain-Specific Modes And High-Stakes Handling

Goal: make source ranking sensitive to topic risk.

- [ ] PORT Tech/software mode: prefer official docs, GitHub/GitLab, package registries, changelogs, release notes.
- [ ] PORT Municipal/local-facts mode: prefer city, municipality, county, government, and official administration pages.
- [ ] PORT Price/product mode: prefer official pricing, vendor pages, stores, and recent pages.
- [ ] PORT News/current mode: prefer fresh and dated sources.
- [ ] PORT Medical/legal/financial mode: require stronger confidence and explicit uncertainty.
- [ ] PORT Add high-stakes warning when sources are weak or insufficient.
- [ ] PORT Document that Research Guard improves grounding but cannot guarantee truth.

## v0.12 - Tests And Release Quality

Goal: make future changes safe.

- [ ] PORT Translate OpenClaw heuristic tests into Python tests.
- [ ] PORT Add tests for model detection, cloud markers, manual force/skip, and cloud-trigger escape hatch.
- [x] Add tests for local infrastructure skip rules.
- [x] Add tests for speech-wrapper cleanup.
- [ ] PORT Add tests for follow-up subject carryover.
- [ ] PORT Add tests for source scoring and confidence gates.
- [ ] PORT Add tests for duplicate/same-domain dampening.
- [ ] PORT Add tests for freshness/staleness scoring.
- [ ] PORT Add tests for provider normalization.
- [ ] ADAPT Add integration smoke test for Hermes `pre_llm_call` context injection if a stable test harness exists.
- [ ] ADAPT Add GitHub Actions lint/test workflow once the project has a test runner.

## v1.0 - Documentation And Distribution

Goal: make the plugin installable, understandable, and safe to operate.

- [ ] ADAPT Update README with Hermes-specific architecture notes.
- [ ] ADAPT Document that Hermes injects plugin context into the user message, not system prompt.
- [ ] PORT Add example configs for local-only, voice/STT, stricter citation-first, and gateway-heavy setups.
- [ ] PORT Add troubleshooting for provider keys, plugin enablement, gateway restart, and model detection.
- [ ] PORT Add demo script: current fact, local-infra skip, status output.
- [ ] PORT Add release checklist and semantic versioning.
- [ ] PORT Add changelog entries for each roadmap milestone.
- [ ] CHECK Confirm current Hermes plugin/community distribution path.

## Explicit Non-Goals For Now

- [ ] LIMIT True plugin-side system prompt rewriting. Hermes reserves the system prompt for core internals and currently routes plugin context through the current user message.
- [ ] LIMIT OpenClaw-specific `runtime.webSearch` integration. Hermes should use Hermes-native tools/providers instead.
- [ ] LIMIT OpenClaw metadata/XML wrapper normalization unless equivalent Hermes wrappers appear in real gateway transcripts.
- [ ] LIMIT Guaranteed model obedience. Research Guard can provide evidence and instructions, but local models may still ignore context; status and confidence tools should make that visible.
