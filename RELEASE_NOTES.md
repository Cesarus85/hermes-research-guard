# Release Notes

## v0.8.0-beta.16

This beta closes the remaining route-answer wording loopholes.

### Fixed

- Route course answers must now be presented only as numbered Google Routes steps.
- Local models are explicitly forbidden from creating compact highway chains such as `B470 -> A73 -> A3 -> ...`.
- Toll/vignette/Brenner/Italian toll/elevation/pass-height claims are blocked unless official data was injected.
- Charger candidates with good connector data may only be described as `plausibel zu prüfen` or `stärker belegter Kandidat`.
- Wording such as `ideal`, `best option`, `high availability`, `recommendation`, or `the ID.7 charges fast here` is explicitly blocked unless a real optimization/live source exists.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.16
```

Expected tests:

```text
Ran 71 tests
OK
```

## v0.8.0-beta.15

This beta tightens multi-stop route planning so local models cannot turn candidate chargers into invented route segments.

### Fixed

- EV/fuel stop candidates now include approximate route position metadata (`route_position`, `route_progress_percent_approx`) with explicit wording that these are search areas, not exact stop order or segment distances.
- Follow-up requests such as `mit zwei Ladestopps` now trigger a fresh Google Routes/Places refresh instead of reusing the old snapshot as if it were optimized.
- The default number of sampled route points for stop searches increased from 3 to 5.
- Route context now forbids assigning charger candidates to navigation steps, creating `Etappe 1 -> Stop -> Etappe 2` plans, or inventing segment kilometers between candidates.
- If only one relevant candidate has confirmed connector data, Hermes must say that instead of treating an unconfirmed candidate as equivalent.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.15
```

Expected tests:

```text
Ran 71 tests
OK
```

## v0.8.0-beta.14

This beta makes route-course answers functional instead of guessed.

### New

- Google Routes requests now include `routes.legs.steps.*` fields.
- Route context injects Google navigation steps with instruction, distance, and duration when available.
- Route diagnostics include the parsed step summary.

### Fixed

- Route follow-up detection now catches route-course questions such as `Streckenverlauf`, `Autobahn`, `Maut`, `Brenner`, and related wording.
- Local models are instructed to name roads, highways, junctions, intermediate places, and segment distances only from Google Routes steps.
- If no step data is present, Hermes must say that the detailed route course is not available in the Research Guard context.
- Toll, vignette, Brenner toll, Italian motorway toll, total toll, elevation, pass-height, and border-cost claims are explicitly blocked unless official data is injected.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.14
```

Expected tests:

```text
Ran 69 tests
OK
```

## v0.8.0-beta.13

This beta tightens EV route-answer discipline again.

### Fixed

- Route context now explicitly forbids invented 20-80% windows, charging minutes, target SoC, arrival SoC, charger quality, amenities, prices, and operator reliability claims.
- Start-area chargers must be treated as pre-departure options when the user starts full, not as the first route stop.
- Prompts such as `voll geladen`, `voller Akku`, `mit vollem Akku`, or `100%` are now recognized as `start_soc_percent=100`.
- Chargers without connector or power data must be described only as candidates to check, not as confirmed suitable charging stops.
- Tesla Supercharger wording now tells the model to say that VW ID.7 uses CCS and that third-party access should be checked when Research Guard did not provide explicit access data.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.13
```

Expected tests:

```text
Ran 67 tests
OK
```

## v0.8.0-beta.12

This beta adds EV range plausibility math to route context.

### Fixed

- Route context now includes a simple energy estimate when the prompt contains an EV battery size.
- The injected estimate includes the formula, a conservative consumption band, rough full-battery range, rough route energy need, and a mathematical lower bound for mid-route charging.
- Local models are instructed to use that estimate when discussing range, energy need, or rough charge-stop count.
- Common user wording such as `77 kw Batterie` is now treated as a battery-size typo, while ordinary charging-power mentions remain untouched.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.12
```

Expected tests:

```text
Ran 66 tests
OK
```

## v0.8.0-beta.11

This beta tightens route-planning answer discipline.

### Fixed

- Route context now explicitly says that Google Maps provides route data and Places candidates, not an optimized EV/fuel stop plan.
- Local models are instructed to avoid calling candidates "ideal", "optimal", or "recommended" unless Research Guard has actually computed that optimization.
- Route answers must not invent segment distances, SoC values, charging times, charging power, prices, live availability, providers, or extra stops from training knowledge.
- Route follow-ups inherit the same candidate-only rules when they reuse previous route context.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.11
```

Expected tests:

```text
Ran 63 tests
OK
```

## v0.8.0-beta.10

This beta fixes stop-candidate selection for route planning.

### Fixed

- EV charger and fuel-stop candidates are now balanced across sampled route points before injection.
- A dense cluster at the start of the route can no longer fill the entire candidate list and hide middle/end route samples.
- Route context now includes stop coverage diagnostics with sampled route-point indexes.
- Guardrails now explicitly forbid supplementing missing along-route stops from training knowledge when Google only returned candidates from one sampled route area.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.10
```

Expected tests:

```text
Ran 63 tests
OK
```

## v0.8.0-beta.9

This beta adds explicit Google Routes API diagnostics for route-planning problems.

### New

- Added `research_guard_route_test`, a manual Hermes tool that validates the configured Google Maps key against Routes API.
- The diagnostic returns distance, duration, static duration, decoded polyline point count, sampled route coordinates, and a route bounding box.
- Route context now includes route-shape diagnostics so local models are less likely to invent named detours or impossible route geography.

### Usage

```text
Use research_guard_route_test with origin Forchheim and destination Riva del Garda.
```

If this succeeds, the key can call Routes API. If chat output still claims a strange route, the model is misreading or inventing beyond the injected route context.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.9
```

Expected tests:

```text
Ran 61 tests
OK
```

## v0.8.0-beta.8

This beta adds route follow-up handling.

### New

- Research Guard now stores a small in-memory snapshot of the last route result.
- Route follow-ups such as `Welche Ladestation würdest du bevorzugen?` reuse the previous route context without a fresh Google request.
- Return/reverse or explicit recalculation follow-ups such as `Und zurück?` can trigger a fresh Google Routes/Places request.
- Status diagnostics now distinguish `route-followup-context` from `route-planning-followup-refresh`.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.8
```

Expected tests:

```text
Ran 58 tests
OK
```

## v0.8.0-beta.7

This beta makes route planning more flexible.

### Changed

- Clear route prompts now trigger route planning even without explicit charging or fuel-stop wording.
- EV charger candidates are only fetched when EV/charging/battery context is present.
- Fuel-stop candidates are only fetched when fuel/tank-stop context is present.
- Generic vehicle hints such as `mit einem VW Golf` are retained as route context without forcing charger or fuel-stop searches.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.7
```

Expected tests:

```text
Ran 56 tests
OK
```

## v0.8.0-beta.6

This beta fixes an EV route-planning trigger gap.

### Fixed

- Route prompts that mention an EV model and battery size, such as `VW ID 7 mit 77 kWh Batterie`, now trigger route planning even when the user does not explicitly say `E-Auto` or `Ladeplanung`.
- Route planning now extracts additional useful hints: battery size, vehicle hint, passenger count, and loaded-vehicle wording.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.6
```

Expected tests:

```text
Ran 53 tests
OK
```

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
