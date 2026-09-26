"""Service layer: prompt versioning, multi-provider comparison, logging, stats."""
from __future__ import annotations

from ai.providers import complete_text, provider_status
from promptlab.engine.analyzer import analyze_prompt
from promptlab.models import AIRequestLog, Prompt, PromptVersion, WorkflowRun


# --- prompts & versioning -------------------------------------------------------
def create_prompt(*, title, body, **fields) -> Prompt:
    """Create a prompt and its first version snapshot."""
    prompt = Prompt.objects.create(title=title, body=body, **fields)
    PromptVersion.objects.create(prompt=prompt, version_number=1, body=body,
                                 score=analyze_prompt(body)["score"],
                                 change_note="Initial version")
    return prompt


def add_version(prompt: Prompt, body: str, change_note: str = "") -> PromptVersion:
    """Append a new version. History is never overwritten."""
    latest = prompt.versions.order_by("-version_number").first()
    number = (latest.version_number + 1) if latest else 1
    version = PromptVersion.objects.create(
        prompt=prompt, version_number=number, body=body,
        score=analyze_prompt(body)["score"], change_note=change_note[:240])
    prompt.body = body
    prompt.save(update_fields=["body", "updated_at"])
    return version


def duplicate_prompt(prompt: Prompt) -> Prompt:
    copy = Prompt.objects.create(
        title=f"{prompt.title} (copy)", body=prompt.body, goal=prompt.goal,
        category=prompt.category, tags=prompt.tags, target_model=prompt.target_model,
        audience=prompt.audience, tone=prompt.tone, language=prompt.language,
        source=prompt.source)
    PromptVersion.objects.create(prompt=copy, version_number=1, body=prompt.body,
                                 score=analyze_prompt(prompt.body)["score"],
                                 change_note=f"Duplicated from '{prompt.title}'")
    return copy


# --- AI comparison --------------------------------------------------------------
def compare_providers(text: str, provider_ids: list[str] | None = None,
                      *, kind: str = "compare", timeout: int = 45) -> dict:
    """Send the same prompt to each configured provider (sequentially).

    Only configured providers are contacted, one call each - no fan-out spam.
    Every call is logged with latency/usage/error for the dashboard.
    """
    results = []
    statuses = {s["id"]: s for s in provider_status()}
    chosen = provider_ids or list(statuses.keys())
    for pid in chosen:
        status = statuses.get(pid)
        if not status or not status["configured"] or "text" not in status["capabilities"]:
            if provider_ids and pid in provider_ids:
                results.append({"provider": pid, "label": pid, "model": "-",
                                "ok": False, "error_code": "missing_config",
                                "error": "Not configured - add its API key to .env.",
                                "latency_ms": 0, "usage": {}})
            continue

        result = complete_text(text, providers=[pid], timeout=timeout)
        usage = result.usage or {}
        if result.ok:
            AIRequestLog.objects.create(
                provider=result.provider, model=result.model, kind=kind,
                status="ok", latency_ms=result.latency_ms,
                prompt_tokens=usage.get("prompt_tokens") or usage.get("promptTokenCount"),
                completion_tokens=usage.get("completion_tokens") or usage.get("candidatesTokenCount"),
                total_tokens=usage.get("total_tokens") or usage.get("totalTokenCount"))
            results.append({"provider": result.provider, "label": status["label"],
                            "model": result.model, "ok": True, "text": result.text,
                            "error_code": None, "error": "", "latency_ms": result.latency_ms,
                            "usage": usage, "attempts": result.attempts})
        else:
            AIRequestLog.objects.create(
                provider=result.provider, model=result.model or "-", kind=kind,
                status="error", error_code=result.error_code or "error",
                error_message=(result.error_message or "")[:240], latency_ms=result.latency_ms)
            results.append({"provider": result.provider, "label": status["label"],
                            "model": result.model or "-", "ok": False, "text": "",
                            "error_code": result.error_code, "error": result.error_message,
                            "latency_ms": result.latency_ms, "usage": {},
                            "attempts": result.attempts})
    return {"results": results, "any_success": any(r["ok"] for r in results)}


# --- workflow persistence ---------------------------------------------------------
def save_workflow_run(name: str, preset: str, input_text: str, outcome: dict) -> WorkflowRun:
    return WorkflowRun.objects.create(
        name=name or f"{preset} workflow", preset=preset, input_text=input_text,
        final_text=outcome.get("final", ""), final_score=outcome.get("final_score"),
        used_ai=outcome.get("used_ai", False), steps=outcome.get("steps", []))


# --- dashboard stats (all real data) ------------------------------------------------
def lab_stats() -> dict:
    prompts = Prompt.objects.all()
    versions = PromptVersion.objects.all()
    logs = AIRequestLog.objects.all()
    scored = [v.score for v in versions.only("score") if v.score is not None]
    avg_score = round(sum(scored) / len(scored)) if scored else None
    categories: dict[str, int] = {}
    for prompt in prompts:
        label = prompt.get_category_display()
        categories[label] = categories.get(label, 0) + 1
    provider_usage: dict[str, dict] = {}
    for log in logs[:500]:
        entry = provider_usage.setdefault(log.provider, {"total": 0, "ok": 0})
        entry["total"] += 1
        entry["ok"] += 1 if log.status == "ok" else 0
    for entry in provider_usage.values():
        entry["success_rate"] = round(100 * entry["ok"] / entry["total"]) if entry["total"] else 0
    return {
        "total_prompts": prompts.count(),
        "favorites": prompts.filter(favorite=True).count(),
        "versions": versions.count(),
        "improvements": max(0, versions.count() - prompts.count()),
        "avg_score": avg_score,
        "ai_requests": logs.count(),
        "ai_errors": logs.filter(status="error").count(),
        "workflows": WorkflowRun.objects.count(),
        "categories": sorted(categories.items(), key=lambda kv: kv[1], reverse=True)[:6],
        "provider_usage": provider_usage,
        "recent_prompts": prompts[:5],
        "favorite_prompts": prompts.filter(favorite=True)[:5],
        "recent_logs": logs[:6],
    }


