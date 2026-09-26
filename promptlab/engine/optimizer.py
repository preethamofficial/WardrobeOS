"""Prompt optimizer: weak/basic prompt -> professionally structured prompt.

Levels: BASIC < PROFESSIONAL < EXPERT < MAXIMUM. The optimizer inspects the
analyzer report, decides what is missing, avoids inventing assumptions (it
asks the model to state them instead) and picks the technique set accordingly.
"""
from __future__ import annotations

from .analyzer import analyze_prompt
from .pipeline import build_prompt
from .techniques import detect_intent, TECHNIQUES

LEVELS = {
    "basic": {"label": "Basic", "tier": "improved",
              "description": "Fixes clarity, adds the missing core sections."},
    "professional": {"label": "Professional", "tier": "expert",
                     "description": "Full role/context/constraints/format structure with XML delimiters."},
    "expert": {"label": "Expert", "tier": "expert",
               "description": "Professional structure + negative constraints, quality bar and edge cases."},
    "maximum": {"label": "Maximum", "tier": "maximum",
                "description": "Expert structure + task decomposition, self-check and instruction priority."},
}


def optimize(text: str, level: str = "professional", **opts) -> dict:
    """Optimize a weak prompt. Returns before/after with full explanations."""
    original = (text or "").strip()
    if not original:
        raise ValueError("Nothing to optimize - the prompt is empty.")
    level = level if level in LEVELS else "professional"
    before = analyze_prompt(original)
    intent, _signals = detect_intent(original)

    merged_opts = dict(opts)
    # Feed the analyzer's suggestions in as constraints so real gaps get fixed.
    gap_constraints = [s for s in before["suggestions"][:3]]
    if gap_constraints:
        merged_opts["constraints"] = ((merged_opts.get("constraints") or "") + "\n"
                                      + "\n".join(gap_constraints)).strip()

    generated = build_prompt(original, tier=LEVELS[level]["tier"], **merged_opts)
    after = analyze_prompt(generated["prompt"])

    missing_info = list(before["missing"])
    assumptions = [
        "The optimized prompt never invents facts: it instructs the model to state assumptions explicitly.",
        "If the audience, tone or format was not specified, the prompt picks a sensible default and labels it.",
    ]

    techniques = [TECHNIQUES[t]["name"] for t in generated["techniques"]]
    why = generated["why_better"] + [
        f"Analyzer score moved from {before['score']} to {after['score']} "
        f"({'+' if after['score'] >= before['score'] else ''}{after['score'] - before['score']}).",
    ]
    return {
        "original": original,
        "optimized": generated["prompt"],
        "level": level,
        "level_label": LEVELS[level]["label"],
        "level_description": LEVELS[level]["description"],
        "score_before": before["score"],
        "score_after": after["score"],
        "missing_info": missing_info,
        "assumptions": assumptions,
        "intent": intent,
        "intent_label": generated["intent_label"],
        "techniques": techniques,
        "improvements": generated["improvements"],
        "why": why,
        "analysis_before": before,
        "analysis_after": after,
    }
