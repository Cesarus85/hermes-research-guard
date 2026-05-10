from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "research-guard" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("research_guard_plugin", MODULE_PATH)
guard = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(guard)


class ResearchGuardHeuristicTests(unittest.TestCase):
    def test_manual_research_prefixes_are_consistent(self):
        self.assertEqual(
            guard._should_research("#research Wer ist aktuell Präsident von Frankreich?"),
            (True, "explicit"),
        )
        self.assertEqual(
            guard._should_research("/research Wer ist aktuell Präsident von Frankreich?"),
            (True, "explicit"),
        )
        self.assertEqual(
            guard._should_research("#no-research Wer ist aktuell Präsident von Frankreich?"),
            (False, "opt-out"),
        )
        self.assertEqual(
            guard._should_research("/no-research Wer ist aktuell Präsident von Frankreich?"),
            (False, "opt-out"),
        )
        self.assertEqual(
            guard._build_search_query("/research Wer ist aktuell Präsident von Frankreich?"),
            "Wer ist aktuell Präsident von Frankreich?",
        )

    def test_slash_commands_are_skipped_unless_manual_research(self):
        self.assertEqual(guard._should_research("/status"), (False, "slash-command"))
        self.assertEqual(guard._should_research("/help zeig mir die Befehle"), (False, "slash-command"))

    def test_local_infrastructure_prompts_do_not_trigger_web_search(self):
        examples = [
            "Hast du Zugriff auf Ares?",
            "Kannst du Ares erreichen?",
            "Wie ist der Status der Verbindung zu Goliath?",
            "Wie ist die IP von Ares?",
            "Welche Tailscale-IP hat Goliath?",
            "Was ist der SSH-Port von Ares?",
            "Ares IP bitte",
            "Wie ist Ares erreichbar?",
            "Wie erreiche ich Ares?",
            "Wie komme ich auf Goliath?",
        ]
        for prompt in examples:
            with self.subTest(prompt=prompt):
                should, reason = guard._should_research(prompt)
                self.assertFalse(should)
                self.assertEqual(reason, "local-infrastructure")

    def test_speech_wrappers_are_removed_before_classification_and_query_building(self):
        prompt = 'Audio: "Wer ist Bürgermeister von Forchheim?"'
        self.assertEqual(guard._clean_message_for_research(prompt), "Wer ist Bürgermeister von Forchheim?")
        self.assertEqual(guard._build_search_query(prompt), "Wer ist Bürgermeister von Forchheim?")
        self.assertTrue(guard._should_research(prompt)[0])

        transcript = "Transkript: Bürgermeister von Forchheim"
        self.assertEqual(guard._clean_message_for_research(transcript), "Bürgermeister von Forchheim")
        self.assertTrue(guard._should_research(transcript)[0])

    def test_current_factual_questions_still_trigger(self):
        self.assertTrue(guard._should_research("Wer ist aktuell Präsident von Frankreich?")[0])
        self.assertTrue(guard._should_research("Welche Version von Python ist aktuell?")[0])

    def test_source_followups_do_not_trigger_a_fresh_web_search(self):
        self.assertEqual(guard._should_research("Wo hast du die Info her?"), (False, "source-followup"))
        self.assertEqual(guard._should_research("Was waren deine Quellen?"), (False, "source-followup"))
        self.assertEqual(guard._should_research("/research Wo hast du die Info her?"), (True, "explicit"))

    def test_context_followups_do_not_trigger_literal_web_search(self):
        self.assertEqual(guard._should_research("Was hältst du davon?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Was sagst du dazu?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Wie findest du das?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("/research Was hältst du davon?"), (True, "explicit"))

    def test_source_followup_context_uses_last_research_decision(self):
        guard.DECISIONS.clear()
        guard._record_decision(
            "injected",
            "current-facts",
            provider="duckduckgo-html",
            query="Bürgermeister Forchheim",
            sources=[
                {
                    "title": "Stadt Forchheim Bürgermeister",
                    "url": "https://www.forchheim.de/rathaus-service/",
                    "snippet": "Offizielle Stadtverwaltung.",
                }
            ],
        )

        context = guard._format_source_followup_context()
        self.assertIn("Research Guard: Quellenstatus", context)
        self.assertIn("Bürgermeister Forchheim", context)
        self.assertIn("https://www.forchheim.de/rathaus-service/", context)
        self.assertIn("NICHT", context)

    def test_context_followup_context_uses_last_research_decision(self):
        guard.DECISIONS.clear()
        guard._record_decision(
            "injected",
            "factual-question",
            provider="duckduckgo-html",
            query="Wer ist Wal Timmy?",
            sources=[
                {
                    "title": "NDR Timmy",
                    "url": "https://www.ndr.de/",
                    "snippet": "Bericht über Timmy.",
                }
            ],
        )

        context = guard._format_context_followup_context()
        self.assertIn("Research Guard: Kontext-Follow-up", context)
        self.assertIn("Wer ist Wal Timmy?", context)
        self.assertIn("https://www.ndr.de/", context)
        self.assertIn("Suche NICHT", context)
        self.assertIn("Meinung", context)

    def test_status_tool_reports_recent_decisions(self):
        guard.DECISIONS.clear()
        guard._record_decision("skipped", "local-infrastructure", model="qwen")
        payload = guard.research_guard_status({"limit": 1})
        self.assertIn('"plugin": "research-guard"', payload)
        self.assertIn('"reason": "local-infrastructure"', payload)

    def test_scores_preferred_and_official_sources_above_weak_aggregators(self):
        old_preferred = os.environ.get("RESEARCH_GUARD_PREFERRED_DOMAINS")
        os.environ["RESEARCH_GUARD_PREFERRED_DOMAINS"] = "example.com"
        try:
            quality = guard._score_research_results(
                [
                    {
                        "title": "Official API Documentation",
                        "url": "https://docs.example.com/api",
                        "snippet": "Official documentation and release notes for Example.",
                    },
                    {
                        "title": "Top 10 Example alternatives",
                        "url": "https://alternativeto.net/software/example",
                        "snippet": "Best alternatives and deals.",
                    },
                ],
                "Example latest release",
            )
        finally:
            if old_preferred is None:
                os.environ.pop("RESEARCH_GUARD_PREFERRED_DOMAINS", None)
            else:
                os.environ["RESEARCH_GUARD_PREFERRED_DOMAINS"] = old_preferred

        self.assertEqual(quality["confidence"], "high")
        self.assertEqual(quality["results"][0]["url"], "https://docs.example.com/api")
        self.assertIn("preferred-domain", quality["results"][0]["quality"]["signals"])
        self.assertIn("documentation-source", quality["results"][0]["quality"]["signals"])
        self.assertEqual(quality["results"][1]["quality"]["confidence"], "low")

    def test_excludes_blocked_domains_from_usable_sources(self):
        old_blocked = os.environ.get("RESEARCH_GUARD_BLOCKED_DOMAINS")
        os.environ["RESEARCH_GUARD_BLOCKED_DOMAINS"] = "spam.example"
        try:
            quality = guard._score_research_results(
                [
                    {
                        "title": "Blocked result",
                        "url": "https://spam.example/article",
                        "snippet": "Looks relevant but must not be used.",
                    },
                    {
                        "title": "Government source",
                        "url": "https://data.gov/example",
                        "snippet": "Official population data.",
                    },
                ],
                "current population example",
            )
        finally:
            if old_blocked is None:
                os.environ.pop("RESEARCH_GUARD_BLOCKED_DOMAINS", None)
            else:
                os.environ["RESEARCH_GUARD_BLOCKED_DOMAINS"] = old_blocked

        self.assertEqual(quality["blocked_result_count"], 1)
        self.assertEqual(quality["usable_result_count"], 1)
        self.assertNotIn("https://spam.example/article", [item["url"] for item in quality["results"]])
        self.assertIn("Blocked domain", " ".join(quality["warnings"]))

    def test_prefers_municipal_sources_for_local_office_questions(self):
        quality = guard._score_research_results(
            [
                {
                    "title": "Forchheim mayor result",
                    "url": "https://example-news.test/forchheim-mayor",
                    "snippet": "News report about the mayoral election in Forchheim.",
                    "age": "2026-03-23",
                },
                {
                    "title": "Stadt Forchheim Bürgermeister",
                    "url": "https://www.forchheim.de/rathaus-service/stadtverwaltung/aemteruebersicht/buergermeister",
                    "snippet": "Offizielle Stadtverwaltung: Oberbürgermeisterin Martina Hebendanz.",
                    "age": "2026-05-01",
                },
            ],
            "Wer ist Bürgermeister von Forchheim?",
        )

        self.assertIn("forchheim.de", quality["results"][0]["url"])
        self.assertIn("municipal-source", quality["results"][0]["quality"]["signals"])
        self.assertIn("fresh-source", quality["results"][0]["quality"]["signals"])

    def test_dampens_repeated_sources_from_same_domain(self):
        quality = guard._score_research_results(
            [
                {
                    "title": "Official release notes",
                    "url": "https://docs.example.com/releases/1",
                    "snippet": "Official release notes for Example 1.0.",
                },
                {
                    "title": "Official release notes archive",
                    "url": "https://docs.example.com/releases/archive",
                    "snippet": "Official release notes for Example 1.0 archive.",
                },
            ],
            "Example latest release",
        )

        self.assertEqual(quality["unique_domain_count"], 1)
        self.assertEqual(quality["evidence_diversity"], "low")
        self.assertIn("Low evidence diversity", " ".join(quality["warnings"]))
        self.assertTrue(any("same-domain-duplicate" in item["quality"]["signals"] for item in quality["results"][1:]))

    def test_confidence_gate_and_multiple_source_requirement_helpers(self):
        self.assertTrue(guard._meets_min_confidence("high", "medium"))
        self.assertFalse(guard._meets_min_confidence("low", "medium"))

        old_require = os.environ.get("RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES")
        os.environ["RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES"] = "true"
        try:
            quality = guard._score_research_results(
                [
                    {
                        "title": "Official docs",
                        "url": "https://docs.example.com/release",
                        "snippet": "Official release notes.",
                    },
                ],
                "Example latest release",
            )
        finally:
            if old_require is None:
                os.environ.pop("RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES", None)
            else:
                os.environ["RESEARCH_GUARD_REQUIRE_MULTIPLE_SOURCES"] = old_require

        self.assertEqual(quality["confidence"], "low")
        self.assertIn("requires multiple usable sources", " ".join(quality["warnings"]))

    def test_injected_context_includes_quality_and_location_discipline(self):
        quality = guard._score_research_results(
            [
                {
                    "title": "Official city page",
                    "url": "https://www.forchheim.de/rathaus-service/",
                    "snippet": "Offizielle Stadtverwaltung Forchheim.",
                },
            ],
            "Wo liegt Forchheim?",
        )
        context = guard._format_context(
            {
                "success": True,
                "provider": "test",
                "query": "Wo liegt Forchheim?",
                "results": quality["results"],
            },
            "factual-question",
            "qwen",
            quality,
            "Wo liegt Forchheim?",
        )

        self.assertIn("Quellenbewertung:", context)
        self.assertIn("Qualität:", context)
        self.assertIn("Bei Ortsfragen", context)
        self.assertIn("Aktuelle Nutzerfrage: Wo liegt Forchheim?", context)


if __name__ == "__main__":
    unittest.main()
