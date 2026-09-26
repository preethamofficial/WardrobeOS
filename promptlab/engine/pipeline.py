"""Prompt generation pipeline.

USER'S SIMPLE IDEA
  -> intent detection -> context extraction -> task analysis
  -> role definition -> objective definition -> context enrichment
  -> constraint generation -> output format design -> quality requirements
  -> edge case consideration -> FINAL OPTIMIZED PROMPT

The whole pipeline is deterministic (rule-based), runs with zero API keys and
never exposes private model reasoning: users only see *what was built and why*.
"""
from __future__ import annotations

import re

from .analyzer import analyze_prompt
from .techniques import (INTENTS, detect_intent, select_techniques, TECHNIQUES)

TIER_LABELS = {
    "basic": "Basic",
    "improved": "Improved",
    "expert": "Expert",
    "maximum": "Maximum",
}

TONE_HINTS = {
    "professional": "a professional, polished tone",
    "friendly": "a warm, friendly tone",
    "casual": "a relaxed, conversational tone",
    "academic": "a precise, academic tone",
    "persuasive": "a persuasive, confident tone",
    "neutral": "a neutral, objective tone",
    "humorous": "a light, humorous tone (without undermining accuracy)",
}

FORMAT_HINTS = {
    "markdown": "Markdown with headings",
    "json": "strict JSON (no commentary outside the JSON)",
    "xml": "XML tags matching the requested schema",
    "table": "a Markdown table",
    "bullets": "concise bullet points",
    "numbered": "a numbered list",
    "plaintext": "plain text with no markup",
    "email": "an email with subject line, greeting, body and sign-off",
}


def _clean_idea(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text


def _title_case_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _extract_context_fields(idea: str, opts: dict) -> dict:
    """Merge user-provided options with signals detected inside the idea text."""
    lowered = idea.lower()
    audience = (opts.get("audience") or "").strip()
    tone = (opts.get("tone") or "").strip().lower()
    language = (opts.get("language") or "").strip()
    output_format = (opts.get("output_format") or "").strip().lower()
    if not audience:
        for marker in ("for beginners", "for students", "for developers", "for kids",
                       "for executives", "for my team", "for clients"):
            if marker in lowered:
                audience = marker.replace("for ", "").capitalize()
                break
    if not tone:
        for hint in TONE_HINTS:
            if hint in lowered:
                tone = hint
                break
    if not output_format:
        for key in FORMAT_HINTS:
            if key in lowered:
                output_format = key
                break
    if not language:
        match = re.search(r"\bin ([A-Z][a-z]+)\b", idea)
        language = match.group(1) if match else ""
    return {"audience": audience, "tone": tone, "language": language,
            "output_format": output_format}


def _constraint_list(idea: str, intent: str, ctx: dict, opts: dict) -> list[str]:
    """Merge intent defaults, explicit user constraints and negative constraints."""
    spec = INTENTS[intent]
    constraints = list(spec["constraints"])
    user_constraints = [c.strip().lstrip("-•") for c in re.split(r"[\n;]+", opts.get("constraints") or "") if c.strip()]
    constraints = user_constraints + constraints
    if ctx["language"] and ctx["language"].lower() != "english":
        constraints.append(f"Respond entirely in {ctx['language']}.")
    if ctx["tone"]:
        constraints.append(f"Use {TONE_HINTS.get(ctx['tone'], ctx['tone'] + ' tone')}.")
    if ctx["audience"]:
        constraints.append(f"Assume the audience is {ctx['audience'].lower()} - adjust vocabulary and depth accordingly.")
    negative = ["Do not invent facts; if unsure, say so explicitly.",
                "Do not pad the answer with filler or repetition."]
    return constraints, negative


def _format_text(ctx: dict, intent: str, opts: dict) -> str:
    custom = (opts.get("output_format_custom") or "").strip()
    if custom:
        return custom
    if ctx["output_format"] in FORMAT_HINTS:
        base = FORMAT_HINTS[ctx["output_format"]]
    else:
        base = INTENTS[intent]["format"]
    if ctx["output_format"] == "json":
        base += (" Include exactly these top-level keys as relevant to the task; "
                 'use "" for unknown values.')
    return base


def _build_basic(idea: str) -> str:
    return _title_case_first(idea.rstrip(".")) + "."


def _build_structured(idea: str, intent: str, ctx: dict, constraints: list[str],
                      negative: list[str], opts: dict, *, expert: bool) -> dict:
    """Shared builder for improved/expert tiers."""
    spec = INTENTS[intent]
    role = f"You are {spec['role']}."
    objective = f"Task: {_title_case_first(idea.rstrip('.'))}."
    context_bits = []
    if ctx["audience"]:
        context_bits.append(f"Audience: {ctx['audience']}.")
    if ctx["tone"]:
        context_bits.append(f"Desired tone: {ctx['tone']}.")
    if opts.get("reference"):
        context_bits.append("Reference material is provided below - treat it as the source of truth:\n"
                            "---\n" + str(opts["reference"]).strip() + "\n---")
    if opts.get("examples"):
        context_bits.append("Example of the desired style/output:\n" + str(opts["examples"]).strip())
    if not context_bits:
        context_bits.append("No additional background was provided; state your assumptions instead of guessing.")

    format_text = _format_text(ctx, intent, opts)

    if not expert:
        lines = [role, "", objective]
        if context_bits:
            lines += ["", "Context:"] + [bit.splitlines()[0] if "\n" not in bit else bit
                                         for bit in context_bits]
        lines += ["", "Requirements:"] + [f"- {c}" for c in constraints]
        lines += ["", f"Output format: {format_text}"]
        return {"text": "\n".join(lines),
                "sections": ["role", "objective", "context", "constraints", "output_format"]}

    text_parts = [
        "<role>", role, "</role>", "",
        "<objective>", objective, "</objective>", "",
        "<context>",
    ]
    text_parts += [f"- {bit}" if "\n" not in bit else bit for bit in context_bits]
    text_parts += [
        "</context>", "",
        "<instructions>",
        "1. Read the objective and context carefully before answering.",
        "2. Plan the response structure silently, then produce it.",
        "3. Follow every constraint below without exception.",
        "</instructions>", "",
        "<constraints>",
    ]
    text_parts += [f"- {c}" for c in constraints]
    text_parts += ["- " + n for n in negative]
    text_parts += [
        "</constraints>", "",
        "<output_format>", format_text, "</output_format>", "",
        "<quality_bar>",
        "- Accuracy first: every claim must be defensible from the task or reference material.",
        "- Be concise; every sentence must earn its place.",
        "- Prefer concrete examples over abstract generalities.",
        "</quality_bar>", "",
        "<edge_cases>",
        "- If key information is missing, list your assumptions at the top of the answer.",
        "- If the request is ambiguous, answer the most likely interpretation and note the alternative.",
        "</edge_cases>",
    ]
    return {"text": "\n".join(text_parts),
            "sections": ["role", "objective", "context", "instructions", "constraints",
                         "negative_constraints", "output_format", "quality_bar", "edge_cases"]}


_DECOMPOSITION = {
    "coding": ["Restate the requirement in one sentence.",
               "Identify inputs, outputs and error cases.",
               "Outline the approach in 2-3 bullet points.",
               "Write the complete implementation.",
               "Re-check edge cases and correctness before finalising."],
    "analysis": ["Restate the question and what a good answer must contain.",
                 "List the relevant factors and gather evidence for each.",
                 "Weigh trade-offs explicitly.",
                 "Commit to a recommendation with confidence level."],
    "writing": ["Clarify the message and the reader's takeaway.",
                "Draft an outline (hook, body, close).",
                "Write the full piece following the constraints.",
                "Trim filler and verify tone consistency."],
}
_DEFAULT_DECOMPOSITION = ["Restate the task in one sentence to confirm understanding.",
                          "List what information you need and what is missing.",
                          "Produce the deliverable following the constraints.",
                          "Verify the result against the quality bar before finalising."]


def _build_maximum(idea: str, intent: str, ctx: dict, constraints: list[str],
                   negative: list[str], opts: dict) -> dict:
    base = _build_structured(idea, intent, ctx, constraints, negative, opts, expert=True)
    steps = _DECOMPOSITION.get(intent, _DEFAULT_DECOMPOSITION)
    decomposition = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    self_check = "\n".join([
        "1. Does the answer satisfy every constraint? If not, fix it before responding.",
        "2. Is anything invented or unsupported? Remove or flag it.",
        "3. Does the structure match the requested output format exactly?",
    ])
    text = base["text"] + (
        "\n\n<task_decomposition>\nWork through these steps in order:\n"
        + decomposition + "\n</task_decomposition>"
        + "\n\n<self_check>\nBefore sending your final answer, verify:\n"
        + self_check + "\n</self_check>"
        + "\n\n<priority>If sections conflict, constraints and the output format win over style preferences.</priority>"
    )
    return {"text": text,
            "sections": base["sections"] + ["task_decomposition", "self_check",
                                            "instruction_hierarchy"]}


def build_prompt(idea: str, *, tier: str = "improved", **opts) -> dict:
    """Generate an optimized prompt from a simple idea."""
    idea = _clean_idea(idea)
    if not idea:
        raise ValueError("Idea text is empty.")
    tier = tier if tier in TIER_LABELS else "improved"
    intent, signals = detect_intent(idea)
    ctx = _extract_context_fields(idea, opts)
    constraints, negative = _constraint_list(idea, intent, ctx, opts)
    has_examples = bool((opts.get("examples") or "").strip())

    if tier == "basic":
        prompt = _build_basic(idea)
        sections = ["objective"]
    elif tier == "improved":
        built = _build_structured(idea, intent, ctx, constraints, negative, opts, expert=False)
        prompt, sections = built["text"], built["sections"]
    elif tier == "expert":
        built = _build_structured(idea, intent, ctx, constraints, negative, opts, expert=True)
        prompt, sections = built["text"], built["sections"]
    else:
        built = _build_maximum(idea, intent, ctx, constraints, negative, opts)
        prompt, sections = built["text"], built["sections"]

    techniques = select_techniques(intent, tier, has_examples=has_examples,
                                   needs_structure=tier != "basic")

    why = [
        f"Detected intent: {INTENTS[intent]['label']}"
        + (f" (signals: {', '.join(signals[:3])})" if signals else ""),
        "Applied techniques: "
        + ", ".join(TECHNIQUES[t]["name"] for t in techniques[:6])
        + ("…" if len(techniques) > 6 else ""),
    ]
    improvements = []
    if "role" in sections:
        improvements.append({"title": "Role defined",
                             "detail": f"The model is told exactly who to be: {INTENTS[intent]['role']}."})
    if "constraints" in sections:
        improvements.append({"title": "Hard constraints added",
                             "detail": f"{len(constraints)} explicit rule(s) keep the output usable on the first try."})
    if "negative_constraints" in sections:
        improvements.append({"title": "Negative constraints added",
                             "detail": "Common failure modes (invented facts, filler) are blocked explicitly."})
    if "output_format" in sections:
        improvements.append({"title": "Output format specified",
                             "detail": "The response shape is defined, so no re-formatting is needed."})
    if "quality_bar" in sections:
        improvements.append({"title": "Quality bar included",
                             "detail": "The prompt defines what 'good' means for this task."})
    if "edge_cases" in sections:
        improvements.append({"title": "Edge cases covered",
                             "detail": "Missing-information and ambiguity behaviour is pre-agreed."})
    if "task_decomposition" in sections:
        improvements.append({"title": "Task decomposition",
                             "detail": "Complex work is broken into ordered, checkable steps."})
    if "self_check" in sections:
        improvements.append({"title": "Self-evaluation step",
                             "detail": "The model verifies its own answer against the constraints first."})
    if ctx["language"]:
        improvements.append({"title": "Language locked",
                             "detail": f"Responses are requested in {ctx['language']}."})

    why.append(f"Analyzer score for this generated prompt: {analyze_prompt(prompt)['score']}/100.")

    return {
        "prompt": prompt, "tier": tier, "tier_label": TIER_LABELS[tier],
        "intent": intent, "intent_label": INTENTS[intent]["label"],
        "techniques": techniques, "sections": sections,
        "why_better": why, "improvements": improvements, "context": ctx,
    }


def generate_all_tiers(idea: str, **opts) -> dict:
    """The studio default: basic + improved + expert + maximum side by side."""
    out = {tier: build_prompt(idea, tier=tier, **opts)
           for tier in ("basic", "improved", "expert", "maximum")}
    for tier_data in out.values():
        tier_data["analysis"] = analyze_prompt(tier_data["prompt"])
    return out



