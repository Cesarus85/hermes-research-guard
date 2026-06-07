# Release Notes

## v0.8.0-beta.34

This beta improves municipal factual follow-ups such as asking for a city's population after asking where the city is located.

### Fixed

- Subject follow-ups such as `und wieviele Einwohner hat die Stadt?` now recognize city/town wording as a follow-up subject reference.
- When Hermes does not pass conversation history into the hook, Research Guard can carry the subject from the last Research Guard decision buffer.
- Municipal population queries now run targeted supplemental searches for official city, city portrait, and state-statistics pages.
- This reduces generic population-source drift such as returning broad Destatis pages or unrelated city-statistics pages for a Forchheim follow-up.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.34
```

Expected tests:

```text
Ran 98 tests
```

## v0.8.0-beta.33

This beta adds high-stakes legal, financial, and broad safety handling on top of the existing health/food-allergen mode.

### Improved

- Legal, financial, and broad safety prompts can now trigger Research Guard even when framed personally.
- Provider queries are sanitized toward general official-source terms rather than personal details.
- Source scoring adds `legal-official`, `financial-official`, and `safety-official` profiles.
- High-stakes prompts now require at least medium confidence before context injection.
- Weak or insufficient official source support is surfaced as a high-stakes warning.
- Injected context adds guardrails against individual legal, tax, investment, insurance, or risky emergency/self-repair advice.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.33
```

Expected tests:

```text
Ran 96 tests
```

## v0.8.0-beta.32

This beta hardens provider result normalization and freshness/staleness scoring coverage.

### Improved

- Provider result normalization now accepts additional common aliases such as `display_title`, `sourceUrl`, `canonicalUrl`, `body`, `excerpt`, `abstract`, `publishedAt`, and `datePublished`.
- Nested provider payloads such as `data.web.results` are now recursively extracted instead of being ignored.
- Current-information scoring has fuller tests for fresh, stale, and undated sources.
- Route wording hardening and the GitHub Actions unit-test workflow from the previous hardening commit are included in this beta.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.32
```

Expected tests:

```text
Ran 93 tests
```

## v0.8.0-beta.31

This beta tightens the local chat/meta boundary for conversation corrections and Research Guard meta questions.

### Fixed

- Conversation-correction prompts no longer trigger public-topic web research.
- Research Guard meta questions such as `Was hat Research Guard da zu suchen?` now skip with `research-guard-meta`.
- Prompts such as `Wie kommst du darauf ... wenn ich schreibe ...` now skip with `conversation-correction`.
- The diagnostic query plan no longer labels these local chat/meta questions as `public-factual-topic`.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.31
```

Expected tests:

```text
Ran 90 tests
```

## v0.8.0-beta.30

This beta tightens the local/private boundary after the broad public-topic trigger introduced in v0.8.0-beta.29.

### Fixed

- Hermes Memory cleanup and maintenance prompts no longer trigger web research.
- Prompts such as `Schau in deinem Memory was gelöscht werden kann` now skip with `local-memory-task`.
- The public factual topic-shift trigger remains active for real public subjects, but it no longer treats local Memory, notes, or reminder-maintenance tasks as public topics.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.30
```

Expected tests:

```text
Ran 88 tests
```

## v0.8.0-beta.29

This beta generalizes stale-context protection beyond tech/product prompts.

### Fixed

- New standalone public factual questions can now trigger fresh research across domains, not only technology.
- Public topic-shift detection covers named or domain-specific questions about products, films, music, politics, places, companies, science, food, sports, and similar subjects.
- Conversational personal phrasing such as `in meinen Augen`, `ich finde`, or `obwohl ich das anders sehe` is removed from the provider query when the topic is public.
- Private memory questions such as `Was ist meine Heimatstadt?` and `Wie heißt meiner Meinung nach die beste Stadt?` still skip web research.
- The injected context includes a topic-shift guardrail telling the model not to reuse Research Guard sources, status data, or conclusions from unrelated previous turns.

### Examples

These now trigger `public-factual-topic` rather than relying on stale previous context:

```text
Warum ist Oppenheimer in meinen Augen so populär geworden?
Warum wird Meteora oft mit Hybrid Theory verglichen, obwohl ich das anders sehe?
Ist der Thermomix TM7 wirklich besser als der TM6 oder ist das Marketing?
```

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.29
```

Expected tests:

```text
Ran 87 tests
```

## v0.8.0-beta.28

This beta fixes stale-context failures for public tech/product questions after an unrelated researched turn.

### Fixed

- `Woher kommt ...` is no longer treated as a source-follow-up unless it asks where the answer, source, or information came from.
- Public tech/product prompts now trigger fresh research for topics such as NVIDIA DGX Spark, Mac Studio, LLM inference, tuning, CUDA, TensorRT-LLM, NIM, vLLM, Unified Memory, VRAM/RAM, model-size claims, specs, benchmarks, and hardware corrections.
- Conversational phrasing such as `in my eyes` / `in meine Augen` no longer causes a public tech/product query to be skipped as personal context.
- Product/spec prompts rewrite to compact search queries containing the public product and technical terms rather than stale previous-topic context.
- The injected context now includes a tech/product guardrail: do not reuse old Research Guard sources from unrelated topics, and do not guess specs such as Unified Memory, VRAM, RAM, or model capacity when sources do not support them.

### Example

This now triggers fresh Research Guard context:

```text
Warum verwenden immer mehr Leute den NVIDIA DGX Spark für LLM Inferencing, obwohl er eher für Tuning gedacht ist. Woher kommt die Popularität, die in meine Augen einem Mac Studio Konkurrenz macht?
```

and rewrites to a tech/product query shape such as:

```text
NVIDIA DGX Spark Grace Blackwell Mac Studio Apple Silicon LLM inference inferencing fine-tuning tuning popularity market adoption comparison official specs benchmarks technical analysis
```

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.28
```

Expected tests:

```text
Ran 84 tests
```

## v0.8.0-beta.27

This beta adds a first high-stakes health/food-allergen trigger for questions that contain personal framing.

### Fixed

- Health and food-allergen prompts now override the personal/private skip when the factual question is about allergies, allergens, food labelling, symptoms, diagnosis, treatment, or similar health-safety topics.
- Provider queries are sanitized: personal framing such as family relationships or age is not sent to web search.
- Sellerie/celery allergy and EU food-allergen labelling prompts rewrite to official medical and food-safety search terms.
- Health/food-safety sources receive a dedicated source profile and scoring boost.
- The injected context now includes a health/safety rule: answer cautiously, give general information only, avoid diagnosis or individual medical advice, and refer to medical/allergological clarification or emergency planning when appropriate.

### Example

This prompt now triggers Research Guard automatically:

```text
Die Freundin meines Sohnes ist allergisch gegen Sellerie. Ist Sellerie oft in Lebensmitteln drin?
```

but the search provider receives a general query shape such as:

```text
Sellerie Celery Allergie Allergen Anaphylaxie EU Allergenkennzeichnung Lebensmittel Zutaten Pflichtkennzeichnung offizielle Informationen medizinische Quellen
```

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.27
```

Expected tests:

```text
Ran 82 tests
```

## v0.8.0-beta.26

This beta generalizes contextual factual follow-ups beyond animal questions.

### Fixed

- Follow-ups such as `Welche Alternativen gibt es?`, `Gib mir konkrete Beispiele`, `Nenn mir konkrete Vorteile und Nachteile`, `Erkläre Details`, or `Liste Risiken` can now reuse the previous researched subject.
- The model context now includes a dedicated contextual-follow-up guardrail telling Hermes to answer the current follow-up while staying on the carried topic.
- Rabbit/hare handling remains as a specialized extra layer, but the core follow-up carryover is domain-independent.

### Examples

After:

```text
Welche Version von Python ist aktuell?
```

the follow-up:

```text
Welche Alternativen gibt es?
```

is searched with `Python` carried into the query.

After:

```text
Was kostet ChatGPT Team?
```

the follow-up:

```text
Nenn mir konkrete Vorteile und Nachteile.
```

is searched with `ChatGPT Team` carried into the query.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.26
```

Expected tests:

```text
Ran 80 tests
```

## v0.8.0-beta.25

This beta fixes context-dependent factual follow-ups that ask for concrete examples, breeds, variants, or options after a previous researched topic.

### Fixed

- Follow-ups such as `Gib mir konkrete Rassen` can now reuse the previous researched subject instead of being treated as an isolated generic query.
- Rabbit/hare care questions now rewrite into rabbit-specific breed/care queries with `Kaninchen`, `Kaninchenrassen`, `Haltung`, `Gesundheit`, `Qualzucht`, and `artgerecht`.
- Rabbit/hare prompts now demote off-topic dog or family-dog results, which prevents search providers from drifting into `Familienhunde` results when the user meant rabbits.
- The injected context includes an animal-care rule telling the model not to use dog/family-dog results for rabbit/hare questions and not to add child/family suitability unless asked.

### Example

After:

```text
Was gibt es bei der Haltung von Schlappohrhasen zu beachten?
```

the follow-up:

```text
Ja, es war auf Hasen bezogen. Gib mir konkrete Rassen.
```

is now searched as a rabbit/kaninchen breed and care query, not as a generic breed or dog/family-pet query.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.25
```

Expected tests:

```text
Ran 79 tests
```

## v0.8.0-beta.24

This beta fixes the remaining Brave-provider failure mode for municipal office questions.

### Fixed

- Municipal office rewrites now include gendered office terms, `Stadtspitze`, `Amtsinhaber`, and `aktuell`.
- Bürgermeister/Oberbürgermeister/Landrat questions now run targeted supplemental office queries before scoring.
- Supplemental results are merged with the provider's original result set so current primary-office pages can compete against official deputy, representative, or stale pages.

### Example

If Brave initially returns only `Bürgermeister Udo Schönfelder` and an old `Oberbürgermeister` page for Forchheim, Research Guard now also asks for current primary-office pages such as `Oberbürgermeisterin ... Stadtspitze ... aktuell` before ranking.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.24
```

Expected tests:

```text
Ran 78 tests
```

## v0.8.0-beta.23

This beta adds role and variant disambiguation for provider-dependent search result ordering.

### Fixed

- Municipal office questions now distinguish primary current offices from deputy, second, substitute, candidate, interim, and former roles.
- Generic role-sensitive questions now get similar safeguards for company leadership, sports roles, universities, churches, courts, organizations, and political offices.
- Version, release, and tracklist questions now mark beta/preview/nightly/RC and deluxe/bonus/anniversary/live/EP variants as related variants rather than primary answers.
- The injected context now includes role/office and variant rules so local models explain mixed evidence instead of treating a related official page as the main answer.

### Example

For a query such as `Wer ist Bürgermeister von Forchheim?`, an official `zweiter Bürgermeister` or `Vertretungsfall` page is no longer treated as equivalent to the current `Oberbürgermeisterin` page.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.23
```

Expected tests:

```text
Ran 77 tests
```

## v0.8.0-beta.22

This beta clarifies Google Routes travel-time wording.

### Fixed

- `duration` is now described as the Google Routes travel time with current traffic conditions.
- `staticDuration` is now described as the static duration without current traffic conditions.
- The model is explicitly told not to call `staticDuration` "typical" or "typische Fahrzeit".
- Route follow-ups receive the same wording rule.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.22
```

Expected tests:

```text
Ran 73 tests
```

## v0.8.0-beta.21

This beta tightens the final route-corridor presentation rule.

### Fixed

- Compact route chains derived by Research Guard must now be shown as `Geprüfte Verlaufskette: ...`.
- The model is explicitly told not to label that compact chain as `Verlauf:` or `Streckenverlauf:`, because those labels make the chain look like free model knowledge.
- Route follow-ups receive the same label rule.
- Numbered Google Routes steps remain available only when the user explicitly asks for the route course/highways/roads.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.21
```

Expected tests:

```text
Ran 73 tests
```

## v0.8.0-beta.20

This beta closes the remaining route-planning wording gaps around candidate lists.

### Fixed

- Route contexts now explicitly block strategy/order wording such as `erster Ladestopp`, `zweiter Stopp`, `Hauptladestopp`, `Zwei-Stopp-Strategie`, and "this should get you through" style claims unless Research Guard has actually calculated an optimized stop sequence.
- Toll and vignette language is stricter: no `wahrscheinlich relevant`, `Vignette nötig`, `Brennermaut`, or reminder-style toll claims unless official toll data was injected.
- The `Grobe Einordnung` section is limited to coarse route position, available/missing connector data, and "to check" language. Free geography interpretations such as "before the Alpine ascent" or "after the Brenner" are blocked unless they come directly from Google Routes steps.
- Route follow-ups receive the same guardrails, so a later request for two stops or a preferred station cannot turn candidates into a fabricated itinerary.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.20
```

Expected tests:

```text
Ran 73 tests
```

## v0.8.0-beta.19

This beta reintroduces highway/road chains safely.

### New

- Research Guard now derives a compact `Geprüfte Verlaufskette` mechanically from Google Routes step instructions.
- Example shape: `A73 -> A9 -> E45`.
- The model may use exactly that chain or omit it, but must not add, correct, or extend it from world knowledge.

### Still Guarded

- Full numbered Google Routes steps are still exposed only when the user explicitly asks for route course/highways/roads.
- Toll/vignette/pass/elevation claims remain blocked unless official data is injected.
- The verified corridor is not an optimized route explanation, toll source, or charger-stop sequence.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.19
```

Expected tests:

```text
Ran 73 tests
OK
```

## v0.8.0-beta.18

This beta removes route-course data from normal charging-plan answers.

### Fixed

- Google Routes steps are no longer included in the answer context for normal route/charging-planning prompts.
- Route steps remain stored in the route snapshot and are exposed only when the user explicitly asks for route course/highways/roads.
- The `Route` section is constrained to start, destination, total distance, and total duration only.
- The `Grobe Einordnung` section may not include SoC percentages, charging windows, charging minutes, segment kilometers, or “this should get you through” style claims.
- Connector aggregation is now worded as `Places meldet verfügbar/gesamt X/Y` with `nicht live garantiert; nicht als belegt lesen`, so local models should not invert it into occupied counts.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.18
```

Expected tests:

```text
Ran 72 tests
OK
```

## v0.8.0-beta.17

This beta adds a required answer template for route planning.

### Fixed

- Route-planning answers are constrained to allowed sections: `Route`, `Energie-Check`, `Ladepunkt-Kandidaten`, `Grobe Einordnung`, `Nicht von Research Guard geprüft`, and `Datenquelle`.
- A `Streckenverlauf` section is allowed only when the user explicitly asks for route course/highways/roads, and then only as numbered Google Routes steps.
- One-line highway chains such as `B470 -> A73 -> A3 -> ...` are explicitly disallowed.
- Toll/vignette content may only appear as “not checked by Research Guard” unless official toll data was injected.
- The model must not offer to open/check ABRP, PlugShare, VW apps, or other live tools unless such a tool is actually present in context.

### Verification

```bash
grep '^version:' ~/.hermes/plugins/research-guard/plugin.yaml
python3 -m unittest discover -s test -p 'test_*.py'
```

Expected plugin version:

```text
version: 0.8.0-beta.17
```

Expected tests:

```text
Ran 71 tests
OK
```

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
