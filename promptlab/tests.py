"""Tests for the Prompt Lab engine, provider routing, views and core regressions."""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from ai import providers as ai_providers
from ai.providers.base import AIProvider, AIResult, MissingConfigError
from promptlab.engine.analyzer import analyze_prompt, compare_versions, WEIGHTS
from promptlab.engine.mutations import mutate
from promptlab.engine.optimizer import optimize
from promptlab.engine.pipeline import build_prompt, generate_all_tiers
from promptlab.engine.workflows import run_workflow
from promptlab.models import Prompt, PromptTemplate, WorkflowRun
from promptlab.services import lab_stats
from wardrobe.models import Item

WEAK_PROMPT = "write something good about our product maybe"
STRONG_PROMPT = (
    "You are a senior conversion copywriter. Task: Write a 120-word product description "
    "for a stainless steel water bottle aimed at hikers.\n\nRequirements:\n- Maximum 120 words.\n"
    "- Avoid cliches.\n- Include one benefit-led bullet list with 3 bullets.\n\n"
    "Output format: Markdown with one headline and one paragraph."
)


class AnalyzerTests(TestCase):
    def test_scores_are_bounded_and_deterministic(self):
        first = analyze_prompt(STRONG_PROMPT)
        second = analyze_prompt(STRONG_PROMPT)
        self.assertEqual(first["score"], second["score"])
        self.assertTrue(0 <= first["score"] <= 100)
        self.assertEqual(len(first["metrics"]), len(WEIGHTS))

    def test_weak_prompt_scores_below_strong(self):
        weak = analyze_prompt(WEAK_PROMPT)
        strong = analyze_prompt(STRONG_PROMPT)
        self.assertLess(weak["score"], strong["score"])
        self.assertTrue(weak["missing"])

    def test_empty_prompt_scores_low(self):
        self.assertLessEqual(analyze_prompt("")["score"], 30)

    def test_report_contains_actionable_sections(self):
        report = analyze_prompt(WEAK_PROMPT)
        self.assertTrue(report["suggestions"])
        self.assertTrue(report["band"])

    def test_compare_versions_reports_delta(self):
        comparison = compare_versions(WEAK_PROMPT, STRONG_PROMPT)
        self.assertGreater(comparison["score_delta"], 0)
        self.assertGreaterEqual(comparison["sentences_added"], 0)


class PipelineTests(TestCase):
    def test_all_tiers_generated_with_sections(self):
        tiers = generate_all_tiers("write a blog post about hiking boots for beginners")
        for tier in ("basic", "improved", "expert", "maximum"):
            self.assertIn(tier, tiers)
            self.assertTrue(tiers[tier]["prompt"].strip())
        self.assertIn("role", tiers["expert"]["sections"])
        self.assertIn("task_decomposition", tiers["maximum"]["sections"])

    def test_intent_detection(self):
        result = build_prompt("fix this python bug in my function", tier="improved")
        self.assertEqual(result["intent"], "coding")
        self.assertIn("You are", result["prompt"])

    def test_language_and_tone_constraints_applied(self):
        result = build_prompt("write a product pitch", tier="expert", language="German",
                              tone="persuasive")
        self.assertIn("German", result["prompt"])
        self.assertIn("persuasive", result["prompt"].lower())

    def test_user_constraints_are_included(self):
        result = build_prompt("write an email", tier="improved",
                              constraints="Use UK English\nNo emojis")
        self.assertIn("UK English", result["prompt"])
        self.assertIn("No emojis", result["prompt"])

    def test_empty_idea_raises(self):
        with self.assertRaises(ValueError):
            build_prompt("   ")


class MutationTests(TestCase):
    def test_shorten_reduces_length(self):
        result = mutate(STRONG_PROMPT, "shorten")
        self.assertLess(len(result["text"]), len(STRONG_PROMPT))

    def test_tone_mutation(self):
        result = mutate(STRONG_PROMPT, "tone:casual")
        self.assertIn("<tone>", result["text"].lower())
        self.assertIn("conversational", result["text"].lower())

    def test_format_mutation(self):
        result = mutate(STRONG_PROMPT, "format:json")
        self.assertIn("output_format", result["text"].lower())

    def test_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            mutate(STRONG_PROMPT, "explode")


class OptimizerTests(TestCase):
    def test_optimization_improves_weak_prompt(self):
        outcome = optimize(WEAK_PROMPT, "professional")
        self.assertGreaterEqual(outcome["score_after"], outcome["score_before"])
        self.assertTrue(outcome["optimized"])
        self.assertTrue(outcome["techniques"])

    def test_all_levels_valid(self):
        for level in ("basic", "professional", "expert", "maximum"):
            outcome = optimize(WEAK_PROMPT, level)
            self.assertEqual(outcome["level"], level)


class WorkflowTests(TestCase):
    def test_local_workflow_completes(self):
        outcome = run_workflow(WEAK_PROMPT, "writing")
        self.assertEqual(len(outcome["steps"]), 4)
        self.assertTrue(outcome["final"])
        self.assertFalse(outcome["used_ai"])

    def test_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            run_workflow("text", "does-not-exist")


class ProviderRoutingTests(TestCase):
    class StubProvider(AIProvider):
        id = "stub"
        label = "Stub"
        capabilities = ("text",)
        default_model = "stub-1"
        calls = 0

        @classmethod
        def is_configured(cls):
            return True

        def complete(self, prompt, **kwargs):
            type(self).calls += 1
            return AIResult(provider=self.id, model=self.default_model,
                            text="stub says hi", ok=True)

    class BrokenProvider(StubProvider):
        id = "broken"
        label = "Broken"

        def complete(self, prompt, **kwargs):
            raise MissingConfigError("no key")

    def setUp(self):
        self._old_all = ai_providers.ALL_PROVIDERS
        self._old_instances = dict(ai_providers._INSTANCES)
        ai_providers._INSTANCES.clear()

    def tearDown(self):
        ai_providers.ALL_PROVIDERS = self._old_all
        ai_providers._INSTANCES.clear()
        ai_providers._INSTANCES.update(self._old_instances)

    def test_fallback_to_second_provider_on_failure(self):
        class Broken2(self.BrokenProvider):
            pass
        class Stub2(self.StubProvider):
            pass
        ai_providers.ALL_PROVIDERS = [Broken2, Stub2]
        result = ai_providers.complete_text("hello")
        self.assertTrue(result.ok)
        self.assertEqual(result.provider, "stub")
        self.assertEqual(result.attempts[0]["provider"], "broken")

    def test_no_providers_configured_returns_clean_error(self):
        class Unconfigured(self.StubProvider):
            id = "unconf"
            @classmethod
            def is_configured(cls):
                return False
        ai_providers.ALL_PROVIDERS = [Unconfigured]
        result = ai_providers.complete_text("hello")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "missing_config")
        self.assertIn("No AI provider is configured", result.error_message)


class PromptLabViewTests(TestCase):
    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")

    def test_studio_generates_tiers(self):
        response = self.client.post("/lab/studio/", {"idea": "write a resume summary for a barista"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Basic prompt")
        self.assertContains(response, "Why this prompt is better")

    def test_analyzer_scores_prompt(self):
        response = self.client.post("/lab/analyze/", {"text": STRONG_PROMPT})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Metric breakdown")

    def test_optimizer_flow(self):
        response = self.client.post("/lab/optimize/", {"text": WEAK_PROMPT, "level": "expert"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "optimization")

    def test_prompt_save_creates_version_history(self):
        self.client.post("/lab/prompts/add/", {"title": "Test prompt", "body": WEAK_PROMPT,
                                               "category": "other", "source": "manual"})
        prompt = Prompt.objects.get(title="Test prompt")
        self.assertEqual(prompt.versions.count(), 1)
        self.client.post(f"/lab/prompts/{prompt.pk}/edit/",
                         {"body": STRONG_PROMPT, "title": "Test prompt", "change_note": "v2"})
        self.assertEqual(prompt.versions.count(), 2)
        self.assertEqual(prompt.versions.first().version_number, 2)
        self.assertEqual(prompt.versions.order_by("version_number").first().body, WEAK_PROMPT)

    def test_duplicate_favorite_delete(self):
        prompt = Prompt.objects.create(title="Dup me", body=WEAK_PROMPT)
        self.client.post(f"/lab/prompts/{prompt.pk}/duplicate/")
        self.assertEqual(Prompt.objects.filter(title__startswith="Dup me").count(), 2)
        self.client.post(f"/lab/prompts/{prompt.pk}/favorite/")
        prompt.refresh_from_db()
        self.assertTrue(prompt.favorite)
        self.client.post(f"/lab/prompts/{prompt.pk}/delete/")
        self.assertFalse(Prompt.objects.filter(pk=prompt.pk).exists())

    def test_library_search_and_template_use(self):
        PromptTemplate.objects.create(title="Seo brief", category="content_writing",
                                      body="You are an SEO strategist...", tags="seo")
        response = self.client.get("/lab/library/", {"q": "seo"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seo brief")
        template = PromptTemplate.objects.get(title="Seo brief")
        # "Use" writes a new prompt, so GET must be rejected (405) - P1 #12.
        response = self.client.get(f"/lab/templates/{template.pk}/use/")
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Prompt.objects.filter(title="Seo brief").exists())
        response = self.client.post(f"/lab/templates/{template.pk}/use/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Prompt.objects.filter(title="Seo brief").exists())

    def test_compare_without_providers_is_graceful(self):
        response = self.client.post("/lab/compare/", {"text": STRONG_PROMPT})
        self.assertEqual(response.status_code, 200)

    def test_workflow_local_run(self):
        response = self.client.post("/lab/workflows/", {"text": WEAK_PROMPT, "preset": "polish"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Final score")

    def test_api_analyze_json(self):
        import json
        response = self.client.post("/lab/api/analyze/",
                                    json.dumps({"text": STRONG_PROMPT}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(0 <= data["report"]["score"] <= 100)

    def test_lab_dashboard_real_stats(self):
        Prompt.objects.create(title="Stat check", body=WEAK_PROMPT)
        response = self.client.get("/lab/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stat check")


class CoreRegressionTests(TestCase):
    """Original wardrobe features keep working after the upgrade."""

    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")

    def test_dashboard_renders_with_prompt_stats(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prompt Lab")

    def test_wardrobe_list(self):
        Item.objects.create(name="Blue shirt", category="shirt")
        response = self.client.get("/wardrobe/")
        self.assertContains(response, "Blue shirt")

    def test_outfit_save_endpoint(self):
        item = Item.objects.create(name="Test jacket", category="jacket", status="clean")
        response = self.client.post("/outfits/save/",
                                    {"occasion": "casual", "score": "88.5", "items": str(item.pk)})
        self.assertEqual(response.status_code, 302)
        from outfits.models import Outfit
        outfit = Outfit.objects.first()
        self.assertIsNotNone(outfit)
        self.assertIn(item, outfit.items.all())

    def test_planner_add_and_clear(self):
        from planner.models import Plan
        response = self.client.post("/planner/add/",
                                    {"date": "2099-01-01", "occasion": "office",
                                     "location": "HQ"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Plan.objects.filter(date="2099-01-01").exists())
        self.client.post("/planner/add/", {"date": "2099-01-01"})
        self.assertFalse(Plan.objects.filter(date="2099-01-01").exists())

    def test_weather_and_outfit_apis(self):
        for url in ("/api/items/", "/api/weather/", "/api/outfits/today/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)


class PromptLabOwnershipTests(TestCase):
    """Audit P0 #1 / P2 #22: prompts, logs and workflow runs are per-account."""

    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")
        self.alice = User.objects.create_user("alice", password="pw12345!")
        self.bob = User.objects.create_user("bob", password="pw12345!")

    def test_create_prompt_is_owned_by_the_signed_in_user(self):
        self.client.force_login(self.alice)
        self.client.post("/lab/prompts/add/", {"title": "Alice prompt",
                                               "body": STRONG_PROMPT,
                                               "goal": "coding"})
        prompt = Prompt.objects.get(title="Alice prompt")
        self.assertEqual(prompt.owner, self.alice)

    def test_anonymous_prompt_goes_to_the_shared_local_workspace(self):
        self.client.post("/lab/prompts/add/", {"title": "Local prompt",
                                               "body": STRONG_PROMPT})
        self.assertIsNone(Prompt.objects.get(title="Local prompt").owner)

    def test_library_lists_only_own_prompts(self):
        Prompt.objects.create(title="Alice secret", body=STRONG_PROMPT, owner=self.alice)
        Prompt.objects.create(title="Bob secret", body=STRONG_PROMPT, owner=self.bob)
        Prompt.objects.create(title="Shared local", body=STRONG_PROMPT)
        self.client.force_login(self.alice)
        page = self.client.get("/lab/library/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Alice secret")
        self.assertNotContains(page, "Bob secret")
        self.assertNotContains(page, "Shared local")

    def test_foreign_prompt_detail_is_404_and_writes_do_not_leak(self):
        foreign = Prompt.objects.create(title="Not yours", body=STRONG_PROMPT, owner=self.bob)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(f"/lab/prompts/{foreign.pk}/").status_code, 404)
        # "Use" (POST) must not bump another account's counters.
        self.client.post(f"/lab/prompts/{foreign.pk}/use/")
        foreign.refresh_from_db()
        self.assertEqual(foreign.use_count, 0)
        # Delete on someone else's prompt leaves it alone.
        self.client.post(f"/lab/prompts/{foreign.pk}/delete/")
        self.assertTrue(Prompt.objects.filter(pk=foreign.pk).exists())

    def test_workflow_runs_are_scoped_per_user(self):
        WorkflowRun.objects.create(name="Alice workflow", preset="polish",
                                   input_text="x", owner=self.alice)
        WorkflowRun.objects.create(name="Bob workflow", preset="polish",
                                   input_text="x", owner=self.bob)
        self.client.force_login(self.alice)
        page = self.client.get("/lab/workflows/")
        self.assertContains(page, "Alice workflow")
        self.assertNotContains(page, "Bob workflow")

    def test_dashboard_stats_do_not_count_other_users(self):
        Prompt.objects.create(title="Bob only", body=STRONG_PROMPT, owner=self.bob)
        self.client.force_login(self.alice)
        page = self.client.get("/lab/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Bob only")

    def test_stats_helper_respects_the_given_user(self):
        Prompt.objects.create(title="mine", body=STRONG_PROMPT, owner=self.alice)
        Prompt.objects.create(title="theirs", body=STRONG_PROMPT, owner=self.bob)
        mine = lab_stats(self.alice)
        theirs = lab_stats(self.bob)
        shared = lab_stats(None)
        self.assertEqual(mine["total_prompts"], 1)
        self.assertEqual(theirs["total_prompts"], 1)
        self.assertEqual(shared["total_prompts"], 2)



