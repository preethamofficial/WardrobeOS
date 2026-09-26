"""PromptLab views: studio, analyzer, optimizer, library, compare, workflows."""
from __future__ import annotations

import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai.providers import provider_status
from promptlab.engine.analyzer import analyze_prompt, compare_versions
from promptlab.engine.mutations import mutate
from promptlab.engine.optimizer import LEVELS, optimize
from promptlab.engine.pipeline import generate_all_tiers
from promptlab.engine.techniques import TECHNIQUES
from promptlab.engine.workflows import PRESETS, run_workflow
from promptlab.models import Prompt, PromptAnalysis, PromptTemplate
from promptlab.ratelimit import RateLimitExceeded, check_rate_limit, rate_limited_json_response
from promptlab.services import (add_version, compare_providers, create_prompt,
                                duplicate_prompt, lab_stats, save_workflow_run)

MUTATION_ACTIONS = [
    ("regenerate", "↻ Regenerate"), ("improve", "✦ Improve"), ("shorten", "⤓ Shorten"),
    ("expand", "⤒ Expand"), ("professionalize", "★ Make professional"),
    ("beginner", "☺ Make beginner-friendly"), ("tone:professional", "Tone: professional"),
    ("tone:casual", "Tone: casual"), ("tone:academic", "Tone: academic"),
    ("format:json", "Format: JSON"), ("format:markdown", "Format: Markdown"),
    ("format:table", "Format: Table"), ("add_examples", "+ Examples"),
    ("add_constraints", "+ Constraints"),
]


def _opts_from_post(request) -> dict:
    return {
        "audience": request.POST.get("audience", ""),
        "tone": request.POST.get("tone", ""),
        "language": request.POST.get("language", ""),
        "output_format": request.POST.get("output_format", ""),
        "output_format_custom": request.POST.get("output_format_custom", ""),
        "constraints": request.POST.get("constraints", ""),
        "examples": request.POST.get("examples", ""),
        "reference": request.POST.get("reference", ""),
        "target_model": request.POST.get("target_model", "any"),
    }


def lab_dashboard(request):
    stats = lab_stats()
    return render(request, "promptlab/dashboard.html",
                  {"stats": stats, "providers": provider_status()})


def studio(request):
    """Prompt generator: idea in, basic/improved/expert/maximum out."""
    idea = request.POST.get("idea", "").strip() if request.method == "POST" else ""
    body = request.POST.get("body", "").strip()
    tiers = None
    active_body = body
    error = None
    if request.method == "POST":
        mutation = request.POST.get("mutation", "")
        if mutation:
            if not active_body:
                messages.warning(request, "Paste a prompt into the working box first, then apply an action.")
            else:
                try:
                    result = mutate(active_body, mutation, tier="improved")
                    active_body = result["text"]
                    messages.info(request, result["change_note"])
                except (ValueError, KeyError) as exc:
                    error = str(exc)
        if idea:
            try:
                tiers = generate_all_tiers(idea, **_opts_from_post(request))
            except ValueError as exc:
                error = str(exc)
    return render(request, "promptlab/studio.html",
                  {"idea": idea, "active_body": active_body, "tiers": tiers,
                   "error": error, "mutations": MUTATION_ACTIONS,
                   "categories": Prompt.CATEGORIES})


def analyzer(request):
    """Score any prompt across 12 metrics."""
    text = ""
    report = None
    comparison = None
    if request.method == "POST":
        text = request.POST.get("text", "")
        compare_with = request.POST.get("compare_with", "").strip()
        if text.strip():
            report = analyze_prompt(text)
            PromptAnalysis.objects.create(body=text[:20000],
                                          score=report["score"], report=report)
            if compare_with:
                comparison = compare_versions(compare_with, text)
        else:
            messages.warning(request, "Enter a prompt to analyze.")
    return render(request, "promptlab/analyzer.html",
                  {"text": text, "report": report, "comparison": comparison,
                   "compare_with": request.POST.get("compare_with", "") if request.method == "POST" else ""})


def optimizer(request):
    """Weak prompt -> structured professional prompt, four levels."""
    original = ""
    outcome = None
    level = request.POST.get("level", "professional")
    if request.method == "POST":
        original = request.POST.get("text", "").strip()
        if original:
            try:
                outcome = optimize(original, level, **_opts_from_post(request))
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.warning(request, "Enter a prompt to optimize.")
    return render(request, "promptlab/optimizer.html",
                  {"original": original, "outcome": outcome, "levels": LEVELS,
                   "level": level if level in LEVELS else "professional"})


# --- library -------------------------------------------------------------------
def library(request):
    prompts = Prompt.objects.all()
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    sort = request.GET.get("sort", "recent")
    fav_only = request.GET.get("favorites") == "1"
    if q:
        from django.db.models import Q
        prompts = prompts.filter(Q(title__icontains=q) | Q(body__icontains=q) | Q(tags__icontains=q))
    if category:
        prompts = prompts.filter(category=category)
    if fav_only:
        prompts = prompts.filter(favorite=True)
    ordering = {"recent": "-updated_at", "name": "title", "used": "-use_count",
                "score": "-versions__score"}.get(sort, "-updated_at")
    if sort == "score":
        prompts = prompts.distinct().order_by("-versions__score")
    else:
        prompts = prompts.order_by(ordering)
    templates = PromptTemplate.objects.all()
    if q:
        templates = templates.filter(title__icontains=q) | templates.filter(tags__icontains=q)
    if category:
        templates = templates.filter(category=category)
    recent = Prompt.objects.filter(last_used_at__isnull=False).order_by("-last_used_at")[:4]
    return render(request, "promptlab/library.html", {
        "prompts": prompts, "templates": templates, "q": q,
        "category": category, "sort": sort, "fav_only": fav_only,
        "categories": Prompt.CATEGORIES, "recent": recent})


def template_use(request, pk):
    """Copy a library template into a new editable prompt."""
    template = get_object_or_404(PromptTemplate, pk=pk)
    template.use_count += 1
    template.save(update_fields=["use_count"])
    prompt = create_prompt(title=template.title, body=template.body,
                           category=template.category, tags=template.tags,
                           goal=template.description, source="library")
    prompt.mark_used()
    messages.success(request, f"\"{template.title}\" copied to your prompts.")
    return redirect("prompt_detail", pk=prompt.pk)


@require_POST
def prompt_save(request):
    """Persist a generated/edited prompt body from studio/optimizer/analyzer."""
    body = request.POST.get("body", "").strip()
    title = request.POST.get("title", "").strip() or "Untitled prompt"
    category = request.POST.get("category", "other")
    source = request.POST.get("source", "manual")
    if not body:
        messages.warning(request, "Nothing to save - the prompt is empty.")
        return _safe_redirect(request, "library")
    prompt = create_prompt(title=title[:160], body=body, category=category, source=source)
    messages.success(request, f"Saved \"{prompt.title}\" to your library.")
    return redirect("prompt_detail", pk=prompt.pk)


def prompt_detail(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    versions = prompt.versions.all()
    comparison = None
    a_id = request.GET.get("a")
    b_id = request.GET.get("b")
    if a_id and b_id:
        va = versions.filter(version_number=a_id).first()
        vb = versions.filter(version_number=b_id).first()
        if va and vb:
            comparison = compare_versions(va.body, vb.body)
    return render(request, "promptlab/detail.html",
                  {"prompt": prompt, "versions": versions, "comparison": comparison,
                   "a": a_id, "b": b_id, "categories": Prompt.CATEGORIES})


@require_POST
def prompt_edit(request, pk):
    """Editing the body creates a new version - history is preserved."""
    prompt = get_object_or_404(Prompt, pk=pk)
    body = request.POST.get("body", "").strip()
    title = request.POST.get("title", "").strip()
    note = request.POST.get("change_note", "").strip() or "Edited"
    if not body:
        messages.warning(request, "Prompt body cannot be empty.")
        return redirect("prompt_detail", pk=pk)
    if body != prompt.body:
        add_version(prompt, body, note)
        messages.success(request, "New version saved. Previous versions are kept.")
    else:
        messages.info(request, "No changes detected.")
    if title and title != prompt.title:
        prompt.title = title[:160]
        prompt.save(update_fields=["title", "updated_at"])
    return redirect("prompt_detail", pk=pk)


@require_POST
def prompt_delete(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    title = prompt.title
    prompt.delete()
    messages.success(request, f"Deleted \"{title}\".")
    return redirect("library")


@require_POST
def prompt_favorite(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    prompt.favorite = not prompt.favorite
    prompt.save(update_fields=["favorite"])
    messages.success(request, f"{'★ Added to' if prompt.favorite else 'Removed from'} favorites.")
    return _safe_redirect(request, "prompt_detail", pk=pk)


def _safe_redirect(request, fallback, *, pk=None):
    """Redirect to request.POST['next'] only when it is a safe local path."""
    from django.utils.http import url_has_allowed_host_and_scheme
    next_url = request.POST.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                                    require_https=request.is_secure()):
        return redirect(next_url)
    if pk is not None:
        return redirect(fallback, pk=pk)
    return redirect(fallback)


@require_POST
def prompt_duplicate(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    copy = duplicate_prompt(prompt)
    messages.success(request, f"Duplicated as \"{copy.title}\".")
    return redirect("prompt_detail", pk=copy.pk)


@require_POST
def prompt_use(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    prompt.mark_used()
    messages.success(request, "Marked as used - it now appears in Recently used.")
    return redirect("prompt_detail", pk=pk)


# --- AI comparison ---------------------------------------------------------------
def compare(request):
    """Send one prompt to multiple configured providers, side by side."""
    text = ""
    selected = None
    outcome = None
    providers = provider_status()
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        selected = request.POST.getlist("providers")
        if text:
            try:
                check_rate_limit(request, "compare")
                outcome = compare_providers(text, selected or None, timeout=60)
                if not outcome["any_success"]:
                    messages.warning(request,
                                     "No provider returned a response - see the error cards "
                                     "for the exact reason (usually a missing API key).")
            except RateLimitExceeded as exc:
                messages.error(request, str(exc))
        else:
            messages.warning(request, "Enter a prompt to compare.")
    return render(request, "promptlab/compare.html",
                  {"text": text, "providers": providers, "selected": selected,
                   "outcome": outcome})


# --- workflows ---------------------------------------------------------------------
def workflows(request):
    outcome = None
    text = ""
    preset = "writing"
    use_ai = False
    error = None
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        preset = request.POST.get("preset", "writing")
        use_ai = request.POST.get("use_ai") == "on"
        if text:
            try:
                if use_ai:
                    check_rate_limit(request, "workflow")
                outcome = run_workflow(text, preset, use_ai=use_ai, timeout=60)
                outcome["steps_display"] = outcome["steps"]
                name = request.POST.get("name", "").strip()
                if request.POST.get("save") == "on":
                    run = save_workflow_run(name, preset, text, outcome)
                    messages.success(request, f"Workflow saved as \"{run.name}\".")
                messages.success(request, f"Workflow completed - final score {outcome['final_score']}/100.")
            except (ValueError, RateLimitExceeded) as exc:
                error = str(exc)
        else:
            messages.warning(request, "Enter the text or prompt to run through the workflow.")
    return render(request, "promptlab/workflows.html",
                  {"presets": PRESETS, "text": text, "preset": preset,
                   "use_ai": use_ai, "outcome": outcome, "error": error})


# --- JSON API (for fetch-based UI) ---------------------------------------------------
@require_POST
def api_analyze(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)
    text = str(data.get("text", ""))
    if not text.strip():
        return JsonResponse({"ok": False, "error": "Text is required."}, status=400)
    return JsonResponse({"ok": True, "report": analyze_prompt(text)})


def api_status(request):
    return JsonResponse({"ok": True, "providers": provider_status()})


