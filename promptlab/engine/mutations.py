"""Deterministic prompt mutations: regenerate, improve, shorten, expand, etc.

Every action returns {text, change_note, actions:[...]} so the UI can explain
exactly what happened. Mutations never call an external API - they are local,
instant and free.
"""
from __future__ import annotations

import re

from .analyzer import analyze_prompt
from .pipeline import build_prompt, FORMAT_HINTS, TONE_HINTS

_TONE_ALIASES = {t: t for t in TONE_HINTS}


def _strip_section(text: str, tag: str) -> str:
    return re.sub(rf"<{tag}>.*?</{tag}\s*>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def mutate(text: str, action: str, **opts) -> dict:
    """Apply one mutation action to a prompt."""
    original = (text or "").strip()
    if not original:
        raise ValueError("Nothing to mutate - the prompt is empty.")
    analysis = analyze_prompt(original)

    if action == "shorten":
        keep = max(3, int(opts.get("keep_sentences", 4)))
        core = _strip_section(original, "task_decomposition")
        core = _strip_section(core, "self_check")
        core = _strip_section(core, "quality_bar")
        sents = _sentences(core)
        trimmed = sents[:keep] if len(sents) > keep else sents
        out = " ".join(trimmed)
        # keep bullet blocks short too
        lines = []
        bullets = 0
        for line in out.splitlines():
            if line.strip().startswith(("-", "•")):
                bullets += 1
                if bullets > 6:
                    continue
            lines.append(line)
        out = "\n".join(lines)
        return {"text": out, "change_note": "Shortened: trimmed secondary sections and kept the core instruction.",
                "actions": ["Removed self-check and decomposition sections", "Kept the first core sentences"]}

    if action == "expand":
        additions = [
            "", "<quality_bar>",
            "- Accuracy first: every claim must be defensible.",
            "- Be concise; avoid filler.",
            "</quality_bar>", "",
            "<edge_cases>",
            "- If key information is missing, state your assumptions at the top.",
            "</edge_cases>",
        ]
        out = original.rstrip() + "\n" + "\n".join(additions)
        return {"text": out, "change_note": "Expanded: added a quality bar and edge-case guidance.",
                "actions": ["Added <quality_bar> section", "Added <edge_cases> section"]}

    if action == "professionalize" or action == "improve":
        regenerated = build_prompt(
            original,
            tier="expert" if action == "professionalize" else "improved",
            constraints="\n".join(analysis["suggestions"][:2]),
        )
        return {"text": regenerated["prompt"],
                "change_note": regenerated["why_better"][0],
                "actions": [imp["title"] for imp in regenerated["improvements"]]}

    if action == "beginner":
        addition = ("\n\n<audience_note>\nExplain everything for a complete beginner: "
                    "define jargon on first use, use short sentences and one worked example.\n</audience_note>")
        return {"text": original.rstrip() + addition,
                "change_note": "Rewritten for beginners: jargon must be defined, simpler sentences.",
                "actions": ["Added beginner audience note"]}

    if action.startswith("tone:"):
        tone = action.split(":", 1)[1].strip().lower()
        tone = _TONE_ALIASES.get(tone, tone)
        addition = f"\n\n<tone>Use {TONE_HINTS.get(tone, tone + ' tone')} throughout.</tone>"
        return {"text": original.rstrip() + addition,
                "change_note": f"Tone set to '{tone}'.",
                "actions": [f"Added tone instruction: {tone}"]}

    if action.startswith("format:"):
        fmt = action.split(":", 1)[1].strip().lower()
        desc = FORMAT_HINTS.get(fmt, fmt)
        return {"text": original.rstrip() + f"\n\n<output_format>Respond using {desc}.</output_format>",
                "change_note": f"Output format set to '{fmt}'.",
                "actions": [f"Added output format: {desc}"]}

    if action == "add_examples":
        scaffold = ("\n\n<example>\nInput: <describe a typical input here>\n"
                    "Expected output: <show the exact style you want>\n</example>")
        return {"text": original.rstrip() + scaffold,
                "change_note": "Few-shot scaffold added - fill in one real example for best results.",
                "actions": ["Added <example> scaffold (few-shot prompting)"]}

    if action == "add_constraints":
        scaffold = ("\n\n<constraints>\n- Maximum length: <N words>\n"
                    "- Must include: <required elements>\n"
                    "- Avoid: <things to exclude>\n</constraints>")
        return {"text": original.rstrip() + scaffold,
                "change_note": "Constraint block added - fill in your hard rules.",
                "actions": ["Added <constraints> scaffold"]}

    if action == "regenerate":
        regenerated = build_prompt(original, tier=opts.get("tier", "improved"))
        return {"text": regenerated["prompt"], "change_note": "Regenerated from the original idea.",
                "actions": [imp["title"] for imp in regenerated["improvements"]]}

    raise ValueError(f"Unknown mutation action: {action}")
