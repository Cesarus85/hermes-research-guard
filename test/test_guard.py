from __future__ import annotations

import importlib.util
import json
import os
import tempfile
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

    def test_internal_hermes_notes_do_not_trigger_web_search(self):
        examples = [
            "[Note: model switch] da?",
            "accomplished [gateway restart note]",
            "Gateway restart note",
        ]
        for prompt in examples:
            with self.subTest(prompt=prompt):
                self.assertEqual(guard._should_research(prompt), (False, "internal-note"))

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
        self.assertEqual(
            guard._build_search_query(prompt),
            "Forchheim Bürgermeister Oberbürgermeister Rathaus offizielle Stadt Verwaltung",
        )
        self.assertTrue(guard._should_research(prompt)[0])

        transcript = "Transkript: Bürgermeister von Forchheim"
        self.assertEqual(guard._clean_message_for_research(transcript), "Bürgermeister von Forchheim")
        self.assertTrue(guard._should_research(transcript)[0])

    def test_current_factual_questions_still_trigger(self):
        self.assertTrue(guard._should_research("Wer ist aktuell Präsident von Frankreich?")[0])
        self.assertTrue(guard._should_research("Welche Version von Python ist aktuell?")[0])

    def test_research_mode_controls_question_heuristics(self):
        old = os.environ.get("RESEARCH_GUARD_MODE")
        try:
            os.environ["RESEARCH_GUARD_MODE"] = "conservative"
            self.assertEqual(guard._should_research("Was ist ein Axolotl?"), (False, "conservative-no-trigger"))
            self.assertTrue(guard._should_research("Wie viele Einwohner hat Forchheim?")[0])

            os.environ["RESEARCH_GUARD_MODE"] = "aggressive"
            self.assertEqual(guard._should_research("Kann man das grob einordnen?"), (True, "aggressive-question"))
        finally:
            if old is None:
                os.environ.pop("RESEARCH_GUARD_MODE", None)
            else:
                os.environ["RESEARCH_GUARD_MODE"] = old

    def test_model_gate_recognizes_local_providers_and_cloud_markers(self):
        self.assertTrue(guard._is_local_or_small_model("qwen3:latest", "goliath"))
        self.assertTrue(guard._is_local_or_small_model("llama-3", "vllm"))
        self.assertFalse(guard._is_local_or_small_model("llama3:cloud", "ollama"))
        self.assertFalse(guard._is_local_or_small_model("gpt-5.2", "openai"))
        self.assertFalse(guard._should_skip_for_model_gate("gpt-5.2", "openai", True, "explicit"))

    def test_cloud_research_trigger_escape_hatch(self):
        old = os.environ.get("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS")
        os.environ["RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS"] = "true"
        try:
            self.assertFalse(guard._should_skip_for_model_gate("gpt-5.2", "openai", True, "current-facts"))
        finally:
            if old is None:
                os.environ.pop("RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS", None)
            else:
                os.environ["RESEARCH_GUARD_ALLOW_CLOUD_RESEARCH_TRIGGERS"] = old

    def test_followup_subject_carryover_builds_search_query_from_history(self):
        messages = [
            {"role": "user", "content": "Wer ist Wal Timmy?"},
            {"role": "assistant", "content": "Timmy war ein Buckelwal."},
        ]
        self.assertEqual(
            guard._build_search_query("Was ist mit ihm danach passiert?", messages),
            "Wal Timmy Was ist mit ihm danach passiert",
        )

        location_messages = [{"role": "user", "content": "Wo liegt Forchheim?"}]
        self.assertEqual(
            guard._build_search_query("Wie viele Einwohner hat es?", location_messages),
            "Forchheim Einwohner Einwohnerzahl Bevölkerung Statistik offizielle Stadt",
        )

        office_messages = [{"role": "user", "content": "Wer ist Bürgermeister von Forchheim?"}]
        self.assertEqual(
            guard._build_search_query("Wann wurde sie gewählt?", office_messages),
            "Forchheim Wann wurde sie gewählt",
        )

    def test_followup_subject_carryover_supports_content_parts(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Wer ist Martina Hebendanz?"}]},
        ]
        self.assertEqual(
            guard._build_search_query("Was ist über sie aktuell bekannt?", messages),
            "Martina Hebendanz Was ist über sie aktuell bekannt official current",
        )

    def test_query_rewrite_templates_add_official_source_hints(self):
        self.assertEqual(
            guard._build_search_query("Welche Version von Python ist aktuell?"),
            "Python official latest version release notes",
        )
        self.assertEqual(
            guard._build_search_query("Was kostet ChatGPT Team?"),
            "ChatGPT Team official pricing price",
        )
        self.assertEqual(
            guard._build_search_query("Wer ist Bürgermeister von Forchheim?"),
            "Forchheim Bürgermeister Oberbürgermeister Rathaus offizielle Stadt Verwaltung",
        )
        self.assertEqual(
            guard._query_debug("Welche Version von Python ist aktuell?")["rewrite_strategy"],
            "software-version",
        )

    def test_source_followups_do_not_trigger_a_fresh_web_search(self):
        self.assertEqual(guard._should_research("Wo hast du die Info her?"), (False, "source-followup"))
        self.assertEqual(guard._should_research("Was waren deine Quellen?"), (False, "source-followup"))
        self.assertEqual(guard._should_research("/research Wo hast du die Info her?"), (True, "explicit"))

    def test_research_guard_status_requests_do_not_become_source_followups(self):
        self.assertEqual(guard._should_research("Zeig mir den Research Guard Status"), (False, "status-request"))
        self.assertEqual(guard._should_research("Zeige research guard status"), (False, "status-request"))
        self.assertEqual(guard._should_research("research_guard_status"), (False, "status-request"))
        self.assertEqual(guard._should_research("Diagnose vom research guard bitte"), (False, "status-request"))
        self.assertFalse(guard._is_source_followup("Zeige research guard status"))

    def test_context_followups_do_not_trigger_literal_web_search(self):
        self.assertEqual(guard._should_research("Was hältst du davon?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Was sagst du dazu?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Wie findest du das?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Wie ist dein Eindruck von meiner Heimatstadt?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("Welchen Eindruck hast du von Forchheim?"), (False, "context-followup"))
        self.assertEqual(guard._should_research("/research Was hältst du davon?"), (True, "explicit"))

    def test_private_possessives_do_not_trigger_research(self):
        self.assertEqual(guard._should_research("Was ist meine Heimatstadt?"), (False, "looks-local-personal-writing-coding"))
        self.assertEqual(guard._should_research("Wie heißt meiner Meinung nach die beste Stadt?"), (False, "looks-local-personal-writing-coding"))

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
        self.assertIn("Erfinde keine persönlichen Details", context)
        self.assertIn("Gib keine Zeile `Quellen (Research Guard):` aus", context)

    def test_status_tool_reports_recent_decisions(self):
        guard.DECISIONS.clear()
        guard._record_decision("skipped", "local-infrastructure", model="qwen")
        payload = guard.research_guard_status({"limit": 1})
        self.assertIn('"plugin": "research-guard"', payload)
        self.assertIn(f'"version": "{guard.__version__}"', payload)
        self.assertIn('"status_version": 2', payload)
        self.assertIn('"skipped_turns_inject_context_by_default": false', payload)
        self.assertIn('"reason": "local-infrastructure"', payload)
        self.assertIn('"response_policy"', payload)
        self.assertIn('"status_buffer"', payload)
        self.assertIn('"summary"', payload)

    def test_status_request_context_embeds_diagnostics(self):
        guard.DECISIONS.clear()
        guard._record_decision("injected", "factual-question", model="qwen", query="Meteora tracklist")

        context = guard._format_status_request_context()

        self.assertIn("Research Guard: Diagnose-Status", context)
        self.assertIn('"status_version": 2', context)
        self.assertIn('"reason": "factual-question"', context)
        self.assertIn("Status-JSON BEGIN", context)
        self.assertIn("Benenne Felder nicht um", context)

    def test_active_research_context_has_turn_boundary_and_required_sources(self):
        payload = {
            "success": True,
            "provider": "hermes-web",
            "query": "Wo liegt Forchheim?",
            "results": [
                {
                    "title": "Forchheim",
                    "url": "https://example.com/forchheim",
                    "snippet": "Forchheim liegt in Oberfranken.",
                }
            ],
        }
        quality = {
            "confidence": "medium",
            "score": 60,
            "usable_result_count": 1,
            "result_count": 1,
            "evidence_diversity": "low",
            "unique_domain_count": 1,
            "duplicate_cluster_count": 0,
            "warnings": [],
            "results": payload["results"],
        }

        context = guard._format_context(payload, "factual-question", "qwen", quality, "Wo liegt Forchheim?")

        self.assertIn("[Research Guard aktiv]", context)
        self.assertIn("[Research Guard: Web-Recherche-Kontext]", context)
        self.assertIn("Research-Guard-Kontexte, Quellenlisten, Statusdaten oder Diagnoseblöcke aus früheren Turns", context)
        self.assertIn("Quellenpflicht", context)
        self.assertIn("[/Research Guard: Web-Recherche-Kontext]", context)

    def test_no_research_context_invalidates_stale_research_sources(self):
        context = guard._format_no_research_context("no-trigger", "Hallo", "qwen", "ollama")

        self.assertIn("[Research Guard inaktiv für aktuelle Frage]", context)
        self.assertIn("KEIN neuer Research-Guard-Webkontext", context)
        self.assertIn("Quellen (Research Guard)", context)
        self.assertIn("Gib keine Zeile", context)
        self.assertIn("Grund: no-trigger", context)

    def test_no_research_response_is_opt_in(self):
        old = os.environ.get("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY")
        os.environ.pop("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", None)
        try:
            self.assertIsNone(guard._no_research_response("no-trigger", "Hallo", "qwen", "ollama"))
            os.environ["RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY"] = "true"
            response = guard._no_research_response("no-trigger", "Hallo", "qwen", "ollama")
            self.assertIsInstance(response, dict)
            self.assertIn("[Research Guard inaktiv für aktuelle Frage]", response["context"])
        finally:
            if old is None:
                os.environ.pop("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", None)
            else:
                os.environ["RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY"] = old

    def test_pre_hook_does_not_inject_no_research_boundary_by_default(self):
        guard.DECISIONS.clear()
        old = os.environ.get("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY")
        os.environ.pop("RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY", None)
        try:
            result = guard.pre_llm_research_guard("s1", "Hallo", "qwen", "ollama")
        finally:
            if old is not None:
                os.environ["RESEARCH_GUARD_INJECT_NO_RESEARCH_BOUNDARY"] = old

        self.assertIsNone(result)
        self.assertEqual(guard.DECISIONS[-1]["action"], "skipped")
        self.assertEqual(guard.DECISIONS[-1]["reason"], "too-short")

    def test_status_v2_adds_categories_evidence_and_redacted_prompt_preview(self):
        guard.DECISIONS.clear()
        guard._record_decision(
            "skipped",
            "local-infrastructure",
            model="qwen",
            provider="ollama",
            query_debug={
                "original_preview": "Wie ist die IP von Ares?",
                "cleaned_prompt": "Wie ist die IP von Ares?",
                "carried_subject": None,
                "final_query": "Wie ist die IP von Ares?",
                "history_available": False,
            },
            prompt="Mail test@example.com Token abcdefghijklmnopqrstuvwxyz1234567890 Telefon +49 123 456789",
        )
        status = json.loads(guard.research_guard_status({"limit": 1}))
        decision = status["decisions"][0]

        self.assertEqual(decision["category"], "checked_and_skipped")
        self.assertEqual(decision["visible_effect"], "none")
        self.assertEqual(decision["reason_summary"], "Die Frage betraf lokale Infrastruktur oder private Systemdetails und wurde nicht ins Web geschickt.")
        self.assertEqual(decision["visible_effect_summary"], "Es gab keinen sichtbaren Quellenkontext für die Modellantwort.")
        self.assertIn("nicht ins Web geschickt", decision["user_explanation"])
        self.assertEqual(decision["diagnostic"]["category"], "checked_and_skipped")
        self.assertFalse(decision["diagnostic"]["searched"])
        self.assertIn("user_explanation", decision["diagnostic"])
        self.assertIn("skipped research", decision["diagnostic"]["explanation"])
        self.assertIn("action=skipped", decision["evidence"])
        self.assertIn("query_debug", decision)
        self.assertIn("[redacted-email]", decision["prompt_preview"])
        self.assertIn("[redacted-token]", decision["prompt_preview"])
        self.assertIn("[redacted-phone]", decision["prompt_preview"])
        self.assertNotIn("test@example.com", decision["prompt_preview"])
        self.assertIn("cache", status)
        self.assertIn("config", status)
        self.assertIn("latest_explanation", status["summary"])

    def test_status_user_explanation_for_injected_research_decision(self):
        guard.DECISIONS.clear()
        guard._record_decision(
            "injected",
            "factual-risk",
            provider="duckduckgo-html",
            query="Wer ist Bürgermeister von Forchheim?",
            confidence="high",
            score=82,
            usable_result_count=3,
            blocked_result_count=0,
        )
        status = json.loads(guard.research_guard_status({"limit": 1}))
        decision = status["decisions"][0]

        self.assertEqual(decision["visible_effect"], "sources_injected")
        self.assertIn("faktische oder aktuelle Wissensfrage", decision["reason_summary"])
        self.assertIn("Quellen wurden", decision["visible_effect_summary"])
        self.assertIn("Quellenbewertung: high (82/100).", decision["user_explanation"])
        self.assertEqual(status["summary"]["latest_explanation"], decision["user_explanation"])

    def test_query_debug_is_redacted_when_stored_in_decisions(self):
        guard.DECISIONS.clear()
        guard._record_decision(
            "skipped",
            "no-trigger",
            query_debug={
                "original_preview": "Mail test@example.com",
                "cleaned_prompt": "Token abcdefghijklmnopqrstuvwxyz1234567890",
                "carried_subject": None,
                "final_query": "Telefon +49 123 456789",
                "history_available": False,
            },
        )
        decision = json.loads(guard.research_guard_status({"limit": 1}))["decisions"][0]

        self.assertEqual(decision["query_debug"]["original_preview"], "Mail [redacted-email]")
        self.assertIn("[redacted-token]", decision["query_debug"]["cleaned_prompt"])
        self.assertIn("[redacted-phone]", decision["query_debug"]["final_query"])

    def test_query_debug_reports_carried_subject_and_final_query(self):
        messages = [{"role": "user", "content": "Wer ist Wal Timmy?"}]
        debug = guard._query_debug("Was ist mit ihm danach passiert?", messages)

        self.assertEqual(debug["carried_subject"], "Wal Timmy")
        self.assertEqual(debug["final_query"], "Wal Timmy Was ist mit ihm danach passiert")
        self.assertTrue(debug["history_available"])

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
        self.assertIn("municipal-local", quality["query_profiles"])
        self.assertIn("municipal", quality["source_profiles"])

    def test_domain_profiles_prefer_package_and_release_sources_for_software(self):
        quality = guard._score_research_results(
            [
                {
                    "title": "Example package",
                    "url": "https://pypi.org/project/example/",
                    "snippet": "Official package release history and latest version.",
                    "age": "2026-05-12",
                },
                {
                    "title": "Example release notes",
                    "url": "https://github.com/example/example/releases",
                    "snippet": "Official changelog and release notes for Example.",
                    "age": "2026-05-12",
                },
                {
                    "title": "Top Example downloads",
                    "url": "https://softonic.com/example",
                    "snippet": "Download free Example alternatives.",
                    "age": "2026-05-12",
                },
            ],
            "Example latest version release notes",
        )

        self.assertIn("tech-software", quality["query_profiles"])
        self.assertEqual(quality["results"][0]["url"], "https://pypi.org/project/example/")
        self.assertIn("package-registry", quality["results"][0]["quality"]["profiles"])
        self.assertIn("package-registry-source", quality["results"][0]["quality"]["signals"])
        self.assertIn("release-notes", quality["source_profiles"])
        self.assertIn("weak-aggregator", quality["source_profiles"])

    def test_domain_profiles_prefer_official_pricing_sources(self):
        quality = guard._score_research_results(
            [
                {
                    "title": "ChatGPT Team pricing",
                    "url": "https://openai.com/chatgpt/pricing/",
                    "snippet": "Official pricing plans and subscription details.",
                    "age": "2026-05-10",
                },
                {
                    "title": "Best ChatGPT coupons",
                    "url": "https://coupon.example/chatgpt",
                    "snippet": "Best deals and coupons for subscriptions.",
                    "age": "2026-05-10",
                },
            ],
            "ChatGPT Team official pricing price",
        )

        self.assertIn("price-product", quality["query_profiles"])
        self.assertEqual(quality["results"][0]["url"], "https://openai.com/chatgpt/pricing/")
        self.assertIn("pricing", quality["results"][0]["quality"]["profiles"])
        self.assertIn("pricing-source", quality["results"][0]["quality"]["signals"])

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

    def test_provider_aware_cache_key_contains_provider_and_query_shape(self):
        old_cache = os.environ.get("RESEARCH_GUARD_CACHE_TTL_SECONDS")
        old_provider = os.environ.get("RESEARCH_GUARD_PROVIDER")
        os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = "3600"
        os.environ.pop("RESEARCH_GUARD_PROVIDER", None)
        original_load = guard._load_cache
        original_save = guard._save_cache
        original_duck = guard._duckduckgo_search
        saved = {}
        try:
            guard._load_cache = lambda: {
                "provider=duckduckgo-html:limit=3:deep=off:query=forchheim": {
                    "ts": 9_999_999_999,
                    "payload": {
                        "success": True,
                        "provider": "duckduckgo-html",
                        "query": "Forchheim",
                        "results": [{"title": "Cached", "url": "https://example.com", "snippet": "Cached result."}],
                        "cached": False,
                    },
                }
            }
            guard._save_cache = lambda cache: saved.update(cache)
            guard._duckduckgo_search = lambda query, limit: []
            payload = guard._search("Forchheim", 3)
        finally:
            guard._load_cache = original_load
            guard._save_cache = original_save
            guard._duckduckgo_search = original_duck
            if old_cache is None:
                os.environ.pop("RESEARCH_GUARD_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = old_cache
            if old_provider is None:
                os.environ.pop("RESEARCH_GUARD_PROVIDER", None)
            else:
                os.environ["RESEARCH_GUARD_PROVIDER"] = old_provider

        self.assertTrue(payload["cached"])
        self.assertEqual(payload["provider"], "duckduckgo-html")
        self.assertEqual(payload["cache_key"], "provider=duckduckgo-html:limit=3:deep=off:query=forchheim")

    def test_cache_pruning_respects_max_entries_and_profile_ttl(self):
        old_max = os.environ.get("RESEARCH_GUARD_CACHE_MAX_ENTRIES")
        old_ttl = os.environ.get("RESEARCH_GUARD_CACHE_TTL_SECONDS")
        old_current_ttl = os.environ.get("RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS")
        try:
            os.environ["RESEARCH_GUARD_CACHE_MAX_ENTRIES"] = "20"
            os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = "3600"
            os.environ["RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS"] = "60"
            cache = {
                f"provider=duckduckgo-html:limit=3:deep=off:query=stable fact {idx}": {"ts": 1000 - idx, "payload": {}}
                for idx in range(25)
            }
            cache["provider=duckduckgo-html:limit=3:deep=off:query=latest price example"] = {"ts": 930, "payload": {}}
            pruned = guard._prune_cache(cache, now=1000)
        finally:
            if old_max is None:
                os.environ.pop("RESEARCH_GUARD_CACHE_MAX_ENTRIES", None)
            else:
                os.environ["RESEARCH_GUARD_CACHE_MAX_ENTRIES"] = old_max
            if old_ttl is None:
                os.environ.pop("RESEARCH_GUARD_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = old_ttl
            if old_current_ttl is None:
                os.environ.pop("RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS", None)
            else:
                os.environ["RESEARCH_GUARD_CACHE_TTL_CURRENT_SECONDS"] = old_current_ttl

        self.assertEqual(len(pruned), 20)
        self.assertIn("provider=duckduckgo-html:limit=3:deep=off:query=stable fact 0", pruned)
        self.assertNotIn("provider=duckduckgo-html:limit=3:deep=off:query=stable fact 24", pruned)
        self.assertNotIn("provider=duckduckgo-html:limit=3:deep=off:query=latest price example", pruned)

    def test_cache_can_be_disabled_without_writing_new_entries(self):
        old_cache = os.environ.get("RESEARCH_GUARD_CACHE_TTL_SECONDS")
        original_load = guard._load_cache
        original_save = guard._save_cache
        original_order = guard._provider_order
        original_run = guard._run_provider
        saved = []
        try:
            os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = "0"
            guard._load_cache = lambda: {}
            guard._save_cache = lambda cache: saved.append(cache)
            guard._provider_order = lambda: ["duckduckgo"]
            guard._run_provider = lambda provider, query, limit: [{"title": "Fresh", "url": "https://example.com", "snippet": "ok"}]
            payload = guard._search("Forchheim", 3)
        finally:
            guard._load_cache = original_load
            guard._save_cache = original_save
            guard._provider_order = original_order
            guard._run_provider = original_run
            if old_cache is None:
                os.environ.pop("RESEARCH_GUARD_CACHE_TTL_SECONDS", None)
            else:
                os.environ["RESEARCH_GUARD_CACHE_TTL_SECONDS"] = old_cache

        self.assertTrue(payload["success"])
        self.assertFalse(saved)

    def test_provider_order_honors_configuration_and_optional_providers(self):
        old_provider = os.environ.get("RESEARCH_GUARD_PROVIDER")
        old_brave = os.environ.get("BRAVE_API_KEY")
        old_searx = os.environ.get("RESEARCH_GUARD_SEARXNG_URL")
        original_wsp = guard._web_search_plus_available
        try:
            os.environ["RESEARCH_GUARD_PROVIDER"] = "brave"
            self.assertEqual(guard._provider_order(), ["brave"])

            os.environ["RESEARCH_GUARD_PROVIDER"] = "auto"
            os.environ["BRAVE_API_KEY"] = "test-key"
            os.environ["RESEARCH_GUARD_SEARXNG_URL"] = "https://searx.example"
            guard._web_search_plus_available = lambda: True
            self.assertEqual(
                guard._provider_order(),
                ["web_search_plus", "brave", "hermes", "searxng", "duckduckgo"],
            )
        finally:
            guard._web_search_plus_available = original_wsp
            if old_provider is None:
                os.environ.pop("RESEARCH_GUARD_PROVIDER", None)
            else:
                os.environ["RESEARCH_GUARD_PROVIDER"] = old_provider
            if old_brave is None:
                os.environ.pop("BRAVE_API_KEY", None)
            else:
                os.environ["BRAVE_API_KEY"] = old_brave
            if old_searx is None:
                os.environ.pop("RESEARCH_GUARD_SEARXNG_URL", None)
            else:
                os.environ["RESEARCH_GUARD_SEARXNG_URL"] = old_searx

    def test_search_falls_back_through_configured_provider_chain(self):
        original_load = guard._load_cache
        original_save = guard._save_cache
        original_order = guard._provider_order
        original_run = guard._run_provider
        try:
            guard._load_cache = lambda: {}
            guard._save_cache = lambda cache: None
            guard._provider_order = lambda: ["brave", "duckduckgo"]

            def fake_run(provider, query, limit):
                if provider == "brave":
                    raise RuntimeError("missing key")
                return [{"title": "Fallback", "url": "https://example.com", "snippet": "ok", "age": "2026-05-13"}]

            guard._run_provider = fake_run
            payload = guard._search("Forchheim", 3)
        finally:
            guard._load_cache = original_load
            guard._save_cache = original_save
            guard._provider_order = original_order
            guard._run_provider = original_run

        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider"], "duckduckgo-html")
        self.assertEqual(payload["provider_chain"], ["brave", "duckduckgo-html"])
        self.assertIn("brave: missing key", payload["fallback_errors"])
        self.assertEqual(payload["results"][0]["age"], "2026-05-13")

    def test_search_result_normalization_supports_common_provider_shapes(self):
        results = guard._extract_web_results(
            {
                "data": {
                    "web": [
                        {
                            "name": "Example <b>Title</b>",
                            "link": "https://example.com",
                            "description": "Example <em>snippet</em>",
                            "published": "2026-05-13",
                        }
                    ]
                }
            },
            5,
        )

        self.assertEqual(results[0]["title"], "Example Title")
        self.assertEqual(results[0]["url"], "https://example.com")
        self.assertEqual(results[0]["snippet"], "Example snippet")
        self.assertEqual(results[0]["age"], "2026-05-13")

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
        self.assertIn("Quellenprofile:", context)
        self.assertIn("Qualität:", context)
        self.assertIn("Bei Ortsfragen", context)
        self.assertIn("Aktuelle Nutzerfrage: Wo liegt Forchheim?", context)

    def test_deep_fetch_triggers_for_tracklists_and_context_includes_fetched_sources(self):
        self.assertEqual(guard._should_deep_fetch("Wie ist die Tracklist von Meteora?")[0], True)
        quality = guard._score_research_results(
            [
                {
                    "title": "Meteora album",
                    "url": "https://example.com/meteora",
                    "snippet": "Album page with track listing.",
                },
            ],
            "Meteora tracklist",
        )
        context = guard._format_context(
            {
                "success": True,
                "provider": "test",
                "query": "Meteora tracklist",
                "results": quality["results"],
            },
            "general-knowledge",
            "qwen",
            quality,
            "Wie ist die Tracklist von Meteora?",
            [
                {
                    "title": "Meteora - Linkin Park",
                    "url": "https://example.com/meteora",
                    "text": "Original track listing: 1. Foreword 2. Don't Stay 3. Somewhere I Belong",
                }
            ],
        )

        self.assertIn("Tracklist-Pflicht", context)
        self.assertIn("Vertiefte Quellen-Auszüge", context)
        self.assertIn("Original track listing", context)

    def test_deep_fetch_profile_changes_cache_key_shape(self):
        profile = guard._deep_fetch_profile(True)
        self.assertIn("pages=", profile)
        self.assertIn("chars=", profile)

    def test_structured_tracklist_extraction_and_context_output(self):
        tracklist = guard._extract_structured_tracklist(
            "1. Foreword\n2. Don't Stay\n3. Somewhere I Belong\n4. Lying from You"
        )
        self.assertEqual(tracklist[1]["title"], "Don't Stay")
        quality = guard._score_research_results(
            [{"title": "Meteora", "url": "https://example.com/meteora", "snippet": "Track listing."}],
            "Meteora tracklist",
        )
        context = guard._format_context(
            {"success": True, "provider": "test", "query": "Meteora tracklist", "results": quality["results"]},
            "general-knowledge",
            "qwen",
            quality,
            "Wie ist die Tracklist von Meteora?",
            [{"title": "Meteora", "url": "https://example.com/meteora", "text": "excerpt", "structured_tracklist": tracklist}],
        )
        self.assertIn("Strukturierte Tracklist-Kandidaten", context)
        self.assertIn("2. Don't Stay", context)

    def test_route_planning_prompt_detection_and_extraction(self):
        prompt = "Plane eine Fahrt von Forchheim nach Berlin mit Ladeplanung für ein E-Auto."

        self.assertTrue(guard._is_route_planning_prompt(prompt))
        self.assertFalse(guard._is_route_planning_prompt("Wo liegt Forchheim?"))
        self.assertTrue(guard._is_route_planning_prompt("Plane eine Route von Forchheim nach Berlin mit Tankplanung."))

        request = guard._extract_route_request(prompt)
        self.assertEqual(request["origin"], "Forchheim")
        self.assertEqual(request["destination"], "Berlin")
        self.assertIn("ladeplanung", request["preferences"]["ev_or_fuel_terms_detected"])
        self.assertTrue(request["needs_ev_chargers"])
        self.assertFalse(request["needs_fuel_stops"])

        fuel_request = guard._extract_route_request("Plane eine Route von Forchheim nach Berlin mit Tankstopps.")
        self.assertFalse(fuel_request["needs_ev_chargers"])
        self.assertTrue(fuel_request["needs_fuel_stops"])

    def test_route_planning_supports_plain_route_without_stops(self):
        prompt = "Plane die Route von Forchheim nach Riva del Garda."

        self.assertTrue(guard._is_route_planning_prompt(prompt))
        request = guard._extract_route_request(prompt)

        self.assertEqual(request["origin"], "Forchheim")
        self.assertEqual(request["destination"], "Riva del Garda")
        self.assertFalse(request["needs_ev_chargers"])
        self.assertFalse(request["needs_fuel_stops"])

    def test_route_planning_keeps_combustion_vehicle_context_generic(self):
        prompt = "Plane die Route von Forchheim nach Riva del Garda mit einem VW Golf."

        self.assertTrue(guard._is_route_planning_prompt(prompt))
        request = guard._extract_route_request(prompt)

        self.assertFalse(request["needs_ev_chargers"])
        self.assertFalse(request["needs_fuel_stops"])
        self.assertEqual(request["preferences"]["vehicle_hint"], "VW Golf")

    def test_route_planning_detects_ev_from_battery_and_vehicle_context(self):
        prompt = (
            "plane die Route von Forchheim nach Riva del Garda. Ich fahre mit einem "
            "VW ID 7 mit 77 KWH Batterie. Das Auto ist vollbeladen und es sind 4 Personen mit mir."
        )

        self.assertTrue(guard._is_route_planning_prompt(prompt))
        request = guard._extract_route_request(prompt)

        self.assertEqual(request["origin"], "Forchheim")
        self.assertEqual(request["destination"], "Riva del Garda")
        self.assertTrue(request["needs_ev_chargers"])
        self.assertEqual(request["preferences"]["battery_kwh"], 77)
        self.assertIn("ID 7", request["preferences"]["vehicle_hint"])
        self.assertEqual(request["preferences"]["passengers"], 4)
        self.assertTrue(request["preferences"]["loaded_vehicle"])

    def test_route_planning_detects_common_kw_battery_typo(self):
        request = guard._extract_route_request(
            "Plane die Route von Forchheim nach Riva del Garda. Ich fahre mit einem VW ID 7 mit 77 kw Batterie."
        )

        self.assertTrue(request["needs_ev_chargers"])
        self.assertEqual(request["preferences"]["battery_kwh"], 77)

    def test_route_planning_does_not_treat_charging_power_as_battery_size(self):
        request = guard._extract_route_request(
            "Plane die Route von Forchheim nach Riva del Garda mit Ladeplanung. Tesla Supercharger bis 125 kW."
        )

        self.assertTrue(request["needs_ev_chargers"])
        self.assertNotIn("battery_kwh", request["preferences"])

    def test_route_planning_detects_full_start_battery(self):
        request = guard._extract_route_request(
            "Plane die Route von Forchheim nach Riva del Garda mit einem VW ID 7. Ich starte mit vollem Akku."
        )

        self.assertEqual(request["preferences"]["start_soc_percent"], 100)

    def test_route_energy_estimate_provides_range_plausibility_math(self):
        estimate = guard._route_energy_estimate(
            {"distance_meters": 588000},
            {"battery_kwh": 77, "loaded_vehicle": True, "passengers": 4},
        )

        self.assertEqual(estimate["consumption_kwh_per_100km_band"], [18.0, 24.0])
        self.assertEqual(estimate["full_battery_range_km_band"], [321, 428])
        self.assertEqual(estimate["route_energy_need_kwh_band"], [106, 141])
        self.assertEqual(estimate["mathematical_minimum_midroute_charges"], 1)

    def test_enabled_route_planning_without_api_key_injects_guardrail_context(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        old_rg_key = os.environ.get("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY")
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)

            result = guard.pre_llm_research_guard(
                "s1",
                "Plane eine Route von Forchheim nach Berlin mit Ladeplanung für ein E-Auto mit 77 kWh Batterie.",
                "qwen3",
                "ollama",
            )
        finally:
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key
            if old_rg_key is None:
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = old_rg_key

        self.assertIsInstance(result, dict)
        self.assertIn("Routenplanung nicht ausgeführt", result["context"])
        self.assertIn("Google Maps API key", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-planning-missing-api-key")

    def test_route_planning_context_is_injected_from_google_payload(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_payload = guard._route_planning_payload
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
            guard._route_planning_payload = lambda origin, destination, needs_ev=True, needs_fuel=False: {
                "success": True,
                "provider": "google-maps",
                "origin": origin,
                "destination": destination,
                "route": {
                    "distance_meters": 410000,
                    "duration_seconds": 14400,
                    "static_duration_seconds": 13800,
                },
                "chargers": [
                    {
                        "name": "Example Fast Charge",
                        "address": "A9 Rastanlage Beispiel",
                        "rating": 4.4,
                        "google_maps_uri": "https://maps.google.com/?cid=123",
                        "route_position": "middle-route-area",
                        "route_progress_percent_approx": 50,
                        "connectors": [
                            {
                                "type": "EV_CONNECTOR_TYPE_CCS_COMBO_2",
                                "count": 4,
                                "available_count": 2,
                                "max_charge_rate_kw": 300,
                            }
                        ],
                    }
                ],
                "fuel_stops": [
                    {
                        "name": "Example Fuel",
                        "address": "A9 Tankstelle Beispiel",
                        "rating": 4.1,
                        "google_maps_uri": "https://maps.google.com/?cid=456",
                        "fuel_prices": [],
                    }
                ] if needs_fuel else [],
                "route_steps": {
                    "count": 2,
                    "shown": 2,
                    "truncated": False,
                    "steps": [
                        {"index": 1, "instruction": "Auf A73 Richtung Nürnberg fahren", "distance": "35 km", "static_duration": "25 min"},
                        {"index": 2, "instruction": "Auf A9 Richtung München wechseln", "distance": "170 km", "static_duration": "1 h 40 min"},
                    ],
                },
                "route_corridor": {
                    "items": ["A73", "A9"],
                    "text": "A73 -> A9",
                    "source": "google-routes-steps",
                    "truncated": False,
                },
                "warnings": [],
                "cached": False,
                "cache_key": "route=test",
            }

            result = guard.pre_llm_research_guard(
                "s1",
                "Plane eine Route von Forchheim nach Berlin mit Ladeplanung für ein E-Auto mit 77 kWh Batterie.",
                "qwen3",
                "ollama",
            )
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertIsInstance(result, dict)
        self.assertIn("Research Guard: Routen-Kontext", result["context"])
        self.assertIn("410 km", result["context"])
        self.assertIn("Example Fast Charge", result["context"])
        self.assertIn("KEINE optimierte Stoppreihenfolge", result["context"])
        self.assertIn("Nenne ausschließlich die unten aufgeführten Places-Kandidaten", result["context"])
        self.assertIn("keine Kilometerangaben oder Zeitangaben zwischen Start, Kandidaten und Ziel", result["context"])
        self.assertIn("keine echte ABRP-/Live-Ladeplanung", result["context"])
        self.assertIn("Energie-Plausibilitätsrechnung", result["context"])
        self.assertIn("full_battery_range_km_band", result["context"])
        self.assertIn("range_km = battery_kwh / consumption_kwh_per_100km * 100", result["context"])
        self.assertIn("Bewertungssprache", result["context"])
        self.assertIn("plausibel zu prüfen", result["context"])
        self.assertIn("Schreibe nicht `Empfehlung`, `ideal`, `beste Option`, `hohe Verfügbarkeit`, `der ID.7 lädt hier schnell`", result["context"])
        self.assertIn("Start-Ladepunkt-Regel", result["context"])
        self.assertIn("keine Werte wie `20-80%`, `20-30 Min`, `ankommen mit 15-25%`", result["context"])
        self.assertIn("Connector-Regel", result["context"])
        self.assertIn("Places meldet verfügbar/gesamt 2/4", result["context"])
        self.assertIn("nicht live garantiert; nicht als belegt lesen", result["context"])
        self.assertNotIn("frei/gesamt", result["context"])
        self.assertIn("Standort-Komfort-Regel", result["context"])
        self.assertIn("Tesla-CCS-Regel", result["context"])
        self.assertIn("Streckenverlauf aus Google Routes", result["context"])
        self.assertIn("bewusst NICHT in den Antwortkontext aufgenommen", result["context"])
        self.assertIn("Geprüfte Verlaufskette aus Google Routes: A73 -> A9", result["context"])
        self.assertIn("Verlaufsketten-Regel", result["context"])
        self.assertNotIn("Auf A73 Richtung Nürnberg fahren", result["context"])
        self.assertIn("Maut-/Kosten-Regel", result["context"])
        self.assertIn("nur als nummerierte `Google-Routes-Schritte`", result["context"])
        self.assertIn("KEINE eigene kompakte Autobahnkette", result["context"])
        self.assertIn("Research Guard hat dazu keine offiziellen Maut-/Vignetten-/Höhendaten injiziert", result["context"])
        self.assertIn("Maut/Vignette wurde von Research Guard nicht geprüft", result["context"])
        self.assertIn("Stopppositions-Regel", result["context"])
        self.assertIn("Mehrstopps-Regel", result["context"])
        self.assertIn("Antwortvorlage-Pflicht", result["context"])
        self.assertIn("Route-Rubrik-Regel", result["context"])
        self.assertIn("Geprüfte Verlaufskette", result["context"])
        self.assertIn("`Route`, `Energie-Check`, `Ladepunkt-Kandidaten`, `Grobe Einordnung`, `Nicht von Research Guard geprüft`, `Datenquelle`", result["context"])
        self.assertIn("Eine `Streckenverlauf`-Rubrik darf nur erscheinen", result["context"])
        self.assertIn("Maut-/Vignetten-Rubrik darf nur erscheinen", result["context"])
        self.assertIn("Verbotene-Rubriken-Regel", result["context"])
        self.assertIn("Grobe-Einordnung-Regel", result["context"])
        self.assertIn("keine `das sollte reichen/durchbringen`-Aussage", result["context"])
        self.assertIn("Biete nicht an, ABRP, PlugShare, VW-App", result["context"])
        self.assertIn("Position: middle-route-area (~50%)", result["context"])
        self.assertIn("Datenquelle (Research Guard): Google Maps Platform Routes/Places", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["action"], "injected")
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-planning")
        self.assertEqual(guard.DECISIONS[-1]["route_planning"]["charger_candidate_count"], 1)

    def test_route_context_includes_google_steps_only_for_explicit_route_course_request(self):
        context = guard._format_route_context(
            {
                "provider": "google-maps",
                "origin": "Forchheim",
                "destination": "Berlin",
                "route": {"distance_meters": 410000, "duration_seconds": 14400, "static_duration_seconds": 13800},
                "chargers": [],
                "fuel_stops": [],
                "route_steps": {
                    "count": 1,
                    "shown": 1,
                    "truncated": False,
                    "steps": [{"index": 1, "instruction": "Auf A73 Richtung Nürnberg fahren", "distance": "35 km", "static_duration": "25 min"}],
                },
                "warnings": [],
                "cached": False,
            },
            {
                "origin": "Forchheim",
                "destination": "Berlin",
                "needs_ev_chargers": False,
                "needs_fuel_stops": False,
                "preferences": {},
                "prompt": "Zeig mir den Streckenverlauf von Forchheim nach Berlin.",
            },
            "qwen3",
        )

        self.assertIn("Streckenverlauf aus Google Routes", context)
        self.assertIn("Auf A73 Richtung Nürnberg fahren", context)
        self.assertNotIn("bewusst NICHT in den Antwortkontext aufgenommen", context)

    def test_route_corridor_is_extracted_from_google_steps_only(self):
        route_steps = {
            "steps": [
                {"instruction": "Auf A73 Richtung Nürnberg fahren"},
                {"instruction": "Weiter auf die A9/E45"},
                {"instruction": "Auf A9 bleiben"},
                {"instruction": "Ausfahrt auf SS240 nehmen"},
            ]
        }

        corridor = guard._route_corridor_from_steps(route_steps)

        self.assertEqual(corridor["items"], ["A73", "A9", "E45", "SS240"])
        self.assertEqual(corridor["text"], "A73 -> A9 -> E45 -> SS240")
        self.assertIn("Google Routes", corridor["note"])

    def test_route_planning_context_supports_fuel_stops(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_payload = guard._route_planning_payload
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"

            def fake_payload(origin, destination, needs_ev=True, needs_fuel=False):
                self.assertFalse(needs_ev)
                self.assertTrue(needs_fuel)
                return {
                    "success": True,
                    "provider": "google-maps",
                    "origin": origin,
                    "destination": destination,
                    "route": {
                        "distance_meters": 410000,
                        "duration_seconds": 14400,
                        "static_duration_seconds": 13800,
                    },
                    "chargers": [],
                    "fuel_stops": [
                        {
                            "name": "Example Fuel",
                            "address": "A9 Tankstelle Beispiel",
                            "rating": 4.1,
                            "google_maps_uri": "https://maps.google.com/?cid=456",
                            "fuel_prices": [],
                        }
                    ],
                    "warnings": [],
                    "cached": False,
                }

            guard._route_planning_payload = fake_payload
            result = guard.pre_llm_research_guard(
                "s1",
                "Plane eine Route von Forchheim nach Berlin mit Tankstopps.",
                "qwen3",
                "ollama",
            )
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertIsInstance(result, dict)
        self.assertIn("Tankstopp-Kandidaten aus Places", result["context"])
        self.assertIn("Example Fuel", result["context"])
        self.assertNotIn("Ladepunkt-Kandidaten: Keine", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["route_planning"]["fuel_stop_candidate_count"], 1)

    def test_route_planning_context_supports_route_only(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_payload = guard._route_planning_payload
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"

            def fake_payload(origin, destination, needs_ev=True, needs_fuel=False):
                self.assertFalse(needs_ev)
                self.assertFalse(needs_fuel)
                return {
                    "success": True,
                    "provider": "google-maps",
                    "origin": origin,
                    "destination": destination,
                    "route": {
                        "distance_meters": 620000,
                        "duration_seconds": 25200,
                        "static_duration_seconds": 24000,
                    },
                    "chargers": [],
                    "fuel_stops": [],
                    "warnings": [],
                    "cached": False,
                }

            guard._route_planning_payload = fake_payload
            result = guard.pre_llm_research_guard(
                "s1",
                "Plane die Route von Forchheim nach Riva del Garda.",
                "qwen3",
                "ollama",
            )
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertIsInstance(result, dict)
        self.assertIn("Research Guard: Routen-Kontext", result["context"])
        self.assertIn("620 km", result["context"])
        self.assertNotIn("Ladepunkt-Kandidaten aus Places", result["context"])
        self.assertNotIn("Ladepunkt-Kandidaten: Keine", result["context"])
        self.assertNotIn("Tankstopp-Kandidaten aus Places", result["context"])
        self.assertNotIn("Tankstopp-Kandidaten: Keine", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["route_planning"]["charger_candidate_count"], 0)
        self.assertEqual(guard.DECISIONS[-1]["route_planning"]["fuel_stop_candidate_count"], 0)

    def test_route_diagnostic_parses_routes_response_shape(self):
        payload = guard._route_diagnostic_from_response(
            "Forchheim",
            "Riva del Garda",
            {
                "routes": [
                    {
                        "distanceMeters": 620000,
                        "duration": "25200s",
                        "staticDuration": "24000s",
                        "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                        "legs": [
                            {
                                "steps": [
                                    {
                                        "distanceMeters": 35000,
                                        "staticDuration": "1500s",
                                        "navigationInstruction": {"instructions": "Auf <b>A73</b> Richtung Nürnberg fahren"},
                                        "localizedValues": {"distance": {"text": "35 km"}, "staticDuration": {"text": "25 min"}},
                                    },
                                    {
                                        "distanceMeters": 170000,
                                        "staticDuration": "6000s",
                                        "navigationInstruction": {"instructions": "Weiter auf <b>A9</b> Richtung München"},
                                        "localizedValues": {"distance": {"text": "170 km"}, "staticDuration": {"text": "1 h 40 min"}},
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["distance_meters"], 620000)
        self.assertEqual(payload["route_shape"]["point_count"], 3)
        self.assertEqual(len(payload["route_shape"]["sample_points"]), 3)
        self.assertEqual(payload["route_steps"]["count"], 2)
        self.assertEqual(payload["route_steps"]["steps"][0]["instruction"], "Auf A73 Richtung Nürnberg fahren")
        self.assertEqual(payload["route_steps"]["steps"][0]["distance"], "35 km")
        self.assertEqual(payload["route_corridor"]["text"], "A73 -> A9")

    def test_google_routes_compute_requests_navigation_steps(self):
        old_timeout = os.environ.get("RESEARCH_GUARD_ROUTE_TIMEOUT_SECONDS")
        original_post = guard._json_post
        captured = {}
        try:
            os.environ["RESEARCH_GUARD_ROUTE_TIMEOUT_SECONDS"] = "1"

            def fake_post(url, payload, headers, timeout):
                captured.update({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
                return {"routes": []}

            guard._json_post = fake_post
            guard._google_routes_compute("Forchheim", "Riva del Garda", "test-key")
        finally:
            guard._json_post = original_post
            if old_timeout is None:
                os.environ.pop("RESEARCH_GUARD_ROUTE_TIMEOUT_SECONDS", None)
            else:
                os.environ["RESEARCH_GUARD_ROUTE_TIMEOUT_SECONDS"] = old_timeout

        field_mask = captured["headers"]["X-Goog-FieldMask"]
        self.assertIn("routes.legs.steps.navigationInstruction.instructions", field_mask)
        self.assertIn("routes.legs.steps.distanceMeters", field_mask)
        self.assertIn("routes.legs.steps.localizedValues.distance.text", field_mask)

    def test_balanced_route_stop_candidates_spread_across_samples(self):
        stops = [
            {"name": f"Start {idx}", "address": "Forchheim", "sample_index": 1, "google_maps_uri": f"https://maps.example/start-{idx}"}
            for idx in range(6)
        ] + [
            {"name": f"Middle {idx}", "address": "Route Mitte", "sample_index": 2, "google_maps_uri": f"https://maps.example/middle-{idx}"}
            for idx in range(2)
        ] + [
            {"name": f"End {idx}", "address": "Riva", "sample_index": 3, "google_maps_uri": f"https://maps.example/end-{idx}"}
            for idx in range(2)
        ]

        balanced = guard._balanced_route_stop_candidates(stops, 6)

        self.assertEqual(len(balanced), 6)
        self.assertEqual({item["sample_index"] for item in balanced}, {1, 2, 3})
        self.assertLessEqual(sum(1 for item in balanced if item["sample_index"] == 1), 2)

    def test_route_sample_position_marks_search_area_not_stop_order(self):
        self.assertEqual(guard._route_sample_position(1, 5)["route_position"], "start-area")
        self.assertEqual(guard._route_sample_position(3, 5)["route_position"], "middle-route-area")
        self.assertEqual(guard._route_sample_position(5, 5)["route_position"], "destination-area")
        self.assertIn("not an exact stop order", guard._route_sample_position(3, 5)["note"])

    def test_route_planning_payload_balances_chargers_across_route_samples(self):
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_routes = guard._google_routes_compute
        original_chargers = guard._google_places_nearby_ev_chargers
        try:
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
            guard._google_routes_compute = lambda origin, destination, api_key: {
                "routes": [
                    {
                        "distanceMeters": 620000,
                        "duration": "25200s",
                        "staticDuration": "24000s",
                        "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                    }
                ]
            }

            def fake_chargers(point, api_key, limit):
                if point["latitude"] < 39:
                    prefix = "start"
                elif point["latitude"] < 41:
                    prefix = "middle"
                else:
                    prefix = "end"
                return [
                    {
                        "displayName": {"text": f"{prefix} charger {idx}"},
                        "formattedAddress": prefix,
                        "googleMapsUri": f"https://maps.example/{prefix}-{idx}",
                    }
                    for idx in range(6)
                ]

            guard._google_places_nearby_ev_chargers = fake_chargers
            payload = guard._route_planning_payload("Forchheim", "Riva del Garda", True, False)
        finally:
            guard._google_routes_compute = original_routes
            guard._google_places_nearby_ev_chargers = original_chargers
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertEqual(len(payload["chargers"]), 6)
        self.assertGreater(payload["stop_coverage"]["chargers"]["sample_coverage"], 1)
        self.assertEqual({item["sample_index"] for item in payload["chargers"]}, {1, 2, 3})
        self.assertIn("route_position", payload["chargers"][0])
        self.assertEqual(payload["stop_coverage"]["sample_count"], 3)

    def test_route_test_tool_reports_missing_key(self):
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        old_rg_key = os.environ.get("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY")
        old_config_path = guard.CONFIG_PATH
        old_plugin_config_path = guard.PLUGIN_CONFIG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                guard.CONFIG_PATH = Path(tmp) / "research-guard.json"
                guard.PLUGIN_CONFIG_PATH = Path(tmp) / "missing-plugin-config.json"
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
                payload = json.loads(guard.research_guard_route_test({"origin": "Forchheim", "destination": "Riva del Garda"}))
        finally:
            guard.CONFIG_PATH = old_config_path
            guard.PLUGIN_CONFIG_PATH = old_plugin_config_path
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key
            if old_rg_key is None:
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = old_rg_key

        self.assertFalse(payload["ok"])
        self.assertIn("API key", payload["error"])

    def test_route_test_tool_calls_routes_api_when_key_configured(self):
        guard.DECISIONS.clear()
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_routes = guard._google_routes_compute
        try:
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
            guard._google_routes_compute = lambda origin, destination, api_key: {
                "routes": [
                    {
                        "distanceMeters": 620000,
                        "duration": "25200s",
                        "staticDuration": "24000s",
                        "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                    }
                ]
            }
            payload = json.loads(guard.research_guard_route_test({"origin": "Forchheim", "destination": "Riva del Garda"}))
        finally:
            guard._google_routes_compute = original_routes
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider"], "google-maps-routes")
        self.assertEqual(payload["distance_meters"], 620000)
        self.assertEqual(guard.DECISIONS[-1]["reason"], "manual research_guard_route_test tool call")

    def test_route_followup_reuses_previous_route_context_without_google(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        original_payload = guard._route_planning_payload
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            guard._record_decision(
                "injected",
                "route-planning",
                provider="google-maps",
                query="Forchheim -> Riva del Garda",
                route_planning={"origin": "Forchheim", "destination": "Riva del Garda", "charger_candidate_count": 1},
                route_context={
                    "origin": "Forchheim",
                    "destination": "Riva del Garda",
                    "route": {"distance_meters": 620000, "duration_seconds": 25200, "static_duration_seconds": 24000},
                    "request": {"needs_ev_chargers": True, "needs_fuel_stops": False, "preferences": {"battery_kwh": 77}},
                    "chargers": [{"name": "Example Fast Charge", "address": "A9 Beispiel", "connectors": [], "google_maps_uri": "https://maps.example/1"}],
                    "fuel_stops": [],
                    "route_steps": {
                        "count": 1,
                        "shown": 1,
                        "truncated": False,
                        "steps": [{"index": 1, "instruction": "Auf A73 Richtung Nürnberg fahren", "distance": "35 km", "static_duration": "25 min"}],
                    },
                    "warnings": [],
                    "provider": "google-maps",
                },
            )
            guard._route_planning_payload = lambda *args, **kwargs: self.fail("follow-up should not call Google")

            result = guard.pre_llm_research_guard(
                "s1",
                "Welche Ladestation würdest du bevorzugen?",
                "qwen3",
                "ollama",
            )
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled

        self.assertIsInstance(result, dict)
        self.assertIn("Research Guard: Routen-Follow-up", result["context"])
        self.assertIn("Example Fast Charge", result["context"])
        self.assertIn("keine optimierte Stoppreihenfolge", result["context"])
        self.assertIn("Erfinde keine zusätzlichen Ladeparks", result["context"])
        self.assertIn("Nenne keine 20-80%-Fenster", result["context"])
        self.assertIn("Startbereich-Ladepunkte sind bei vollem Startakku nur Vorab-Optionen", result["context"])
        self.assertIn("Gespeicherter Streckenverlauf aus Google Routes", result["context"])
        self.assertIn("bewusst NICHT in den Antwortkontext aufgenommen", result["context"])
        self.assertNotIn("Auf A73 Richtung Nürnberg fahren", result["context"])
        self.assertIn("Gib sie nur als nummerierte Schritte aus", result["context"])
        self.assertIn("keine eigene kompakte Autobahnkette", result["context"])
        self.assertIn("hohe Verfügbarkeit", result["context"])
        self.assertIn("Erfinde keine Vignettenpreise", result["context"])
        self.assertIn("Maut/Vignette nur als `nicht von Research Guard geprüft`", result["context"])
        self.assertIn("Biete nicht an, ABRP, PlugShare, VW-App", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-followup-context")

    def test_route_followup_recognizes_route_course_questions(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            guard._record_decision(
                "injected",
                "route-planning",
                provider="google-maps",
                query="Forchheim -> Riva del Garda",
                route_planning={"origin": "Forchheim", "destination": "Riva del Garda"},
                route_context={
                    "origin": "Forchheim",
                    "destination": "Riva del Garda",
                    "route": {"distance_meters": 620000, "duration_seconds": 25200},
                    "request": {"needs_ev_chargers": False, "needs_fuel_stops": False, "preferences": {}},
                    "route_steps": {
                        "count": 1,
                        "shown": 1,
                        "truncated": False,
                        "steps": [{"index": 1, "instruction": "Auf A73 Richtung Nürnberg fahren", "distance": "35 km"}],
                    },
                },
            )

            result = guard.pre_llm_research_guard(
                "s1",
                "Wie ist der Streckenverlauf?",
                "qwen3",
                "ollama",
            )
        finally:
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled

        self.assertIsInstance(result, dict)
        self.assertIn("Research Guard: Routen-Follow-up", result["context"])
        self.assertIn("Auf A73 Richtung Nürnberg fahren", result["context"])
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-followup-context")

    def test_route_followup_refreshes_google_for_return_trip(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_payload = guard._route_planning_payload
        calls = []
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
            guard._record_decision(
                "injected",
                "route-planning",
                provider="google-maps",
                query="Forchheim -> Riva del Garda",
                route_planning={"origin": "Forchheim", "destination": "Riva del Garda"},
                route_context={
                    "origin": "Forchheim",
                    "destination": "Riva del Garda",
                    "route": {"distance_meters": 620000, "duration_seconds": 25200, "static_duration_seconds": 24000},
                    "request": {"needs_ev_chargers": True, "needs_fuel_stops": False, "preferences": {"battery_kwh": 77}},
                    "chargers": [],
                    "fuel_stops": [],
                    "warnings": [],
                    "provider": "google-maps",
                },
            )

            def fake_payload(origin, destination, needs_ev=True, needs_fuel=False):
                calls.append((origin, destination, needs_ev, needs_fuel))
                return {
                    "success": True,
                    "provider": "google-maps",
                    "origin": origin,
                    "destination": destination,
                    "route": {"distance_meters": 625000, "duration_seconds": 26000, "static_duration_seconds": 24500},
                    "chargers": [],
                    "fuel_stops": [],
                    "warnings": [],
                    "cached": False,
                }

            guard._route_planning_payload = fake_payload
            result = guard.pre_llm_research_guard("s1", "Und zurück?", "qwen3", "ollama")
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertIsInstance(result, dict)
        self.assertEqual(calls, [("Riva del Garda", "Forchheim", True, False)])
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-planning-followup-refresh")
        self.assertTrue(guard.DECISIONS[-1]["route_planning"]["refresh"])

    def test_route_followup_refreshes_google_for_explicit_two_stop_request(self):
        guard.DECISIONS.clear()
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        original_payload = guard._route_planning_payload
        calls = []
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
            guard._record_decision(
                "injected",
                "route-planning",
                provider="google-maps",
                query="Forchheim -> Riva del Garda",
                route_planning={"origin": "Forchheim", "destination": "Riva del Garda"},
                route_context={
                    "origin": "Forchheim",
                    "destination": "Riva del Garda",
                    "route": {"distance_meters": 620000, "duration_seconds": 25200, "static_duration_seconds": 24000},
                    "request": {"needs_ev_chargers": True, "needs_fuel_stops": False, "preferences": {"battery_kwh": 77}},
                    "chargers": [],
                    "fuel_stops": [],
                    "warnings": [],
                    "provider": "google-maps",
                },
            )

            def fake_payload(origin, destination, needs_ev=True, needs_fuel=False):
                calls.append((origin, destination, needs_ev, needs_fuel))
                return {
                    "success": True,
                    "provider": "google-maps",
                    "origin": origin,
                    "destination": destination,
                    "route": {"distance_meters": 620000, "duration_seconds": 25200, "static_duration_seconds": 24000},
                    "chargers": [
                        {"name": "Mid Charger", "address": "Route", "connectors": [], "sample_index": 3, "route_position": "middle-route-area", "route_progress_percent_approx": 50}
                    ],
                    "fuel_stops": [],
                    "warnings": [],
                    "cached": False,
                }

            guard._route_planning_payload = fake_payload
            result = guard.pre_llm_research_guard("s1", "Kannst du mir den Verlauf mit zwei Ladestopps geben?", "qwen3", "ollama")
        finally:
            guard._route_planning_payload = original_payload
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_key

        self.assertIsInstance(result, dict)
        self.assertEqual(calls, [("Forchheim", "Riva del Garda", True, False)])
        self.assertEqual(guard.DECISIONS[-1]["reason"], "route-planning-followup-refresh")
        self.assertTrue(guard.DECISIONS[-1]["route_planning"]["refresh"])

    def test_route_planning_status_reports_config(self):
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY")
        try:
            os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = "true"
            os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = "test-key"
            status = json.loads(guard.research_guard_status({"limit": 1}))
        finally:
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = old_key

        self.assertTrue(status["config"]["route_planning"]["enabled"])
        self.assertTrue(status["config"]["route_planning"]["api_key_configured"])
        self.assertEqual(status["config"]["route_planning"]["provider"], "google-maps")
        self.assertFalse(status["config"]["route_planning"]["persistent_cache"])
        self.assertFalse(status["config"]["route_planning"]["include_fuel_options"])

    def test_route_planning_reads_persistent_config_without_env(self):
        old_config_path = guard.CONFIG_PATH
        old_plugin_config_path = guard.PLUGIN_CONFIG_PATH
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY")
        old_google_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "research-guard.json"
                config_path.write_text(
                    json.dumps(
                        {
                            "route_planning": {
                                "enabled": True,
                                "google_maps_api_key": "test-google-key",
                                "include_fuel_options": True,
                                "max_fuel_stops": 4,
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                guard.CONFIG_PATH = config_path
                guard.PLUGIN_CONFIG_PATH = Path(tmp) / "missing-plugin-config.json"
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)

                status = json.loads(guard.research_guard_status({"limit": 1}))
        finally:
            guard.CONFIG_PATH = old_config_path
            guard.PLUGIN_CONFIG_PATH = old_plugin_config_path
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = old_key
            if old_google_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_google_key

        self.assertTrue(status["config"]["route_planning"]["enabled"])
        self.assertTrue(status["config"]["route_planning"]["api_key_configured"])
        self.assertTrue(status["config"]["route_planning"]["include_fuel_options"])
        self.assertEqual(status["config"]["route_planning"]["max_fuel_stops"], 4)

    def test_config_tool_writes_persistent_route_config_and_masks_key(self):
        old_config_path = guard.CONFIG_PATH
        old_plugin_config_path = guard.PLUGIN_CONFIG_PATH
        old_enabled = os.environ.get("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING")
        old_key = os.environ.get("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY")
        old_google_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                guard.CONFIG_PATH = Path(tmp) / "research-guard.json"
                guard.PLUGIN_CONFIG_PATH = Path(tmp) / "missing-plugin-config.json"
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)

                payload = json.loads(
                    guard.research_guard_config(
                        {
                            "action": "set_route_planning",
                            "enabled": True,
                            "google_maps_api_key": "abcd1234secret",
                            "include_fuel_options": False,
                            "max_charger_searches": 2,
                        }
                    )
                )
                stored = json.loads(guard.CONFIG_PATH.read_text(encoding="utf-8"))
        finally:
            guard.CONFIG_PATH = old_config_path
            guard.PLUGIN_CONFIG_PATH = old_plugin_config_path
            if old_enabled is None:
                os.environ.pop("RESEARCH_GUARD_ENABLE_ROUTE_PLANNING", None)
            else:
                os.environ["RESEARCH_GUARD_ENABLE_ROUTE_PLANNING"] = old_enabled
            if old_key is None:
                os.environ.pop("RESEARCH_GUARD_GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["RESEARCH_GUARD_GOOGLE_MAPS_API_KEY"] = old_key
            if old_google_key is None:
                os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            else:
                os.environ["GOOGLE_MAPS_API_KEY"] = old_google_key

        self.assertTrue(payload["changed"])
        self.assertTrue(payload["effective_route_planning"]["enabled"])
        self.assertTrue(payload["effective_route_planning"]["api_key_configured"])
        self.assertNotIn("abcd1234secret", json.dumps(payload))
        self.assertEqual(stored["route_planning"]["google_maps_api_key"], "abcd1234secret")
        self.assertEqual(stored["route_planning"]["max_charger_searches"], 2)


if __name__ == "__main__":
    unittest.main()
