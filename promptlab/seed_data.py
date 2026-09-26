"""Seed templates for the Prompt Library - every category covered.

Seeding is idempotent (match on title). Free of any API dependency.
"""
from __future__ import annotations

TEMPLATES = [
    # Coding / Programming
    ("Code reviewer", "coding", "Review code for bugs, security and readability.",
     "You are a senior software engineer performing a code review.\n\nTask: Review the code below for correctness bugs, security issues, performance problems and readability.\n\n<code>\n{CODE}\n</code>\n\nRequirements:\n- Order findings by severity (critical, major, minor).\n- For each finding: quote the line, explain the issue, show the fix as code.\n- Do not rewrite the whole program.\n\nOutput format: Markdown with a summary table, then detailed findings.",
     "Role, structured output, negative constraints", "code,review,bugs"),
    ("Bug hunter", "programming", "Systematic debugging from an error message.",
     "You are an expert debugger.\n\nTask: I am getting this error:\n<error>\n{ERROR}\n</error>\n\nHere is the relevant code:\n<code>\n{CODE}\n</code>\n\nSteps:\n1. State the most likely root cause.\n2. Explain why it happens.\n3. Give the minimal fix as a diff.\n4. Suggest one test that would have caught it.\n\nDo not guess without evidence from the error or code; if you must assume something, label it.",
     "Task decomposition, negative constraints", "debugging,error"),
    ("SQL query builder", "data_analysis", "Turn a question into a correct, safe SQL query.",
     "You are a senior data analyst who writes production-safe SQL.\n\nSchema:\n<schema>\n{SCHEMA}\n</schema>\n\nTask: Write a query that answers: {QUESTION}\n\nConstraints:\n- Use standard SQL; note the dialect if you rely on vendor features.\n- Never expose or log sensitive columns; mask them if needed.\n- Explain the query in 2 sentences after the code.",
     "Context engineering, constraints", "sql,database"),
    # Students / Education
    ("Explain like a tutor", "education", "Learn any topic from first principles.",
     "You are a patient expert tutor.\n\nTask: Teach me {TOPIC} assuming I am a complete beginner.\n\nStructure:\n1. Simple explanation (no jargon).\n2. One real-world analogy.\n3. A worked example.\n4. Three practice questions with answers hidden under an 'Answers' heading.\n\nDefine every technical term the first time you use it.",
     "Persona, structured output", "learning,tutor"),
    ("Exam prep coach", "students", "Turn notes into an active-recall study plan.",
     "You are a study coach specialising in active recall.\n\nTask: Convert my notes into a 7-day study plan for {SUBJECT}.\n\n<notes>\n{NOTES}\n</notes>\n\nRequirements:\n- Each day: topics to review, active-recall questions, one self-test.\n- Spaced repetition: revisit earlier topics on later days.\n- Maximum 90 minutes of study per day.",
     "Constraints, quality bar", "study,exam"),
    # Resume / Interview
    ("Resume bullet upgrader", "resume", "Rewrite weak resume bullets into achievement statements.",
     "You are a professional resume writer and hiring manager.\n\nTask: Rewrite each resume bullet below to follow: strong action verb + task + quantified result.\n\n<bullets>\n{BULLETS}\n</bullets>\n\nConstraints:\n- Never invent metrics; use [X] placeholders where numbers are unknown.\n- Keep each bullet under 25 words.\n- Output a table: original | rewritten | why it is stronger.",
     "Few-shot style, negative constraints", "resume,career"),
    ("Interview simulator", "interview", "Practice with realistic questions and grading.",
     "You are an experienced interviewer for a {ROLE} position.\n\nTask: Run a mock interview.\n\nRules:\n- Ask one question at a time and wait for my answer.\n- After each answer, grade it 1-10 with one strength and one improvement.\n- Cover: background, technical depth, behavioural (STAR), and one curveball.\n- After 8 questions, give an overall verdict and the top 3 things to improve.",
     "Persona, instruction hierarchy", "interview,career"),
    # Business / Marketing / Content
    ("One-page business case", "business", "Evaluate an idea like a consultant.",
     "You are a management consultant.\n\nTask: Write a one-page business case for {IDEA}.\n\n<context>\n{CONTEXT}\n</context>\n\nSections: Executive summary, Problem, Proposal, Costs vs benefits (state assumptions), Risks with mitigations, Recommended next step.\n\nConstraints:\n- Quantify wherever the input data allows; label every estimate as an estimate.\n- Maximum 500 words.",
     "Structured output, edge cases", "business,strategy"),
    ("Landing page copy", "marketing", "High-converting landing page copy.",
     "You are a senior conversion copywriter.\n\nTask: Write landing page copy for {PRODUCT} targeting {AUDIENCE}.\n\nProduct facts (source of truth):\n<facts>\n{FACTS}\n</facts>\n\nDeliver: 3 headline options, subheadline, 3 benefit blocks (benefit > feature), social-proof placeholder, FAQ (4 items), and one primary call to action.\n\nDo not invent product claims that are not in the facts.",
     "Context engineering, negative constraints", "copy,landing"),
    ("SEO content brief", "content_writing", "A complete brief writers can execute.",
     "You are an SEO content strategist.\n\nTask: Create a content brief for the keyword \"{KEYWORD}\".\n\nInclude: search intent analysis, target audience, recommended word count, H2/H3 outline, entities to cover, internal-link suggestions, and 5 FAQ questions.\n\nConstraints: no keyword stuffing; prioritise genuinely helpful content.",
     "Structured output", "seo,content"),
    ("Blog post drafter", "content_writing", "First draft from a brief.",
     "You are an experienced editorial writer.\n\nTask: Write a blog post from this brief:\n<brief>\n{BRIEF}\n</brief>\n\nRequirements:\n- Hook in the first two sentences; scannable subheadings every 200 words.\n- Active voice, concrete examples, no filler.\n- End with a 3-bullet takeaway and one question for readers.",
     "Role, quality bar", "blog,writing"),
    ("Research notes", "research", "Structured notes with evidence discipline.",
     "You are a meticulous research assistant.\n\nTask: Produce structured notes on {TOPIC}.\n\nSections: Key points, Supporting evidence (flag [citation needed] where required), Open questions, Minority views vs consensus.\n\nConstraints:\n- Do not fabricate sources; name none unless you are certain they exist.\n- Mark every uncertain claim explicitly.",
     "Negative constraints, edge cases", "research,notes"),
    ("Data story", "data_analysis", "Explain a dataset's story honestly.",
     "You are a senior data analyst.\n\nTask: Analyse the data summary below and tell its story.\n<data>\n{DATA}\n</data>\n\nOutput: Method (1-2 sentences), Findings as a table, Caveats (data quality, sample size), Correlation-vs-causation warnings, 3 recommended next analyses.",
     "Structured output, negative constraints", "data,analysis"),
    ("Security review", "cybersecurity", "Defensive review of a system or flow.",
     "You are a defensive security engineer.\n\nTask: Review the system description below for security risks.\n<system>\n{SYSTEM}\n</system>\n\nOutput: risk table (risk, likelihood, impact, mitigation), priority order for fixes, and the security principle behind each mitigation (e.g. least privilege, defence in depth).\n\nConstraints: defensive guidance only - no exploit instructions.",
     "Negative constraints, structured output", "security,review"),
    ("System prompt architect", "ai", "Design a robust system prompt for a chatbot.",
     "You are a prompt engineering specialist.\n\nTask: Write a system prompt for a chatbot that: {PURPOSE}\n\nInclude: role and expertise, scope boundaries (what it must refuse), tone rules, output format defaults, and handling for out-of-scope requests.\n\nWrap the final system prompt in a single fenced block so it can be copied.",
     "Role, instruction hierarchy", "chatbot,system-prompt"),
    ("Weekly planning", "productivity", "Plan a realistic, prioritised week.",
     "You are an experienced productivity planner.\n\nTask: Plan my week.\n\n<tasks>\n{TASKS}\n</tasks>\n\nRules:\n- Prioritise by impact, flag the single most important task per day.\n- Maximum 6 focused hours per day; include breaks and buffer time.\n- Show the plan as a table (day, focus, tasks, why).\n- If the task list is unrealistic, say so and propose what to drop.",
     "Constraints, edge cases", "planning,week"),
    ("Image prompt builder", "image_generation", "Rich image-model prompt with negative prompt.",
     "You are an art director writing prompts for image-generation models.\n\nTask: Create a prompt for: {SUBJECT}\n\nDeliver:\n1. Main prompt: one comma-separated line covering subject, style, lighting, composition, colour palette, quality terms.\n2. Negative prompt line: what the model should avoid.\n3. One variation with a different mood.\n\nDo not reference living artists by name.",
     "Structured output, negative constraints", "image,midjourney"),
    ("Video scene prompt", "video_generation", "Generative-video prompt with camera language.",
     "You are a video director writing prompts for generative video models.\n\nTask: A {DURATION}-second clip of {SCENE}.\n\nSpecify: scene description, one continuous action, camera movement (dolly/pan/static), lighting, style, and audio ambience. One prompt per line, no multi-scene montages.",
     "Constraints", "video,scene"),
    ("LinkedIn post", "social_media", "Professional post with a real hook.",
     "You are a social media content strategist.\n\nTask: Write a LinkedIn post about {TOPIC}.\n\nStructure: hook line (no clickbait), 3 short paragraphs or bullets, one takeaway, one question to drive comments, 3-5 niche hashtags.\n\nTone: professional but human. Maximum 200 words.",
     "Persona, constraints", "linkedin,post"),
    ("Client proposal", "freelancing", "Win-more-work proposal structure.",
     "You are a freelance business coach.\n\nTask: Draft a proposal for this project:\n<project>\n{PROJECT}\n</project>\n\nSections: understanding of the goal, proposed approach with milestones, deliverables, timeline, price options (good/better/best), and 2 social-proof placeholders.\n\nConstraints: never promise results you cannot guarantee; keep under 400 words.",
     "Structured output, negative constraints", "proposal,client"),
]


def run_seed(verbose: bool = True) -> tuple[int, int]:
    from .models import PromptTemplate
    created, updated = 0, 0
    for title, category, description, body, technique, tags in TEMPLATES:
        obj, was_created = PromptTemplate.objects.get_or_create(
            title=title,
            defaults={"category": category, "description": description, "body": body,
                      "technique": technique, "tags": tags},
        )
        created += 1 if was_created else 0
        updated += 0 if was_created else 1
    if verbose:
        print(f"Prompt templates seeded: {created} created, {updated} existing.")
    return created, updated
