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
