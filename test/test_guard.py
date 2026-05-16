from __future__ import annotations

import importlib.util
import json
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
        self.assertEqual(decision["diagnostic"]["category"], "checked_and_skipped")
        self.assertFalse(decision["diagnostic"]["searched"])
        self.assertIn("skipped research", decision["diagnostic"]["explanation"])
        self.assertIn("action=skipped", decision["evidence"])
        self.assertIn("query_debug", decision)
        self.assertIn("[redacted-email]", decision["prompt_preview"])
        self.assertIn("[redacted-token]", decision["prompt_preview"])
        self.assertIn("[redacted-phone]", decision["prompt_preview"])
        self.assertNotIn("test@example.com", decision["prompt_preview"])
        self.assertIn("cache", status)
        self.assertIn("config", status)

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


if __name__ == "__main__":
    unittest.main()
