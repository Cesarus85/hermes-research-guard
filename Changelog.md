## 2026-05-16 - Verlaufsketten-Label strikt festgelegt
- **Typ:** fix
- **Problem:** Hermes konnte die geprüfte kompakte Route weiterhin als freie `Verlauf:`-Zeile ausgeben, obwohl sie aus Research Guard stammen und nicht wie Modellwissen wirken soll.
- **Änderung:** Die kompakte Kette darf in Antworten nur noch mit dem Label `Geprüfte Verlaufskette:` erscheinen.
- **Guardrail:** `Verlauf:` und `Streckenverlauf:` sind für die kompakte Kette ausdrücklich verboten; nummerierte Google-Routes-Schritte bleiben nur bei expliziter Streckenverlaufsfrage erlaubt.
- **Version:** Plugin version raised to `0.8.0-beta.21`.
- **Tests:** Context tests assert the strict output label for normal route prompts and route follow-ups.

## 2026-05-16 - Strategie- und Maut-Hintertüren blockiert
- **Typ:** fix
- **Problem:** Hermes konnte weiterhin aus Kandidaten eine Reihenfolge oder Strategie formulieren (`erster Ladestopp`, `zweiter Stopp`, `Zwei-Stopp-Strategie`) und Maut/Vignette durch Hinweise wie `wahrscheinlich relevant` oder `vergiss die Vignette nicht` einschleusen.
- **Änderung:** Reihenfolge-/Strategieformulierungen werden explizit blockiert, solange Research Guard keine echte Stoppreihenfolge berechnet hat.
- **Maut:** Maut-/Vignetten-Erinnerungen, `Brennermaut`, `Vignette nötig`, `wahrscheinlich relevant` und ähnliche Formulierungen sind ohne offizielle injizierte Daten verboten.
- **Grobe Einordnung:** Darf nur noch grobe Routenposition, Connector-Daten vorhanden/fehlen und `prüfen` enthalten; keine Reihenfolge, keine Segment-/SoC-/Zeitangaben und keine freie Geografie wie `vor dem Alpenanstieg`.
- **Version:** Plugin version raised to `0.8.0-beta.20`.
- **Tests:** Context tests now assert blocked strategy/maut/geography wording.

## 2026-05-16 - Geprüfte Verlaufskette aus Google-Routes-Schritten
- **Typ:** feature/fix
- **Problem:** Autobahnketten sind für Routenplanung nützlich, durften aber nicht aus Modellwissen rekonstruiert werden.
- **Änderung:** Research Guard extrahiert jetzt selbst eine kompakte `Geprüfte Verlaufskette` aus den Google-Routes-Schritten, z. B. `A73 -> A9 -> E45`.
- **Guardrail:** Hermes darf exakt diese Kette verwenden oder weglassen, aber nicht manuell ergänzen, korrigieren oder aus Weltwissen erweitern.
- **Details:** Nummerierte Google-Routes-Schritte bleiben weiterhin nur bei ausdrücklicher Streckenverlaufsfrage im Antwortkontext.
- **Version:** Plugin version raised to `0.8.0-beta.19`.
- **Tests:** Test suite expanded with route-corridor extraction coverage.

## 2026-05-16 - Normale Ladeplanung ohne Streckenverlauf-Daten
- **Typ:** fix
- **Problem:** Hermes konnte in normalen Ladeplanungsantworten weiterhin eine `Verlauf:`-Zeile oder Autobahnkette erzeugen, weil Google-Routes-Schritte im Kontext sichtbar waren.
- **Änderung:** Google-Routes-Schritte werden in normalen Routen-/Ladeplanungsantworten nicht mehr in den Antwortkontext aufgenommen. Sie bleiben intern im Snapshot und erscheinen nur bei ausdrücklicher Streckenverlaufsfrage.
- **Connector-Zahlen:** Connector-Aggregationen werden jetzt als `Places meldet verfügbar/gesamt X/Y` formuliert, inklusive Hinweis `nicht live garantiert; nicht als belegt lesen`.
- **Antwortvorlage:** Die `Route`-Rubrik darf nur Start, Ziel, Gesamtdistanz und Gesamtfahrzeit enthalten. `Grobe Einordnung` darf keine SoC-Prozente, Ladefenster, Ladezeit-Minuten, Segmentkilometer oder `das sollte reichen/durchbringen` enthalten.
- **Version:** Plugin version raised to `0.8.0-beta.18`.
- **Tests:** Test suite expanded with explicit route-course gating and connector wording coverage.

## 2026-05-16 - Routen-Antwortvorlage erzwingen
- **Typ:** fix
- **Problem:** Hermes konnte trotz Guardrails noch unerlaubte Rubriken wie eigene Streckenverlauf-Ketten, Maut-Hinweise, `Plausibler Ladeplan` oder zu starke Kandidatenempfehlungen ausgeben.
- **Änderung:** Research Guard injiziert jetzt eine verpflichtende Antwortvorlage mit erlaubten Rubriken: `Route`, `Energie-Check`, `Ladepunkt-Kandidaten`, `Grobe Einordnung`, `Nicht von Research Guard geprüft`, `Datenquelle`.
- **Streckenverlauf:** Eine Streckenverlauf-Rubrik ist nur noch bei ausdrücklicher Nachfrage erlaubt und dann nur als nummerierte Google-Routes-Schritte, nie als eigene Ein-Zeilen-Autobahnkette.
- **Maut/Tools:** Maut/Vignette darf ohne offizielle Daten nur als `nicht geprüft` erscheinen. ABRP/PlugShare/VW-App dürfen nicht als aufrufbare Live-Tools angeboten werden, wenn kein entsprechendes Tool vorhanden ist.
- **Version:** Plugin version raised to `0.8.0-beta.17`.
- **Tests:** Context tests now assert the route answer-template guardrails.

## 2026-05-16 - Streckenverlauf und Ladeempfehlungen härter begrenzt
- **Typ:** fix
- **Problem:** Hermes konnte weiterhin eigene kompakte Autobahnketten, Mautpflicht-Hinweise und zu starke Ladeempfehlungen wie `ideal`, `hohe Verfügbarkeit` oder `der ID.7 lädt hier schnell` formulieren.
- **Änderung:** Streckenverläufe dürfen nur noch als nummerierte Google-Routes-Schritte wiedergegeben werden. Eigene Autobahnketten wie `B470 -> A73 -> A3 -> ...` sind ausdrücklich verboten.
- **Maut:** Mautpflicht, Vignette, Brennermaut, Italien-Maut, Höhenmeter und Passhöhen dürfen nicht mehr als Fakt genannt werden, wenn keine offiziellen Daten injiziert wurden.
- **Ladestopps:** Gute Connector-Daten erlauben nur noch `plausibel zu prüfen` oder `stärker belegter Kandidat`, keine echte Empfehlung oder Verfügbarkeitsaussage.
- **Version:** Plugin version raised to `0.8.0-beta.16`.
- **Tests:** Context tests now assert the stricter wording for route-course and charger-candidate language.

## 2026-05-16 - Mehrstopp-Ladeplanung robuster begrenzt
- **Typ:** fix
- **Problem:** Hermes konnte Ladepunkt-Kandidaten noch frei in Google-Routes-Schritte einsortieren und daraus erfundene Etappen, Segmentkilometer oder eine angebliche Zwei-Stopp-Ladeplanung bauen.
- **Änderung:** Lade-/Tankkandidaten enthalten jetzt eine grobe `route_position` und `route_progress_percent_approx`, aber mit ausdrücklichem Hinweis, dass dies nur Suchbereiche entlang der Polyline sind.
- **Follow-ups:** Anfragen wie `mit zwei Ladestopps` lösen jetzt eine frische Routen-/Places-Abfrage aus, statt den alten Snapshot als optimierte Mehrstopp-Route umzudeuten.
- **Kandidatenabdeckung:** Standardmäßig werden jetzt 5 statt 3 Routenpunkte für Lade-/Tankkandidaten abgefragt.
- **Guardrails:** Hermes darf Kandidaten nicht mehr frei zwischen Navigationsschritten platzieren, keine `Etappe 1 -> Stop -> Etappe 2`-Planung erfinden und keine Segmentkilometer zwischen Kandidaten nennen.
- **Version:** Plugin version raised to `0.8.0-beta.15`.
- **Tests:** Test suite expanded with route-position and multi-stop refresh coverage.

## 2026-05-16 - Google-Routes-Schritte für Streckenverlauf ergänzt
- **Typ:** feature/fix
- **Problem:** Anschlussfragen nach dem Streckenverlauf führten wieder zu erfundenen Autobahnen, Grenzdetails, Mautkosten und Segmenten aus Modellwissen.
- **Änderung:** Google Routes wird jetzt mit `routes.legs.steps.*` abgefragt. Research Guard injiziert echte Navigationsschritte mit Instruktion, Distanz und Dauer, sofern Google sie liefert.
- **Guardrails:** Hermes darf Autobahnen, Straßen, Anschlussstellen, Zwischenorte und Segmentdistanzen nur aus den Google-Routes-Schritten ableiten. Ohne Schritte muss es sagen, dass der detaillierte Verlauf nicht im Kontext vorliegt.
- **Maut/Höhenmeter:** Vignettenpreise, Brennermaut, italienische Maut, Gesamtmaut, Passhöhen, Höhenmeter und Grenzkosten werden ausdrücklich blockiert, solange keine offiziellen Daten dafür injiziert wurden.
- **Follow-ups:** `Streckenverlauf`, `Maut`, `Brenner`, `Autobahn` usw. werden als Routen-Follow-ups erkannt.
- **Version:** Plugin version raised to `0.8.0-beta.14`.
- **Tests:** Test suite expanded from 67 to 69 dependency-free tests.

## 2026-05-16 - EV-Ladeplanungs-Antwortdisziplin nachgeschärft
- **Typ:** fix
- **Problem:** Lokale Modelle konnten trotz Kandidatenmodus noch konkrete Ladezeiten, 20-80%-Fenster, Ziel-/Rest-SoC, Start-Ladestopps oder Standort-Komfortdetails erfinden.
- **Änderung:** Routen-Kontext verbietet jetzt explizit erfundene Ladezeiten, SoC-Werte, Standortausstattung, Betreiberqualität, Preise und Tesla-Fremdmarken-Details, sofern sie nicht im Kontext stehen.
- **Startakku:** Formulierungen wie `voll geladen`, `voller Akku`, `mit vollem Akku` und `100%` werden als `start_soc_percent=100` erkannt. Startbereich-Ladepunkte sollen dann nur noch als Vorab-Optionen erscheinen, nicht als erster Routenstopp.
- **Connector-Guardrail:** Ladepunkte ohne Connector-/Leistungsdaten dürfen nur als `Kandidat zu prüfen` genannt werden.
- **Version:** Plugin version raised to `0.8.0-beta.13`.
- **Tests:** Test suite expanded from 66 to 67 dependency-free tests.

## 2026-05-16 - EV-Reichweiten-Plausibilitätsrechnung ergänzt
- **Typ:** fix
- **Problem:** Lokale Modelle konnten bei EV-Routen einfache Reichweitenmathematik falsch ausrechnen, z. B. aus 77 kWh und 16-18 kWh/100 km nur 125-135 km Reichweite ableiten.
- **Änderung:** Research Guard injiziert jetzt bei erkannter Akkugröße eine einfache Energie-Plausibilitätsrechnung mit Formel, Verbrauchsband, grober Vollakku-Reichweite und grobem Energiebedarf der Route.
- **Parsing:** Häufige Nutzereingabe wie `77 kw Batterie` wird als Akkugröße erkannt, ohne normale Ladeleistungsangaben wie `125 kW` als Batterie zu behandeln.
- **Guardrails:** Hermes soll Reichweite, Energiebedarf und grobe Ladestopp-Anzahl nur noch gegen diese Rechnung plausibilisieren und keine widersprüchlichen Werte ausgeben.
- **Version:** Plugin version raised to `0.8.0-beta.12`.
- **Tests:** Test suite expanded from 63 to 66 dependency-free tests.

## 2026-05-16 - Routenplanung auf Kandidaten statt erfundene Optimierung begrenzt
- **Typ:** fix
- **Problem:** Lokale Modelle konnten Google-Places-Kandidaten als `ideale` Ladeplanung ausgeben und zusätzlich Segmentdistanzen, SoC-Werte, Ladezeiten oder weitere Stopps aus Trainingswissen ergänzen.
- **Änderung:** Routen-Kontext und Routen-Follow-ups markieren jetzt ausdrücklich: Research Guard liefert Route + Places-Kandidaten, aber keine optimierte Stoppreihenfolge, keine Etappendistanzen zwischen Kandidaten und keine SoC-/Ladezeitkurve.
- **Guardrails:** Hermes soll ausschließlich injizierte Places-Kandidaten nennen und sie als Kandidaten formulieren, nicht als garantierte oder optimale Stopps.
- **Version:** Plugin version raised to `0.8.0-beta.11`.
- **Tests:** Existing route-context tests now assert the stricter candidate-only route-planning guardrails.

## 2026-05-16 - Lade-/Tankstopp-Auswahl über Routenpunkte balanciert
- **Typ:** fix
- **Problem:** Places konnte pro gesampeltem Routenpunkt bis zu 6 Treffer liefern; danach wurde global auf 6 gekürzt. Dadurch konnten alle Kandidaten vom Startpunkt kommen und unterwegs liegende Treffer verdrängen.
- **Änderung:** Stopp-Kandidaten werden jetzt pro Routenpunkt balanciert ausgewählt. Der Kontext enthält `Stopp-Abdeckung` mit Sample-Indizes.
- **Guardrails:** Wenn Google nur Kandidaten aus einem Routenbereich liefert, muss Hermes das sagen und darf keine unterwegs liegenden Stopps aus Trainingswissen ergänzen.
- **Version:** Plugin version raised to `0.8.0-beta.10`.
- **Tests:** Test suite expanded from 61 to 63 dependency-free tests.

## 2026-05-16 - Google-Routes-Diagnosetool ergänzt
- **Typ:** diagnostics
- **Problem:** Bei unplausiblen Routen war nicht eindeutig sichtbar, ob Google Routes wirklich antwortete oder ob das Modell Route/Orte erfand.
- **Tool:** Neues Hermes-Tool `research_guard_route_test` validiert den konfigurierten Google-Maps-Key gegen Routes API und gibt Distanz, Dauer, Polyline-Punktzahl, Sample-Koordinaten und Bounding Box zurück.
- **Guardrails:** Routen-Kontext enthält jetzt Route-Shape-Diagnostik und weist das Modell an, keine Zwischenorte, Autobahnen, Pässe oder Umwege zu erfinden.
- **Version:** Plugin version raised to `0.8.0-beta.9`.
- **Tests:** Test suite expanded from 58 to 61 dependency-free tests.

## 2026-05-16 - Routen-Follow-ups ergänzt
- **Typ:** feature
- **Änderung:** Research Guard speichert jetzt einen kleinen strukturierten Snapshot des letzten Routen-Kontexts im Statuspuffer.
- **Follow-ups:** Anschlussfragen wie `Welche Ladestation würdest du bevorzugen?` nutzen den letzten Routen-Kontext ohne neue Google-Abfrage.
- **Refresh:** Rückweg-/Return- und explizite Neuberechnungsfragen wie `Und zurück?` oder `Berechne die Route nochmal neu` können eine frische Google-Routenabfrage auslösen.
- **Diagnostik:** Status unterscheidet `route-followup-context` und `route-planning-followup-refresh`.
- **Version:** Plugin version raised to `0.8.0-beta.8`.
- **Tests:** Test suite expanded from 56 to 58 dependency-free tests.

## 2026-05-16 - Route Planning ohne Lade-/Tankangabe aktiviert
- **Typ:** feature
- **Änderung:** Klare Routenfragen wie `Plane die Route von A nach B` triggern jetzt Route Planning auch ohne Lade- oder Tankstopp-Angabe.
- **Stopps:** EV-Ladepunkte werden nur bei EV-/Akku-/Ladekontext gesucht; Tankstellen nur bei Tank-/Fuel-Kontext. Reine Route bleibt reine Route.
- **Fahrzeugkontext:** Generische Fahrzeughinweise wie `mit einem VW Golf` werden als Kontext übernommen, ohne automatisch Tankstopps zu erzwingen.
- **Version:** Plugin version raised to `0.8.0-beta.7`.
- **Tests:** Test suite expanded from 53 to 56 dependency-free tests.

## 2026-05-16 - EV-Route-Trigger für Batterie-/Fahrzeugkontext erweitert
- **Typ:** fix
- **Problem:** Routenfragen wie `VW ID 7 mit 77 kWh Batterie` wurden nicht als EV-Routenplanung erkannt, wenn keine Wörter wie `E-Auto` oder `Ladeplanung` vorkamen.
- **Änderung:** Route-Planning erkennt jetzt EV-Kontext über `kWh`, `Batterie`, `Akku` und typische EV-Modellhinweise wie `VW ID 7`.
- **Zusatzdaten:** Route Request extrahiert nun Batteriegröße, Fahrzeughinweis, Personenzahl und Vollbeladen-Hinweis für bessere Antwort-Guardrails.
- **Version:** Plugin version raised to `0.8.0-beta.6`.
- **Tests:** Test suite expanded from 52 to 53 dependency-free tests.

## 2026-05-16 - Plugin-eigene Route-Planning-Konfiguration ergänzt
- **Typ:** usability
- **Feature:** Neues Tool `research_guard_config` ergänzt, damit Hermes Research Guard dauerhaft konfigurieren kann, ohne dass Nutzer systemd-, Shell- oder Gateway-Environment-Dateien finden müssen.
- **Config:** Research Guard liest jetzt `~/.hermes/research-guard.json` und optional `research-guard/config.json`; Environment-Variablen bleiben als Override erhalten.
- **Sicherheit:** API-Key wird in Tool-/Statusausgaben maskiert. Hinweis: lokal wird er in der Hermes-Konfigurationsdatei im Klartext gespeichert.
- **Doku:** README und Release Notes beschreiben die einfache Hermes-Anweisung zur Aktivierung.
- **Version:** Plugin version raised to `0.8.0-beta.5`.
- **Tests:** Test suite expanded from 50 to 52 dependency-free tests.

## 2026-05-16 - Tankstopp-Kandidaten für Routenplanung ergänzt
- **Typ:** feature
- **Feature:** Optionales Google-Maps-Route-Planning berücksichtigt jetzt neben EV-Ladepunkten auch Tankstopp-Kandidaten über Places `gas_station`.
- **Kostenkontrolle:** Kraftstoff-/Preisfelder (`fuelOptions`) sind standardmäßig deaktiviert und nur per `RESEARCH_GUARD_ROUTE_INCLUDE_FUEL_OPTIONS=true` abrufbar.
- **Status:** `research_guard_status` zeigt `max_fuel_stops`, `include_fuel_options` und pro Entscheidung `fuel_stop_candidate_count`.
- **Version:** Plugin version raised to `0.8.0-beta.4`.
- **Tests:** Test suite expanded from 49 to 50 dependency-free tests.

## 2026-05-16 - Optionale Google-Maps-Routenquelle ergänzt
- **Typ:** feature
- **Feature:** Optionales Route-Planning-Modul für Hermes Research Guard ergänzt. Es erkennt Routen-, Fahrstrecken- und EV-Ladeplanungsfragen und kann Google Maps Platform als spezialisierte Datenquelle nutzen.
- **Datenquellen:** Google Routes API liefert Distanz, Fahrtzeit und Route-Polyline. Google Places API sucht EV-Ladepunkt-Kandidaten an gesampelten Punkten entlang der Route.
- **Sicherheit:** Das Feature ist standardmäßig deaktiviert und benötigt `RESEARCH_GUARD_ENABLE_ROUTE_PLANNING=true` plus `GOOGLE_MAPS_API_KEY` oder `RESEARCH_GUARD_GOOGLE_MAPS_API_KEY`.
- **Guardrails:** Injizierter Kontext weist lokale Modelle ausdrücklich an, keine exakten SoC-Verläufe, Ladezeiten, Preise, Verfügbarkeiten oder optimalen Stopps zu erfinden.
- **Kostenkontrolle:** Keine persistente Speicherung von Google-Routes/Places-Payloads; Charger-Suchen, Radius und Ergebniszahl sind per Environment-Variable begrenzt.
- **Status:** `research_guard_status` zeigt Route-Planning-Konfiguration, API-Key-Status und neue Entscheidungsdiagnostik.
- **Version:** Plugin version raised to `0.8.0-beta.3`.
- **Tests:** Test suite expanded from 45 to 49 dependency-free tests.

## 2026-05-16 - Clarify Hermes-only beta scope
- **Type:** beta/docs
- **Change:** README and release notes now clearly state that this project is a Hermes Agent plugin and requires Hermes.
- **Install docs:** Removed the misleading standalone/non-Hermes installation path.
- **Install docs:** Documented the two supported paths: Hermes-initiated installation from the GitHub repository and manual command-line installation into the Hermes plugin directory.
- **Version:** Plugin version raised to `0.8.0-beta.2`.

## 2026-05-16 - First beta repository preparation
- **Type:** beta/release-prep
- **Change:** README has been rewritten in English as a beta-facing project overview.
- **Install docs:** Added explicit installation instructions for Hermes usage.
- **Beta scope:** Added beta status, known limitations, quick verification, configuration, provider chain, source-quality behavior, privacy boundaries, and roadmap notes.
- **Release notes:** Added `RELEASE_NOTES.md` for `v0.8.0-beta.1`.
- **Version:** Plugin version raised to `0.8.0-beta.1`.

## 2026-05-16 - Kompakte Status-Erklärung portiert
- **Typ:** feature
- **Auslöser:** Letzter offensichtlicher Angleichungspunkt zur OpenClaw-Variante.
- **Änderung:** Status-Entscheidungen enthalten jetzt `reason_summary`, `visible_effect_summary` und `user_explanation`.
- **Nutzen:** `research_guard_status` erklärt nicht-technisch, warum Research Guard lief oder übersprungen wurde und welchen sichtbaren Effekt das hatte.
- **Diagnostik:** Die Kurz-Erklärung steht zusätzlich im verschachtelten `diagnostic`-Block und als `summary.latest_explanation`.
- **Version:** Plugin-Version auf `0.7.4` erhöht.
- **Tests:** Coverage für übersprungene lokale Infrastruktur und injizierte Faktenrecherche ergänzt.

## 2026-05-15 - Cache- und Performance-Härtung ergänzt
- **Typ:** feature
- **Auslöser:** Nächster Angleichungsschritt nach OpenClaw Source-Profilen: stabilerer Dauerbetrieb.
- **Cache:** `RESEARCH_GUARD_CACHE_MAX_ENTRIES` ergänzt; Cache-Schreiben bereinigt abgelaufene und überzählige Einträge. `RESEARCH_GUARD_CACHE_TTL_SECONDS=0` deaktiviert Cache-Lesen und -Schreiben.
- **TTL-Profile:** `RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS` ergänzt. Aktuelle/news-/preis-/release-nahe Queries verwenden standardmäßig eine kürzere TTL von 900 Sekunden, stabile Fakten weiter die normale TTL.
- **Timeouts:** `RESEARCH_GUARD_PROVIDER_TIMEOUT` ergänzt und als per-provider Timeout-Klammer um alle Providerpfade gelegt; direkte HTTP-Provider und Deep Fetch behalten ihre eigenen expliziten Timeouts.
- **Diagnostik:** Status/config zeigen Cache-Maximum, Standard-/Current-TTL sowie Provider- und Deep-Fetch-Timeouts.
- **Version:** Plugin-Version auf `0.7.3` erhöht.
- **Tests:** Coverage für Cache-Eviction, Current-TTL-Pruning und deaktivierten Cache ergänzt.

## 2026-05-15 - Domain-spezifische Quellenprofile ergänzt
- **Typ:** feature
- **Auslöser:** Angleichung an OpenClaw Source-Ranking für Software, kommunale Fakten, Preise/Produkte und aktuelle Themen.
- **Änderung:** Query-Profile `municipal-local`, `tech-software`, `price-product` und `news-current` ergänzt. Quellen erhalten zusätzlich explizite Profile wie `municipal`, `documentation`, `project`, `package-registry`, `release-notes`, `pricing`, `standards`, `reference` und schwache Profile wie `weak-aggregator`.
- **Scoring:** Paketregistries, Release Notes, offizielle Pricing-Seiten und Standards-Domains werden nun stärker bevorzugt; schwache Aggregator-/Commercial-Profile bleiben sichtbar und werden abgewertet.
- **Diagnostik:** `quality`, Statusentscheidungen und injizierter Kontext enthalten jetzt `query_profiles`, `source_profiles`, `profile_coverage` bzw. eine `Quellenprofile:`-Zeile.
- **Version:** Plugin-Version auf `0.7.2` erhöht.
- **Tests:** Coverage für Software-/Package-/Release-Profile, Pricing-Profile und Profilanzeige im Kontext ergänzt.

## 2026-05-14 - Query-Rewrites und Modus-Schalter ergänzt
- **Typ:** feature
- **Auslöser:** Angleichung an OpenClaw Query-Quality-Block nach Provider-Parität.
- **Änderung:** `RESEARCH_GUARD_MODE=conservative|balanced|aggressive` ergänzt. Standard bleibt `balanced`, `conservative` reduziert allgemeine Fakten-Suchen, `aggressive` recherchiert längere Fragezeichen-Prompts eher.
- **Query-Rewrites:** Deterministische Templates für Bürgermeister/Landrat, Einwohner/Bevölkerung, aktuelle Versionen/Releases, Changelogs/Release Notes, Preise/Pricing, Vergleiche und aktuelle Fakten ergänzt.
- **Official Hints:** Rewrites fügen offizielle Suchhinweise wie `official`, `release notes`, `pricing`, `Rathaus`, `offizielle Stadt`, `Statistik` oder `Verwaltung` hinzu.
- **Diagnostik:** `query_debug` enthält jetzt `base_query` und `rewrite_strategy`, damit im Status sichtbar ist, was aus der Nutzerfrage gesucht wurde.
- **Version:** Plugin-Version auf `0.7.1` erhöht.
- **Tests:** Coverage für Modus-Schalter, Rewrite-Templates und Query-Debug ergänzt.

## 2026-05-13 - Provider-Kette und Brave/SearXNG ergänzt
- **Typ:** feature
- **Auslöser:** Angleichung an OpenClaw Provider-/Suchbackend-Parität.
- **Änderung:** `RESEARCH_GUARD_PROVIDER=auto|web_search_plus|brave|hermes|duckduckgo|searxng` ergänzt. `auto` probiert optional `web_search_plus`, dann Brave bei gesetztem API-Key, Hermes Web Search, optional SearXNG und zuletzt DuckDuckGo HTML.
- **Provider:** Brave Search läuft über `BRAVE_API_KEY` oder `RESEARCH_GUARD_BRAVE_API_KEY`; SearXNG über `RESEARCH_GUARD_SEARXNG_URL`.
- **Normalisierung:** Provider-Ergebnisse werden zentral auf `{title, url, snippet, age}` normalisiert, inklusive citation-only/web/result/data-Wrappern.
- **Diagnostik:** Search-Payloads und Entscheidungen enthalten `provider_chain`; Fallback-Fehler werden beibehalten und Status/config zeigen die aktive Provider-Konfiguration.
- **Version:** Plugin-Version auf `0.7.0` erhöht.
- **Tests:** Coverage für Provider-Reihenfolge, Fallbackpfad und Result-Normalisierung ergänzt.

## 2026-05-11 - Runtime-Version im Status sichtbar gemacht
- **Typ:** diagnostics
- **Auslöser:** Chat — Trotz installierter `0.6.7` wurde bei lokalen Prompts weiterhin sichtbares Reasoning angezeigt; zur Abgrenzung zwischen installierter Datei, geladener Plugin-Instanz und Modell-/Hermes-Verhalten fehlte eine Runtime-Angabe.
- **Änderung:** `research_guard_status` enthält jetzt `version` und `runtime.module_version` sowie `runtime.skipped_turns_inject_context_by_default=false` und den aktuellen Wert von `RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY`.
- **Nutzen:** Im Hermes-Chat lässt sich nun prüfen, ob wirklich die neue Python-Modulversion geladen ist oder nur die `plugin.yaml` aktualisiert wurde.
- **Version:** Plugin-Version auf `0.6.8` erhöht.
- **Tests:** Status-Test prüft Version und Skip-Turn-Runtime-Verhalten.

## 2026-05-11 - No-Research-Boundary standardmäßig deaktiviert
- **Typ:** fix
- **Auslöser:** Chat — Nach `0.6.5/0.6.6` zeigte Hermes/Qwen plötzlich sichtbares `💭 Reasoning`, weil der neue `[Research Guard inaktiv für aktuelle Frage]`-Kontext bei Skip-Turns in den Modellkontext gelangte.
- **Ursache:** Die No-Research-Boundary war als Standard aktiv. In Hermes kann injizierter Hook-Kontext je nach Modell/UI sichtbar in Denkspuren einfließen.
- **Änderung:** No-Research-Boundaries sind nun opt-in über `RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY=true`. Standardmäßig geben Skip-, Model-Gate-, Low-Confidence- und Search-Failure-Turns wieder keinen Kontext zurück.
- **Beibehalten:** Aktive Research-Turns, Kontext-Follow-ups, Quellen-Follow-ups und Statusdiagnostik bleiben unverändert.
- **Version:** Plugin-Version auf `0.6.7` erhöht.
- **Tests:** Coverage angepasst: Skip-Turns injizieren standardmäßig nichts, Boundary kann aber per Env-Flag aktiviert werden.

## 2026-05-11 - Heimatstadt-/Eindruck-Follow-ups abgesichert
- **Typ:** fix
- **Auslöser:** Chat — Nach `Wo liegt Forchheim?` wurde `Wie ist dein Eindruck von meiner Heimatstadt?` fälschlich als neue Websuche nach generischen Heimatstadt-Foren behandelt.
- **Änderung:** Kontext-/Meinungs-Follow-ups erkennen jetzt Formulierungen wie `Wie ist dein Eindruck von ...`, `Welchen Eindruck hast du von ...`, `Wie wirkt ... auf dich` und `Was hältst du von meiner Heimatstadt?`.
- **Privatsphäre:** Possessivformen wie `meiner`, `meinem`, `unserer` usw. werden als persönliche/private Prompts erkannt und ohne explizites `/research` nicht ins Web geschickt.
- **Antwortdisziplin:** Der Kontext-Follow-up-Block verbietet erfundene persönliche Details über den Nutzer, seine Projekte, Vorlieben oder Beziehung zum Ort und untersagt eine neue `Quellen (Research Guard):`-Zeile für reine Anschluss-Meinungsfragen.
- **Version:** Plugin-Version auf `0.6.6` erhöht.
- **Tests:** Repro-Fall `Wie ist dein Eindruck von meiner Heimatstadt?` und private Possessivformen ergänzt.

## 2026-05-11 - Answer-Discipline und No-Research-Boundary portiert
- **Typ:** feature/fix
- **Auslöser:** Angleichung an OpenClaw nach Stabilisierung der Statusdiagnostik.
- **Änderung:** Aktive Research-Turns enthalten jetzt eine OpenClaw-nähere `[Research Guard aktiv]`-Klammer plus `[Research Guard: Web-Recherche-Kontext]`. Der Kontext erklärt explizit, dass frühere Research-Guard-Kontexte, Quellenlisten, Statusdaten und Diagnoseblöcke für den aktuellen Turn ungültig sind.
- **No-Research-Boundary:** Skipped-, Model-Gate-, Low-Confidence- und Search-Failure-Turns injizieren jetzt `[Research Guard inaktiv für aktuelle Frage]`, damit lokale Modelle keine alten `Quellen (Research Guard):`-Zeilen wiederverwenden oder behaupten, Research Guard habe für die aktuelle Frage recherchiert.
- **Konfiguration:** `RESEARCH_GUARD_REQUIRE_SOURCES=true|false` ergänzt; Standard bleibt `true`.
- **Version:** Plugin-Version auf `0.6.5` erhöht.
- **Tests:** Coverage für aktive Turn-Boundary, inaktive No-Research-Boundary und Pre-Hook-Skip-Kontext ergänzt.

## 2026-05-10 - Statusdiagnostik näher an OpenClaw angeglichen
- **Typ:** feature/fix
- **Auslöser:** Chat — Hermes gab zwar Statusdaten aus, formte sie aber frei um, hängte eine eigene Zusammenfassung an und zeigte interne Hermes-Notizen als recherchierte Queries.
- **Änderung:** `research_guard_status` enthält jetzt OpenClaw-nähere Felder: `status_buffer`, `legend`, `summary`, `response_policy` und pro Entscheidung ein verschachteltes `diagnostic` mit `searched`, `injected_context`, `manual_tool`, `skipped`, `failed`, `provider_path`, `explanation` und `evidence`.
- **Antwortdisziplin:** Status-Injektionen verlangen nun, das JSON nicht frei umzubenennen, nicht mit Quellenlisten zur Vorantwort zu antworten und keine eigene Zusammenfassung wie `Alles aktiv` anzuhängen.
- **Skip-Regel:** Interne Hermes-/Gateway-Notizen wie `[Note: model switch] da?` und `accomplished [gateway restart note]` werden als `internal-note` übersprungen.
- **Version:** Plugin-Version auf `0.6.4` erhöht.
- **Tests:** Coverage für interne Notizen, Status-Policy-Felder und verschachtelte Entscheidungsdiagnostik ergänzt.

## 2026-05-10 - Status-Intent gegen Quellenpfad abgeschirmt
- **Typ:** fix
- **Auslöser:** Chat — `Zeige research guard status` wurde weiterhin wie eine Quellenfrage zur letzten Antwort beantwortet.
- **Ursache:** Der Quellen-Follow-up-Matcher akzeptierte `research guard` auch ohne Quellen-/Herkunftsfrage. Damit konnte eine Statusfrage im falschen Kontext landen, insbesondere wenn Hermes keinen Tool-Call ausführt.
- **Änderung:** `research guard` allein zählt nicht mehr als Quellen-Follow-up. `_is_source_followup` blockt Status-/Diagnose-Requests zusätzlich explizit ab.
- **Version:** Plugin-Version auf `0.6.3` erhöht.
- **Tests:** Exakter Repro-Fall `Zeige research guard status` ergänzt.

## 2026-05-10 - Status-Anfragen robuster erkannt
- **Typ:** fix
- **Auslöser:** Chat — Hermes beantwortete `Zeig mir den Research Guard status` wie eine Quellen-Nachfrage zur vorherigen Antwort, statt den Diagnose-Status auszugeben.
- **Ursache:** `research guard` war Teil der Quellen-Follow-up-Erkennung. Dadurch gewann `source-followup` vor einem echten Status-/Diagnose-Intent, wenn Hermes keinen Tool-Call auslöste.
- **Änderung:** Eigene Status-Erkennung für `Research Guard Status`, `research_guard_status`, `research_guard_diagnostics`, Diagnose-/Debug-/Health-Fragen. Diese greift vor der Quellenlogik und injiziert den Status-v2-Payload direkt in den Hook-Kontext.
- **Version:** Plugin-Version auf `0.6.2` erhöht.
- **Tests:** Coverage ergänzt, damit Statusfragen nicht mehr als Quellen-Follow-up klassifiziert werden und der Diagnose-Kontext Status-v2-JSON enthält.

## 2026-05-10 - Deep-Fetch-Parität nachgezogen
- **Typ:** feature
- **Auslöser:** Chat — Nachfrage, ob Deep Fetch direkt auf OpenClaw-Parität gebracht werden soll.
- **Änderung:** Deep Fetch fetches topbewertete Seiten jetzt parallel, der Cache-Key enthält das konkrete Deep-Fetch-Profil, und einfache nummerierte Tracklist-Kandidaten werden aus vertieften Auszügen extrahiert.
- **Inhalt:** Der Kontext zeigt `Strukturierte Tracklist-Kandidaten`, wenn nummerierte Listen erkannt werden. Status/Entscheidungen speichern weiterhin `deep_fetch`, `deep_fetch_reason` und `fetched_source_count`.
- **Version:** Plugin-Version auf `0.6.1` erhöht.
- **Tests:** Coverage für Deep-Fetch-Profil, Cache-Key-Form und strukturierte Tracklist-Extraktion ergänzt.

## 2026-05-10 - Structured Deep Fetch für Tracklists
- **Typ:** feature/fix
- **Auslöser:** Chat — Hermes halluzinierte bei der Meteora-Tracklist Songs von `Hybrid Theory`, obwohl Research Guard Quellen gefunden hatte.
- **Ursache:** Snippet-only-Kontext reicht für Tracklists nicht. Das Modell mischte Standardalbum, Streaming-Kataloge und andere Editionen.
- **Änderung:** Strukturierte/detailreiche Prompts wie Tracklists, Songlisten, Tabellen, Release Notes, Preise und Bevölkerungsdaten lösen nun Deep Fetch aus. Research Guard lädt lesbare Auszüge aus den topbewerteten Quellen und injiziert sie als `[Research Guard: Vertiefte Quellen-Auszüge]`.
- **Antwortdisziplin:** Tracklist-Prompts enthalten jetzt eine harte Regel: keine Synthese aus Such-Snippets, Streaming-Mischungen oder Anniversary-/Bonus-Editionen; nur klar belegte Standard-/Original-Tracklists aus vertieften Auszügen verwenden oder Unsicherheit melden.
- **Tools:** `research_guard_diagnostics` als Alias für `research_guard_status` ergänzt.
- **Version:** Plugin-Version auf `0.6.0` erhöht.
- **Tests:** Coverage für Deep-Fetch-Trigger und Kontext-Injektion vertiefter Quellen ergänzt.

## 2026-05-10 - Update-Installation abgesichert
- **Typ:** fix
- **Auslöser:** Chat — Hermes zeigte beim Installieren weiterhin `0.2.0`, obwohl das Repository `0.5.0` enthielt.
- **Ursache:** Die bisherige README-Kopieranweisung war nur für Erstinstallationen sicher. Bei bestehendem `~/.hermes/plugins/research-guard` kann `cp -R research-guard ~/.hermes/plugins/research-guard` die neue Version in einen Unterordner kopieren und die alte `plugin.yaml` oben liegen lassen.
- **Änderung:** README enthält jetzt eine update-sichere Installation: altes Plugin-Verzeichnis entfernen, neu kopieren, aktivieren und Gateway neu starten. Zusätzlich wurde `__version__` im Python-Modul ergänzt.
- **Version:** Plugin-Version auf `0.5.1` erhöht.

## 2026-05-10 - Debug/Status v2 ergänzt
- **Typ:** feature
- **Auslöser:** Chat — Stefan fragte, ob noch ein weiterer kleiner Block sinnvoll ist; gewählt wurde ein risikoarmes Diagnosepaket.
- **Änderung:** `research_guard_status` liefert jetzt Status v2 mit Cache-Statistik, Konfigurations-Snapshot, Entscheidungskategorien, sichtbarem Effekt, Evidence-Strings und Query-Debug.
- **Inhalt:** Entscheidungen werden als `researched_and_injected`, `manual_research`, `researched_but_not_injected`, `checked_and_skipped` oder `failed` klassifiziert. `visible_effect` zeigt, ob Quellen injiziert, ein Tool-Result erzeugt oder nichts sichtbar wurde. `query_debug` enthält redigierten Original-Prompt, bereinigten Prompt, getragenes Subject, finale Query und History-Verfügbarkeit. Prompt-Previews redigieren E-Mails, telefonähnliche Werte und lange tokenartige Strings.
- **Version:** Plugin-Version auf `0.5.0` erhöht.
- **Tests:** Coverage für Status-v2-Felder, Kategorien, Evidence, Prompt-Redaction und Query-Debug ergänzt.

## 2026-05-10 - Quick Parity Pack v0.4.0
- **Typ:** feature
- **Auslöser:** Chat — Stefan wollte 1-3 weitere OpenClaw-Features übernehmen, damit der Versionssprung sich lohnt.
- **Änderung:** Drei kleine Angleichungen umgesetzt: Model-Gate-Parität, Follow-up Subject Carryover v1 und provider-aware Cache Keys.
- **Model Gate:** Erkennt zusätzliche lokale Modell-/Providerpfade wie `vllm`, `tgi`, `lm-studio`, `llama.cpp`, `goliath`, `kimi-k2`, `minimax-m2`; Cloud-Provider und Cloud-Modellmuster werden übersprungen; explizite `:cloud`-Marker gewinnen; `/research` überschreibt weiterhin das Gate. Neu: `RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS`.
- **Follow-ups:** `_build_search_query` kann aus Hermes `conversation_history`, `messages` oder `history` ein vorheriges Thema extrahieren und vor pronomenbasierte Anschlussfragen setzen, z. B. `Wal Timmy Was ist mit ihm danach passiert?`.
- **Cache:** Such-Cache-Keys enthalten nun Provider, Limit, reservierten Deep-Fetch-Status und Query, damit Hermes- und DuckDuckGo-Treffer nicht kollidieren.
- **Version:** Plugin-Version auf `0.4.0` erhöht.
- **Tests:** Coverage für lokale/cloud Model Gates, Cloud-Escape-Hatch, Subject Carryover aus History/Content-Parts und provider-aware Cache Keys ergänzt.

## 2026-05-10 - Source Quality v1 aus OpenClaw portiert
- **Typ:** feature
- **Auslöser:** Chat — Stefan fragte, was als nächstes zur OpenClaw-Angleichung sinnvoll ist; nächster Schritt war Quellenqualität und Antwortdisziplin.
- **Änderung:** Research Guard bewertet Suchtreffer vor der Injektion und sortiert brauchbare Quellen nach Qualität.
- **Inhalt:** Bevorzugt werden Preferred Domains, Behörden-/Government-Seiten, kommunale Quellen, Dokumentation, Projekt-/Vendor-Seiten, Referenzquellen und offizielle Kontexte. Abgewertet werden Aggregatoren, Foren/Social-Quellen, Paywall-/Snippet-only-Seiten, kommerzielle Listicles, veraltete/undatierte Current-Facts-Quellen, Duplikate und wiederholte Treffer derselben Domain. Der injizierte Kontext enthält jetzt `Quellenbewertung:` und `Qualität:`-Zeilen sowie eine strengere Ortsfragen-Regel gegen unaufgeforderte Zusatzdetails.
- **Konfiguration:** Neu sind `RESEARCH_GUARD_PREFERRED_DOMAINS`, `RESEARCH_GUARD_BLOCKED_DOMAINS`, `RESEARCH_GUARD_MIN_CONFIDENCE` und `RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES`.
- **Version:** Plugin-Version auf `0.3.0` erhöht.
- **Tests:** Coverage für Preferred-/Official-Boost, blocked domains, kommunale Quellen, Same-Domain-Dämpfung und Quality-Kontext ergänzt.

## 2026-05-10 - Kontext-Follow-ups gegen Literal-Suche abgesichert
- **Typ:** feature
- **Auslöser:** Chat — Stefan zeigte, dass Hermes bei „Was hältst du davon?“ die Anschlussfrage selbst suchte und anschließend den Kontextfehler als Research-Guard-Problem erklärte.
- **Änderung:** Research Guard erkennt kurze Kontext-/Meinungs-Follow-ups wie „Was hältst du davon?“, „Was sagst du dazu?“ und „Wie findest du das?“.
- **Inhalt:** Diese Follow-ups triggern keine frische Websuche nach dem Wortlaut. Stattdessen wird ein `[Research Guard: Kontext-Follow-up]`-Block mit dem letzten Research-Guard-Thema, Query, Provider und gespeicherten Quellen injiziert. Der Block weist das Modell an, Fakten aus Quellen von eigener Einordnung zu trennen und nicht zu behaupten, Research Guard habe nach der Anschlussformulierung gesucht.
- **Version:** Plugin-Version auf `0.2.1` erhöht.
- **Tests:** Coverage für Kontext-Follow-up-Erkennung, erzwungenes `/research` trotz Follow-up-Text und Kontext-Follow-up-Injektion ergänzt.

## 2026-05-10 - Quellen-Follow-ups und Statuspuffer ergänzt
- **Typ:** feature
- **Auslöser:** Chat — Stefan zeigte, dass Hermes nach „Wo hast du die Info her?“ den Follow-up selbst gesucht und dann fälschlich „Trainingswissen/Halluzination“ behauptet hat.
- **Änderung:** Research Guard merkt sich die letzten Entscheidungen in einem In-Memory-Puffer und erkennt Quellen-/Herkunfts-Follow-ups.
- **Inhalt:** Follow-ups wie „Wo hast du die Info her?“, „Was waren deine Quellen?“ oder „Wie kam die Antwort zustande?“ triggern keine frische Websuche mehr. Stattdessen wird ein `[Research Guard: Quellenstatus]`-Kontext mit letzter Aktion, Query, Provider und gespeicherten URLs injiziert. Der normale Research-Kontext fordert nun eine Quellenzeile `Quellen (Research Guard): ...` und weist das Modell an, Research Guard bei späteren Quellenfragen zu nennen.
- **Tools:** Neues Tool `research_guard_status` gibt den aktuellen Entscheidungs-/Quellenpuffer als JSON aus.
- **Version:** Plugin-Version auf `0.2.0` erhöht.
- **Tests:** Coverage für Quellen-Follow-up-Erkennung, Quellenstatus-Kontext und Status-Tool ergänzt.

## 2026-05-10 - OpenClaw Privacy-Skip-Heuristiken portiert
- **Typ:** feature
- **Auslöser:** Chat — Stefan: „gut, dann mach"
- **Änderung:** Erstes OpenClaw-Paritäts-Paket in Hermes Research Guard umgesetzt.
- **Inhalt:** Lokale Infrastrukturfragen zu IPs, Hosts, Ports, SSH, Ping, Tailscale, Erreichbarkeit und Service-Status werden nun zuverlässig von Webrecherche ausgeschlossen; Slash-Commands werden standardmäßig übersprungen; `/research` und `/no-research` sind konsistent mit `#research` und `#no-research`; Speech/STT-Wrapper wie `Audio:` und `Transkript:` werden vor Klassifikation und Query-Building entfernt.
- **Tests:** Dependency-freie `unittest`-Coverage für manuelle Prefixes, Slash-Command-Skips, lokale Infrastruktur-Skips, Speech-Wrapper-Cleanup und weiterhin triggernde aktuelle Faktenfragen ergänzt.

## 2026-05-10 - ROADMAP.md auf OpenClaw-Parität umgestellt
- **Typ:** docs
- **Auslöser:** Chat — Stefan: „ok, dann baue dir da eine Roadmap.md in der alles entsprechend markiert ist..."
- **Änderung:** `ROADMAP.md` durch eine portierungsorientierte Roadmap ersetzt.
- **Inhalt:** Legende für `[x]`, `[ ] PORT`, `[ ] ADAPT`, `[ ] CHECK`, `[ ] LIMIT`; Portability-Matrix zwischen OpenClaw und Hermes; Meilensteine für Provider, Modell-Gates, Skip-Regeln, Query-Qualität, Source-Scoring, Deep Fetch, Answer Discipline, Status-Tools, Tests und Distribution.

## 2026-05-08 - Hermes Research Guard auf GitHub veröffentlicht
- **Typ:** other
- **Auslöser:** Chat — Stefan: „Lässt sich das auf meinen Github packen…?"
- **Änderung:** Neues öffentliches GitHub-Repository `Cesarus85/hermes-research-guard` erstellt und initiale Plugin-Version veröffentlicht.
- **Inhalt:** Plugin-Code, README mit Installation/Konfiguration, MIT License, `.gitignore`.
- **URL:** https://github.com/Cesarus85/hermes-research-guard

## 2026-05-08 - ROADMAP.md ergänzt
- **Typ:** docs
- **Auslöser:** Chat — Stefan: „Bau doch auf Github eine Roadmap.md…"
- **Änderung:** `ROADMAP.md` mit Feature-Vorschlägen und Checkboxen erstellt.
- **Inhalt:** Provider-Upgrade inkl. Brave Search, Query-Rewrite, Confidence-Gating, Source-Ranking, Anti-Oversearch, Cache/Performance, Citations, Debugging, Domain-Modes und v1.0-Polish.
