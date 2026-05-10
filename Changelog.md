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
