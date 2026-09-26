"""AI workflow engine: connect prompts into a pipeline.

Research -> Summarize -> Analyze -> Improve -> Final answer.

Each node transforms the running text either with the local deterministic
engine (always available) or, when the user enables it and a provider is
configured, through the AI provider layer with fallback. The architecture is
node-based so new node types can be added in one place (`NODES`).
"""
from __future__ import annotations

import re

from ai.providers import complete_text
from .analyzer import analyze_prompt
from .mutations import mutate

PRESETS = {
    "research": {
        "label": "Research → Summarize → Analyze → Improve → Final",
        "nodes": ["clarify", "summarize", "analyze", "critique", "finalize"],
        "description": "Turn rough research notes into a structured, verified answer.",
    },
    "writing": {
        "label": "Draft → Critique → Refine → Final",
        "nodes": ["clarify", "critique", "refine", "finalize"],
        "description": "Classic draft-critique-improve loop for any text.",
    },
    "polish": {
        "label": "Quick polish",
        "nodes": ["critique", "finalize"],
        "description": "One critique pass and a clean final version.",
    },
}


def _local_step(node: str, text: str) -> tuple[str, str]:
    """Deterministic node implementations (no AI needed)."""
    if node == "clarify":
        lines = text.strip().splitlines()
        head = lines[0].strip() if lines else text.strip()
        rest = "\n".join(lines[1:]).strip()
        out = f"Objective: {head}\n\nDetails:\n{rest}" if rest else f"Objective: {head}"
        return out, "Restated the core objective at the top."
    if node == "summarize":
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        key = sents[:5]
        return ("Summary:\n" + "\n".join(f"• {s}" for s in key) + ("\n\nFull input retained below:\n" + text if len(sents) > 5 else ""),
                f"Condensed to {len(key)} key point(s).")
    if node == "analyze":
        analysis = analyze_prompt(text)
        bullets = "\n".join(f"• {s}" for s in analysis["suggestions"][:4])
        return (text.rstrip() + f"\n\n<analysis_notes>\nCurrent weaknesses addressed below:\n{bullets}\n</analysis_notes>",
                f"Scored {analysis['score']}/100 and attached improvement notes.")
    if node == "critique":
        analysis = analyze_prompt(text)
        critiques = "\n".join(f"• {w}" for w in analysis["weaknesses"][:4])
        return (text.rstrip() + f"\n\n<critique>\nCritic identified issues:\n{critiques}\n</critique>",
                "A critic pass listed concrete weaknesses.")
    if node == "refine":
        result = mutate(text, "improve")
        return result["text"], "Applied the improvement mutations (role, constraints, format)."
    if node == "finalize":
        result = mutate(text, "shorten", keep_sentences=6)
        score = analyze_prompt(result["text"])["score"]
        return result["text"], f"Final pass: tightened the text (score {score}/100)."
    return text, f"Unknown node '{node}' - text passed through."


_STEP_SYSTEM = {
    "clarify": "You restate objectives crisply. Output only the improved prompt text.",
    "summarize": "You summarize faithfully. Keep all key facts. Output only the result text.",
    "analyze": "You are a prompt analyst. Add a short analysis section with concrete improvements.",
    "critique": "You are a harsh but fair critic. List the 3-4 biggest weaknesses, then output the text.",
    "refine": "You rewrite prompts to fix every listed weakness. Output only the improved prompt.",
    "finalize": "You produce the final, clean, well-structured version. Output only the final text.",
}


def run_workflow(text: str, preset_key: str, *, use_ai: bool = False,
                 provider_id: str | None = None, timeout: int = 45) -> dict:
    """Execute a workflow. Returns steps + final text; never raises on AI errors."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Workflow input is empty.")
    preset = PRESETS.get(preset_key)
    if not preset:
        raise ValueError(f"Unknown workflow preset: {preset_key}")

    steps = []
    current = text
    for node in preset["nodes"]:
        if use_ai:
            result = complete_text(
                f"Current text:\n---\n{current}\n---\n"
                f"Apply this step: {node.upper()}. Improve it and return the full result.",
                system=_STEP_SYSTEM.get(node, "You improve prompt text."),
                providers=[provider_id] if provider_id else None,
                timeout=timeout,
            )
            if result.ok and result.text.strip():
                current = result.text.strip()
                note = f"AI step via {result.provider} ({result.model})."
                status, error = "ok", None
            else:
                local_text, local_note = _local_step(node, current)
                current = local_text
                note = f"AI step failed ({result.error_code or 'error'}) - local fallback applied."
                status, error = "fallback", result.error_message
        else:
            current, note = _local_step(node, current)
            status, error = "ok", None
        steps.append({"node": node, "status": status, "error": error,
                      "note": note, "output": current})

    final_score = analyze_prompt(current)["score"]
    return {"preset": preset_key, "label": preset["label"], "steps": steps,
            "final": current, "final_score": final_score, "used_ai": use_ai}
