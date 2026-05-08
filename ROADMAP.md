# Roadmap

This roadmap collects planned improvements for **Hermes Research Guard**.  
Tick items off as they land.

## v0.2 — Provider Upgrade

- [ ] Add first-class Brave Search support via `BRAVE_API_KEY`.
- [ ] Add `RESEARCH_GUARD_PROVIDER=brave|auto|hermes|duckduckgo`.
- [ ] Prefer Brave when configured, because it is Stefan's preferred provider.
- [ ] Detect and optionally use `web_search_plus` when installed.
- [ ] Implement provider fallback chain:
  - [ ] `web_search_plus` with `provider="brave"`
  - [ ] direct Brave Search API
  - [ ] Hermes built-in `web_search`
  - [ ] DuckDuckGo/SearXNG fallback
- [ ] Normalize provider results into one internal result format.
- [ ] Surface provider name in injected context and debug output.

## v0.3 — Query Quality

- [ ] Add query rewrite before search.
- [ ] Detect language and preserve German/English intent.
- [ ] Shorten conversational questions into search-friendly queries.
- [ ] Add current-year/latest/release keywords for time-sensitive questions.
- [ ] Add domain-aware query hints for tech, health, prices, law/tax, and news.

## v0.4 — Confidence & Source Ranking

- [ ] Score result quality before injecting context.
- [ ] Skip injection when search results look weak, spammy, or irrelevant.
- [ ] Prefer official sources, documentation, Wikipedia/Wikidata, reputable news, and GitHub for tech topics.
- [ ] De-prioritize forums/Reddit unless explicitly useful.
- [ ] Detect source agreement across multiple results.
- [ ] Include compact confidence metadata in debug mode.

## v0.5 — Anti-Oversearch

- [ ] Distinguish static knowledge, semi-static knowledge, and current/factual-risk questions.
- [ ] Avoid searching for simple math, basic explanations, writing tasks, code tasks, and personal/local context.
- [ ] Add stricter trigger modes: `conservative`, `balanced`, `aggressive`.
- [ ] Support per-model policies, e.g. Qwen aggressive, Llama balanced, cloud models off.

## v0.6 — Cache & Performance

- [x] Add basic query cache with TTL.
- [ ] Make cache provider-aware.
- [ ] Add cache size limit / cleanup.
- [ ] Add stale-while-revalidate option for repeated questions.
- [ ] Keep hook latency bounded with explicit provider timeouts.

## v0.7 — Citations & Answer Discipline

- [ ] Inject citation instructions when research context is provided.
- [ ] Ask the model to cite only sources present in the injected context.
- [ ] Add optional source numbering format.
- [ ] Add `RESEARCH_GUARD_REQUIRE_SOURCES=true|false`.
- [ ] Warn when the model should say it could not verify something.

## v0.8 — Manual Controls & Debugging

- [x] Add `#research` force-research prefix.
- [x] Add `#no-research` skip prefix.
- [ ] Add debug mode via `RESEARCH_GUARD_DEBUG=1`.
- [ ] Explain trigger decision: model match, question match, skip rules, provider choice.
- [ ] Add `research_guard_status` tool.
- [ ] Add `research_guard_why` tool or command for last decision.

## v0.9 — Domain-Specific Modes

- [ ] Tech mode: prefer official docs, GitHub, changelogs, release notes.
- [ ] Medical/health mode: prefer official and reputable medical sources; avoid weak blogs.
- [ ] News mode: prefer recent sources and provider time filters.
- [ ] Price/product mode: prefer official pages, shops, and current review sources.
- [ ] Law/tax mode: prefer official government/legal sources.

## v1.0 — Polish & Distribution

- [ ] Add tests for trigger heuristics and skip rules.
- [ ] Add tests for provider normalization.
- [ ] Add example config snippets.
- [ ] Add screenshots/log examples of injected context.
- [ ] Add release notes and semantic versioning.
- [ ] Add GitHub Actions lint/test workflow.
- [ ] Submit/list in Hermes plugin/community directories if appropriate.
