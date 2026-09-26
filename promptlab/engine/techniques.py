"""Prompting technique catalog + intent-aware technique selection.

Each technique documents *when* it is applied so the UI can explain why a
generated prompt looks the way it does (transparent prompt engineering, no
hidden reasoning).
"""
from __future__ import annotations

TECHNIQUES = {
    "role": {"name": "Role prompting",
             "when": "Gives the model a clear expertise and point of view."},
    "persona": {"name": "Persona prompting",
                "when": "Adds audience-aware voice and style to the response."},
    "context": {"name": "Context engineering",
                "when": "Supplies the background facts the model cannot guess."},
    "objective": {"name": "Objective definition",
                  "when": "One unambiguous task statement removes guesswork."},
    "constraints": {"name": "Constraint prompting",
                    "when": "Hard rules (length, scope, style) keep output usable."},
    "negative_constraints": {"name": "Negative constraints",
                             "when": "Explicitly listing what to avoid prevents failure modes."},
    "output_format": {"name": "Structured output prompting",
                      "when": "A defined shape (sections, table, JSON) makes results usable."},
    "schema": {"name": "Output schema generation",
               "when": "Field-by-field contracts enable programmatic use of the response."},
    "few_shot": {"name": "Few-shot prompting",
                 "when": "Input/output examples anchor style and quality expectations."},
    "zero_shot": {"name": "Zero-shot clarity",
                  "when": "A precisely described task often needs no examples at all."},
    "decomposition": {"name": "Task decomposition",
                      "when": "Complex requests become ordered, checkable steps."},
    "delimiters": {"name": "Delimiter usage",
                   "when": "Sections like <role>/<context> prevent instruction blending."},
    "instruction_hierarchy": {"name": "Instruction hierarchy",
                              "when": "Priority order tells the model what wins on conflict."},
    "quality_bar": {"name": "Quality requirements",
                    "when": "Defines what 'good' means for this exact task."},
    "edge_cases": {"name": "Edge case consideration",
                   "when": "Pre-agreed behaviour for missing or ambiguous inputs."},
    "self_check": {"name": "Self-evaluation",
                   "when": "A short verification checklist before the final answer."},
    "critique_refine": {"name": "Critique and refinement",
                        "when": "Draft, criticise, improve - for high-stakes prompts."},
    "react": {"name": "ReAct-style workflow",
              "when": "Think -> act -> observe loops for multi-step tasks."},
}

INTENTS = {
    "writing": {
        "label": "Writing & editing",
        "role": "an experienced editorial writer and copy editor",
        "verbs": ("write", "draft", "edit", "rewrite", "proofread", "blog", "article",
                  "essay", "story", "newsletter", "email", "letter", "copy", "caption"),
        "format": "Markdown with a short introduction, clear section headings and a closing summary.",
        "constraints": ["Match the requested tone consistently.",
                        "Prefer active voice and concrete language."],
    },
    "coding": {
        "label": "Coding & debugging",
        "role": "a senior software engineer and code reviewer",
        "verbs": ("code", "function", "bug", "debug", "refactor", "script", "api", "class",
                  "program", "python", "javascript", "java", "sql", "html", "css", "typescript",
                  "algorithm", "error", "exception", "test", "implement", "regex"),
        "format": "1) Brief approach, 2) complete code in a fenced block, 3) short usage notes.",
        "constraints": ["Code must be complete and runnable - no omitted sections.",
                        "Handle obvious error cases and edge conditions.",
                        "Add brief comments only where they aid understanding."],
    },
    "analysis": {
        "label": "Analysis & reasoning",
        "role": "a rigorous analyst",
        "verbs": ("analyze", "analyse", "evaluate", "assess", "compare", "review",
                  "why", "explain", "trade-off", "pros and cons", "decision"),
        "format": "Structured sections: Key findings, Evidence, Trade-offs, Recommendation.",
        "constraints": ["Separate facts from assumptions explicitly.",
                        "State confidence levels for major claims."],
    },
    "summarization": {
        "label": "Summarization",
        "role": "an expert at distilling complex material",
        "verbs": ("summarize", "summarise", "tldr", "shorten", "condense", "digest", "recap"),
        "format": "One-paragraph overview followed by 3-6 key bullet points.",
        "constraints": ["Never invent facts that are not in the source material.",
                        "Preserve numbers, names and dates exactly."],
    },
    "brainstorming": {
        "label": "Brainstorming & ideas",
        "role": "a creative strategist",
        "verbs": ("ideas", "brainstorm", "suggest", "names", "concepts", "options",
                  "alternatives", "creative"),
        "format": "Numbered list; each idea gets a title, one-line pitch and a feasibility note.",
        "constraints": ["Include at least one conventional and one unconventional option.",
                        "Avoid repeating variations of the same idea."],
    },
    "learning": {
        "label": "Learning & explanation",
        "role": "a patient expert tutor",
        "verbs": ("teach", "learn", "explain", "understand", "beginner", "tutorial",
                  "study", "student", "exam", "homework"),
        "format": "Simple explanation, an analogy, a worked example, then 2-3 practice questions.",
        "constraints": ["Build from first principles; define jargon on first use.",
                        "Check understanding with one question at the end."],
    },
    "planning": {
        "label": "Planning & productivity",
        "role": "an experienced project planner",
        "verbs": ("plan", "schedule", "roadmap", "itinerary", "strategy", "steps",
                  "organize", "organise", "routine", "goals"),
        "format": "Phased plan with milestones, time estimates and dependencies.",
        "constraints": ["Flag the riskiest assumption in each phase.",
                        "Keep each step small enough to finish in one sitting."],
    },
    "marketing": {
        "label": "Marketing & growth",
        "role": "a senior growth marketing strategist",
        "verbs": ("marketing", "ad ", "ads ", "campaign", "seo", "brand", "launch", "landing",
                  "conversion", "audience", "promo"),
        "format": "Strategy summary, then channel-by-channel tactics with sample copy.",
        "constraints": ["Back claims with the provided product facts only.",
                        "Include one measurable success metric per tactic."],
    },
    "career": {
        "label": "Career (resume & interview)",
        "role": "a professional career coach and hiring manager",
        "verbs": ("resume", "cv", "interview", "job", "cover letter", "linkedin",
                  "hiring", "recruiter", "career", "salary"),
        "format": "Actionable feedback list first, then rewritten examples.",
        "constraints": ["Use strong action verbs and quantified achievements.",
                        "Never fabricate experience, metrics or employers."],
    },
    "data_analysis": {
        "label": "Data analysis",
        "role": "a senior data analyst",
        "verbs": ("data", "dataset", "csv", "statistics", "chart", "trend",
                  "regression", "correlation", "metrics", "dashboard"),
        "format": "Method, then findings as a table, then caveats and next steps.",
        "constraints": ["State assumptions about missing or dirty data.",
                        "Distinguish correlation from causation explicitly."],
    },
    "research": {
        "label": "Research",
        "role": "a meticulous research assistant",
        "verbs": ("research", "sources", "literature", "survey", "paper", "cite",
                  "evidence", "study"),
        "format": "Structured notes: key points, supporting evidence, open questions, sources.",
        "constraints": ["Flag every claim that would need a citation.",
                        "Separate consensus from minority views."],
    },
    "cybersecurity": {
        "label": "Cybersecurity",
        "role": "a defensive security engineer",
        "verbs": ("security", "vulnerability", "exploit", "pentest", "phishing",
                  "firewall", "encryption", "malware", "cve", "threat"),
        "format": "Risk summary, severity rating, mitigation steps in priority order.",
        "constraints": ["Defensive framing only - no working exploit instructions.",
                        "Reference the relevant security principle for each mitigation."],
    },
    "ai_prompting": {
        "label": "AI & prompt engineering",
        "role": "a prompt engineering specialist",
        "verbs": ("prompt", "llm", "gpt", "chatbot", "agent", "system message"),
        "format": "Ready-to-use prompt in a fenced block plus a short usage note.",
        "constraints": ["Keep instructions model-agnostic where possible.",
                        "Prefer explicit structure over implied expectations."],
    },
    "image_prompt": {
        "label": "Image generation",
        "role": "an art director writing image-model prompts",
        "verbs": ("image", "picture", "logo", "illustration", "photo", "art ",
                  "wallpaper", "icon", "midjourney", "dall", "stable diffusion"),
        "format": "One comma-separated prompt line, then an optional negative-prompt line.",
        "constraints": ["Describe subject, style, lighting, composition and quality terms.",
                        "No references to living artists' styles by name."],
    },
    "video_prompt": {
        "label": "Video generation",
        "role": "a video director writing generative-video prompts",
        "verbs": ("video", "animation", "scene", "clip", "motion", "storyboard"),
        "format": "Scene description, camera movement, style, duration feel, then audio notes.",
        "constraints": ["Keep one continuous action per prompt.",
                        "Specify camera language explicitly."],
    },
    "social_media": {
        "label": "Social media",
        "role": "a social media content strategist",
        "verbs": ("twitter", "tweet", "instagram", "linkedin post", "tiktok", "youtube",
                  "thread", "post", "hashtag", "reel"),
        "format": "Ready-to-post copy, then hashtag suggestions, then a posting tip.",
        "constraints": ["Respect each platform's tone and length conventions.",
                        "One clear call to action per post."],
    },
    "business": {
        "label": "Business & operations",
        "role": "a management consultant",
        "verbs": ("business", "startup", "revenue", "pricing", "customers", "b2b",
                  "proposal", "pitch", "market", "operations", "process"),
        "format": "Executive summary, options with trade-offs, recommended next steps.",
        "constraints": ["Quantify costs and benefits where the input data allows.",
                        "Call out the riskiest assumption explicitly."],
    },
    "translation": {
        "label": "Translation & localisation",
        "role": "a professional translator and localisation specialist",
        "verbs": ("translate", "translation", "localize", "localise"),
        "format": "Translation first, then brief notes on choices made.",
        "constraints": ["Preserve meaning, tone and formatting of the original.",
                        "Keep names, code and technical identifiers unchanged."],
    },
    "generic": {
        "label": "General task",
        "role": "a knowledgeable, precise assistant",
        "verbs": (),
        "format": "Clear sections with a short summary at the top.",
        "constraints": ["Ask for clarification only if the task is impossible to attempt.",
                        "Prefer concrete, specific statements over generalities."],
    },
}

INTENT_LABELS = {key: value["label"] for key, value in INTENTS.items()}


def detect_intent(text: str) -> tuple[str, list[str]]:
    """Keyword-scored intent detection. Returns (intent_id, matched_signals)."""
    lowered = f" {text.lower()} "
    scores: dict[str, int] = {}
    signals: dict[str, list[str]] = {}
    for intent_id, spec in INTENTS.items():
        hits = [verb for verb in spec["verbs"] if verb in lowered]
        if hits:
            scores[intent_id] = len(hits)
            signals[intent_id] = hits
    if not scores:
        return "generic", []
    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0], signals[best[0]]


def select_techniques(intent: str, tier: str, *, has_examples: bool = False,
                      needs_structure: bool = True) -> list[str]:
    """Choose applicable technique ids for a tier (basic/improved/expert/maximum)."""
    if tier == "basic":
        return ["objective", "few_shot" if has_examples else "zero_shot"]
    techs = ["role", "objective", "context", "constraints", "output_format", "delimiters"]
    techs.append("few_shot" if has_examples else "zero_shot")
    if needs_structure:
        techs += ["negative_constraints", "quality_bar"]
    if tier in ("expert", "maximum"):
        techs += ["instruction_hierarchy", "edge_cases"]
    if tier == "maximum":
        techs += ["decomposition", "self_check", "critique_refine"]
    return [t for t in techs if t in TECHNIQUES]


