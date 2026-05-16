# Release Notes

## v0.8.0-beta.5

This beta makes optional route planning much easier to enable in Hermes. Operators no longer need to place environment variables in the correct gateway start context.

### New

- Added `research_guard_config`, a Hermes tool for viewing and updating persistent Research Guard config.
- Added persistent config file support at `~/.hermes/research-guard.json`.
- Added plugin-local config fallback support via `research-guard/config.json`.
- Added `research-guard/config.example.json`.
- Route planning can now be enabled by asking Hermes to call `research_guard_config` with `enabled=true` and a Google Maps Platform key.
- `research_guard_status` now reports route config paths and whether a config file is present.

### Simple Route Planning Setup

Ask Hermes:

```text
Use research_guard_config to enable route planning.
Set google_maps_api_key to <your-google-maps-platform-key>.
Keep include_fuel_options false.
```

Then verify:

```text
research_guard_status
```

Expected route-planning status:

```json
{
  "enabled": true,
  "api_key_configured": true
}
```

Environment variables remain supported and override file config when set.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.5
```

Expected tests:

```text
Ran 52 tests
OK
```

## v0.8.0-beta.4

This beta extends optional Google Maps route planning with fuel-stop candidates. The plugin remains a **Hermes Agent plugin only**; there is no standalone runtime or standalone installation path.

### New

- Fuel-stop route context for prompts that ask for tank stops, gas stations, or fuel planning.
- Google Places API Nearby Search integration for `gas_station` candidates near sampled route points.
- Optional `RESEARCH_GUARD_ROUTE_INCLUDE_FUEL_OPTIONS=false` guard. Fuel price/options fields are off by default because they can trigger higher-cost Places SKUs.
- Route diagnostics now include `fuel_stop_candidate_count`, `max_fuel_stops`, and `include_fuel_options`.

### API Key

One Google Maps Platform API key is enough for Hermes Research Guard if the key belongs to a billing-enabled Google Cloud project where both **Routes API** and **Places API (New)** are enabled. Separate keys are optional for tighter security or quota isolation, but not required by the plugin.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.4
```

Expected tests:

```text
Ran 50 tests
OK
```

## v0.8.0-beta.3

This beta adds an optional Google Maps route-planning datasource for Hermes Research Guard. The plugin is still a **Hermes Agent plugin only**; there is no standalone runtime or standalone installation path.

### New

- Optional route-planning trigger for prompts that ask for route, driving, or EV charging planning.
- Google Routes API integration for driving distance, traffic-aware duration, static duration, and route polyline.
- Google Places API Nearby Search integration for EV charging-station candidates near sampled route points.
- Route-planning diagnostics in `research_guard_status`, including enabled state, key configuration, persistent-cache status, sampled charger searches, max injected chargers, and search radius.
- Route-specific guardrails telling the model to avoid inventing exact SoC curves, charger availability, prices, optimal stops, or charge times.
- No persistent storage of Google Routes/Places payloads in the Research Guard web-search cache.

### Disabled By Default

The route-planning datasource is off by default:

```bash
export RESEARCH_GUARD_ENABLE_ROUTE_PLANNING=true
export GOOGLE_MAPS_API_KEY="your-google-maps-platform-key"
```

Google Maps Platform generally requires a billing-enabled Google Cloud project. For low usage, requests may fit within Google Maps Platform monthly free usage caps, but operators should still set quotas and budgets before enabling this feature.

Route/Places payloads are not persisted by Research Guard. Cost control is handled through explicit opt-in, per-request timeouts, sampled route points, and capped charger candidates.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.3
```

Expected tests:

```text
Ran 49 tests
OK
```

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
