"""Deterministic prompt analyzer: 12 weighted metrics, 0-100 overall score.

The scoring is fully transparent and reproducible: every metric is derived from
detectable signals in the text (sections, constraint markers, example markers,
hedging language, contradictions, ...). The same input always yields the same
score, and every subscore carries a human-readable note explaining it.
"""
from __future__ import annotations

import re

# --- metric weights (must sum to 1.0) ---------------------------------------
WEIGHTS = {
    "clarity": 0.12, "specificity": 0.11, "context": 0.10, "goal": 0.12,
    "role": 0.07, "constraints": 0.12, "output_format": 0.11, "examples": 0.06,
    "ambiguity": 0.07, "completeness": 0.05, "consistency": 0.04,
    "compatibility": 0.03,
}

METRIC_LABELS = {
    "clarity": "Clarity", "specificity": "Specificity", "context": "Context",
    "goal": "Goal definition", "role": "Role definition", "constraints": "Constraints",
    "output_format": "Output format", "examples": "Examples", "ambiguity": "Ambiguity (lower is better)",
    "completeness": "Completeness", "consistency": "Consistency",
    "compatibility": "AI compatibility",
}

_VAGUE = ("good", "nice", "better", "stuff", "things", "etc", "some", "several",
          "various", "appropriate", "suitable", "a lot", "many", "few", "soon",
          "modern", "professional", "creative", "engaging")
_HEDGE = ("maybe", "probably", "perhaps", "might want", "possibly", "if possible",
          "try to", "kind of", "sort of", "i guess", "asap")
_GOAL_VERBS = ("write", "create", "generate", "analyze", "analyse", "summarize",
               "summarise", "explain", "list", "compare", "review", "translate",
               "design", "build", "plan", "draft", "rewrite", "edit", "classify",
               "extract", "convert", "debug", "recommend", "evaluate", "describe")
_CONSTRAINT_MARKERS = ("must", "should", "do not", "don't", "avoid", "never",
                       "only", "at least", "at most", "no more than", "limit",
                       "max", "minimum", "exclude", "ensure", "exactly",
                       "within", "keep it", "use ")
_FORMAT_MARKERS = ("json", "xml", "yaml", "csv", "markdown", "bullet", "bullets",
                   "table", "list", "numbered", "sections", "schema", "format",
                   "output", "respond with", "structured", "headings", "paragraph",
                   "steps", "checklist")
_EXAMPLE_MARKERS = ("example", "e.g.", "for instance", "such as", "sample",
                    "like this:", "input:", "output:", "```")
_CONTEXT_MARKERS = ("context", "background", "audience", "for a", "for my",
                    "given", "here is", "about", "i am", "i'm", "my ", "we are",
                    "our ", "project", "company", "currently", "the following")
_ROLE_MARKERS = ("you are", "act as", "as a", "as an", "role:", "persona",
                 "you're a", "imagine you", "expert")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _has_any(lowered: str, markers) -> bool:
    return any(marker in lowered for marker in markers)


def _count_any(lowered: str, markers) -> int:
    return sum(1 for marker in markers if marker in lowered)


# --- individual metrics -------------------------------------------------------
def _metric_clarity(text: str, lowered: str) -> tuple[int, str]:
    sents = _sentences(text)
    words = _words(text)
    if not words:
        return 0, "Empty prompt."
    avg_len = len(words) / max(1, len(sents))
    vague = _count_any(lowered, _VAGUE)
    score = 70.0
    if avg_len <= 28:
        score += 12
    elif avg_len <= 40:
        score += 4
    else:
        score -= min(20, (avg_len - 40) / 3)
    score -= min(30, vague * 9)
    if len(words) < 6:
        score -= 30
    note = f"{len(sents)} sentence(s), avg {avg_len:.0f} words"
    note += f", {vague} vague term(s)" if vague else ", no vague terms"
    return _clamp(score), note


def _metric_specificity(text: str, lowered: str) -> tuple[int, str]:
    words = _words(text)
    if not words:
        return 0, "Empty prompt."
    numbers = len(re.findall(r"\b\d[\d,.%]*\b", text))
    proper = len(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)) - len(_sentences(text))
    proper = max(0, proper)
    concrete = sum(1 for w in words if len(w) > 6)
    score = 40.0
    score += min(20, numbers * 7)
    score += min(16, proper * 5)
    score += min(18, concrete * 2)
    if len(words) >= 30:
        score += 8
    if _has_any(lowered, ("step by step", "first", "then", "finally")):
        score += 4
    note = f"{numbers} numeric detail(s), {proper} named detail(s)"
    return _clamp(score), note


def _metric_context(text: str, lowered: str) -> tuple[int, str]:
    hits = _count_any(lowered, _CONTEXT_MARKERS)
    score = {0: 30, 1: 55, 2: 72, 3: 85}.get(hits, 92)
    if "audience" in lowered:
        score = min(100, score + 6)
    note = f"{hits} context signal(s) found" + (" (audience stated)" if "audience" in lowered else "")
    return _clamp(score), note


def _metric_goal(text: str, lowered: str) -> tuple[int, str]:
    verbs = [v for v in _GOAL_VERBS if v in lowered]
    explicit = _has_any(lowered, ("goal", "objective", "task:", "i want", "i need",
                                  "help me", "please"))
    score = 35.0 + min(40, len(verbs) * 18) + (15 if explicit else 0)
    if _has_any(lowered, ("so that", "in order to", "purpose", "the goal")):
        score = min(100, score + 10)
    note = f"task verb(s): {', '.join(verbs[:3]) or 'none detected'}" + \
           ("; purpose stated" if "so that" in lowered else "")
    return _clamp(score), note


def _metric_role(text: str, lowered: str) -> tuple[int, str]:
    if _has_any(lowered, ("you are", "act as", "role:", "persona", "imagine you")):
        return 95, "Explicit role defined"
    if _has_any(lowered, ("as a", "as an", "expert")):
        return 70, "Partial role hint found"
    return 15, "No role definition"


def _metric_constraints(text: str, lowered: str) -> tuple[int, str]:
    hits = _count_any(lowered, _CONSTRAINT_MARKERS)
    negatives = _count_any(lowered, ("do not", "don't", "avoid", "never", "exclude"))
    score = 30.0 + min(55, hits * 14) + (10 if negatives else 0)
    note = f"{hits} constraint marker(s)" + (f", {negatives} negative" if negatives else "")
    return _clamp(score), note


def _metric_output_format(text: str, lowered: str) -> tuple[int, str]:
    hits = _count_any(lowered, _FORMAT_MARKERS)
    if "json" in lowered and ("{" in text or "schema" in lowered or "keys" in lowered):
        return 97, "Explicit JSON/schema output contract"
    score = {0: 20, 1: 55, 2: 75, 3: 88}.get(hits, 95)
    note = f"{hits} output-format signal(s)"
    return _clamp(score), note


def _metric_examples(text: str, lowered: str) -> tuple[int, str]:
    hits = _count_any(lowered, _EXAMPLE_MARKERS)
    if hits >= 2:
        return 95, f"{hits} example markers"
    if hits == 1:
        return 75, "One example reference"
    return 30, "No examples (fine for simple tasks)"


def _metric_ambiguity(text: str, lowered: str) -> tuple[int, str]:
    """Higher score = LESS ambiguity (inverted metric)."""
    hedges = _count_any(lowered, _HEDGE)
    vague = _count_any(lowered, _VAGUE)
    score = 92.0 - min(45, hedges * 15) - min(35, vague * 8)
    if re.search(r"\b(it|this|that)\b(?=\s+(is|should|works))", lowered) and len(_sentences(text)) > 2:
        score -= 8
    note = f"{hedges} hedge(s), {vague} vague term(s)"
    return _clamp(score), note


_CONFLICT_PAIRS = [
    (("brief", "concise", "short", "shortly"),
     ("detail", "detailed", "comprehensive", "exhaustive", "in-depth", "elaborate", "thorough")),
    (("formal", "professional"), ("casual", "informal", "funny", "slang")),
    (("simple", "beginner"), ("advanced", "expert-level", "technical depth")),
]


def _metric_consistency(text: str, lowered: str) -> tuple[int, str]:
    conflicts = []
    for group_a, group_b in _CONFLICT_PAIRS:
        if _has_any(lowered, group_a) and _has_any(lowered, group_b):
            conflicts.append(f"'{group_a[0]}' vs '{group_b[0]}'")
    sents = _sentences(text)
    duplicates = len(sents) - len({s.lower() for s in sents})
    score = 100.0 - len(conflicts) * 30 - duplicates * 10
    note = "no conflicting instructions" if not conflicts and not duplicates \
        else "; ".join(conflicts) + (f"; {duplicates} duplicate(s)" if duplicates else "")
    return _clamp(score), note


def _metric_completeness(text: str, lowered: str) -> tuple[int, str]:
    parts = {
        "goal": _metric_goal(text, lowered)[0] >= 60,
        "role": _metric_role(text, lowered)[0] >= 60,
        "context": _metric_context(text, lowered)[0] >= 60,
        "constraints": _metric_constraints(text, lowered)[0] >= 60,
        "format": _metric_output_format(text, lowered)[0] >= 60,
    }
    score = 20 + 16 * sum(parts.values())
    missing_parts = [k for k, ok in parts.items() if not ok]
    note = "all core sections present" if not missing_parts \
        else f"missing: {', '.join(missing_parts)}"
    return _clamp(score), note


def _metric_compatibility(text: str, lowered: str) -> tuple[int, str]:
    words = _words(text)
    score = 60.0
    if _has_any(lowered, _FORMAT_MARKERS):
        score += 14
    if _has_any(lowered, _ROLE_MARKERS):
        score += 10
    if 20 <= len(words) <= 1200:
        score += 10
    elif len(words) > 2400:
        score -= 20
    if "```" in text or ("<" in text and ">" in text):
        score += 6
    note = f"{len(words)} words; structure and length are model-friendly" if score >= 80 \
        else f"{len(words)} words; consider tightening structure"
    return _clamp(score), note


# --- public API -----------------------------------------------------------------
def analyze_prompt(text: str, target_model: str = "any") -> dict:
    """Score a prompt across 12 metrics and return a fully explainable report."""
    text = (text or "").strip()
    lowered = text.lower()
    metrics_raw = {
        "clarity": _metric_clarity(text, lowered),
        "specificity": _metric_specificity(text, lowered),
        "context": _metric_context(text, lowered),
        "goal": _metric_goal(text, lowered),
        "role": _metric_role(text, lowered),
        "constraints": _metric_constraints(text, lowered),
        "output_format": _metric_output_format(text, lowered),
        "examples": _metric_examples(text, lowered),
        "ambiguity": _metric_ambiguity(text, lowered),
        "completeness": _metric_completeness(text, lowered),
        "consistency": _metric_consistency(text, lowered),
        "compatibility": _metric_compatibility(text, lowered),
    }
    metrics = {name: {"score": score, "note": note}
               for name, (score, note) in metrics_raw.items()}
    overall = _clamp(sum(metrics[name]["score"] * weight
                         for name, weight in WEIGHTS.items()))

    strengths = [METRIC_LABELS[name] for name, m in metrics.items()
                 if m["score"] >= 80 and name != "ambiguity"]
    if metrics["ambiguity"]["score"] >= 80:
        strengths.append(METRIC_LABELS["ambiguity"])
    weaknesses = [METRIC_LABELS[name] for name, m in metrics.items()
                  if m["score"] < 55]

    missing, suggestions = [], []
    if metrics["role"]["score"] < 55:
        missing.append("Role definition (who the AI should act as)")
        suggestions.append("Add a role, e.g. \"You are a senior copywriter with 10 years of SaaS experience.\"")
    if metrics["goal"]["score"] < 60:
        missing.append("Clear goal (what exactly to produce)")
        suggestions.append("State the objective with one action verb: \"Write...\", \"Analyze...\", \"Generate...\".")
    if metrics["context"]["score"] < 60:
        missing.append("Context (background the AI cannot guess)")
        suggestions.append("Describe the audience and situation: \"The readers are beginner developers...\"")
    if metrics["constraints"]["score"] < 60:
        missing.append("Constraints (length, scope, style rules)")
        suggestions.append("Add 2-3 hard rules, e.g. \"Maximum 300 words. Avoid jargon. Use UK English.\"")
    if metrics["output_format"]["score"] < 60:
        missing.append("Output format (how the answer should be structured)")
        suggestions.append("Specify the shape: \"Return JSON with keys title, summary, tags.\" or \"Use 3 bullet points.\"")
    if metrics["examples"]["score"] < 50 and metrics["specificity"]["score"] < 70:
        missing.append("Example of the desired output")
        suggestions.append("Provide one sample input/output pair so the model can anchor on your style.")
    if metrics["ambiguity"]["score"] < 60:
        suggestions.append("Replace hedging words (\"maybe\", \"some\", \"a lot\") with concrete values.")
    if metrics["consistency"]["score"] < 80:
        suggestions.append("Resolve conflicting instructions - decide between brevity and depth, not both.")

    if not weaknesses:
        weaknesses = ["None detected - keep iterating with real outputs."]
    if not suggestions:
        suggestions = ["Run it against a real model and refine based on the output."]

    band = ("Excellent" if overall >= 85 else "Good" if overall >= 70
            else "Fair" if overall >= 50 else "Needs work")
    return {
        "score": overall,
        "band": band,
        "metrics": metrics,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing": missing,
        "suggestions": suggestions,
        "word_count": len(_words(text)),
    }


def compare_versions(before_text: str, after_text: str) -> dict:
    """Human-readable diff summary between two prompts + before/after scores."""
    before = analyze_prompt(before_text)
    after = analyze_prompt(after_text)
    deltas = {name: after["metrics"][name]["score"] - before["metrics"][name]["score"]
              for name in WEIGHTS}
    improved = {METRIC_LABELS[k]: deltas[k] for k in deltas
                if deltas[k] >= 10 and k != "ambiguity"}
    if deltas["ambiguity"] >= 10:
        improved[METRIC_LABELS["ambiguity"]] = deltas["ambiguity"]
    declined = {METRIC_LABELS[k]: deltas[k] for k in deltas if deltas[k] <= -10}
    b_sents, a_sents = _sentences(before_text), _sentences(after_text)
    added = [s for s in a_sents if s.lower() not in {x.lower() for x in b_sents}]
    removed = [s for s in b_sents if s.lower() not in {x.lower() for x in a_sents}]
    return {
        "score_before": before["score"], "score_after": after["score"],
        "score_delta": after["score"] - before["score"],
        "metrics_before": {k: v["score"] for k, v in before["metrics"].items()},
        "metrics_after": {k: v["score"] for k, v in after["metrics"].items()},
        "improved": improved, "declined": declined,
        "sentences_added": len(added), "sentences_removed": len(removed),
        "summary": (f"Score {before['score']} → {after['score']} "
                    f"({'+' if after['score'] >= before['score'] else ''}"
                    f"{after['score'] - before['score']}); "
                    f"{len(added)} section(s) added, {len(removed)} removed."),
    }





