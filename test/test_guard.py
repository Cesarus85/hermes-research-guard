from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
