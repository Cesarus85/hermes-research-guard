# Release Notes

## v0.8.0-beta.2

This is the second public beta candidate for Hermes Research Guard. It clarifies the project scope: this repository contains a **Hermes Agent plugin**, not a standalone application.

### Highlights

- Automatic pre-answer web research for local and small LLMs.
- Local/cloud model gate with manual `/research` override.
- Provider chain with optional `web_search_plus`, Brave, Hermes web search, SearXNG, and DuckDuckGo HTML fallback.
- Provider-aware cache keys, cache cleanup, configurable cache limits, and shorter TTLs for current/news/price/release style prompts.
- Source-quality scoring with official, municipal, government, documentation, vendor, project, package registry, release-note, pricing, standards, and reference signals.
- Weak-source demotion for aggregators, forums/social pages, scraper-like results, paywall/snippet-only pages, listicles, coupons, duplicate URLs, and repeated same-domain evidence.
- Structured deep fetch for tracklists, tables, release notes, prices, benchmarks, population facts, and detail-heavy prompts.
- Query rewrites for mayors, population, versions, releases, changelogs, prices, comparisons, and current facts.
- Context/source follow-up handling so questions such as "Where did you get that from?" do not trigger a literal search for the follow-up phrase.
- Diagnostics through `research_guard_status` and `research_guard_diagnostics`.
- Compact status explanations via `reason_summary`, `visible_effect_summary`, and `user_explanation`.
- Privacy boundaries for local infrastructure, personal context, files, terminal, coding, memory, notes, and calendar prompts.

### Installation Scope

Hermes Research Guard requires Hermes Agent with plugin support. There are two supported installation paths:

1. Hermes-initiated installation from this GitHub repository.
2. Manual command-line installation into the Hermes plugin directory.

There is no standalone installation path for this variant.

### Hermes-Initiated Installation

If your Hermes setup supports installing or updating plugins from a GitHub repository, give Hermes this repository URL and ask it to install or replace the `research-guard` plugin:

```text
https://github.com/Cesarus85/hermes-research-guard
```

### Manual Command-Line Installation

```bash
git clone https://github.com/Cesarus85/hermes-research-guard.git
cd hermes-research-guard
mkdir -p ~/.hermes/plugins
cp -R research-guard ~/.hermes/plugins/
hermes plugins enable research-guard
hermes gateway restart
```

### Known Beta Limitations

- Research Guard improves grounding, but it cannot guarantee truth.
- Local models can still ignore or misread injected source context.
- Trigger detection is heuristic.
- High-stakes medical/legal/financial/safety mode is not finished.
- Hermes injects plugin context into the current user message rather than the system prompt.
- No-research boundaries are opt-in because some local model UIs expose injected skip context as visible reasoning.
- Hermes Agent is required; this variant is not a standalone Research Guard runtime.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.2
```

Expected tests:

```text
Ran 45 tests
OK
```
