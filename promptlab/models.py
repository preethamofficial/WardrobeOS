from django.db import models
from django.utils import timezone


class Prompt(models.Model):
    """A saved prompt with its metadata. Editing creates a new version."""
    CATEGORIES = [
        ("coding", "Coding"), ("programming", "Programming"), ("students", "Students"),
        ("education", "Education"), ("resume", "Resume"), ("interview", "Interview"),
        ("business", "Business"), ("marketing", "Marketing"),
        ("content_writing", "Content Writing"), ("research", "Research"),
        ("data_analysis", "Data Analysis"), ("cybersecurity", "Cybersecurity"),
        ("ai", "AI"), ("productivity", "Productivity"),
        ("image_generation", "Image Generation"), ("video_generation", "Video Generation"),
        ("social_media", "Social Media"), ("freelancing", "Freelancing"),
        ("other", "Other"),
    ]
    TONES = [("professional", "Professional"), ("friendly", "Friendly"), ("casual", "Casual"),
             ("academic", "Academic"), ("persuasive", "Persuasive"), ("neutral", "Neutral"),
             ("humorous", "Humorous"), ("", "Not set")]

    title = models.CharField(max_length=160)
    body = models.TextField()
    goal = models.CharField(max_length=240, blank=True, help_text="What this prompt should produce")
    category = models.CharField(max_length=30, choices=CATEGORIES, default="other")
    tags = models.CharField(max_length=240, blank=True, help_text="Comma separated")
    target_model = models.CharField(max_length=60, default="any", blank=True)
    audience = models.CharField(max_length=120, blank=True)
    tone = models.CharField(max_length=20, choices=TONES, blank=True)
    language = models.CharField(max_length=40, default="English", blank=True)
    source = models.CharField(max_length=20, default="manual",
                              choices=[("studio", "Studio"), ("optimizer", "Optimizer"),
                                       ("library", "Library"), ("workflow", "Workflow"),
                                       ("manual", "Manual")])
    favorite = models.BooleanField(default=False)
    use_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def latest_version(self):
        return self.versions.first()

    @property
    def current_score(self):
        latest = self.latest_version
        return latest.score if latest and latest.score is not None else None

    def mark_used(self):
        self.use_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["use_count", "last_used_at"])


class PromptVersion(models.Model):
    """Immutable snapshot of a prompt. Never overwritten, only appended."""
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField(default=1)
    body = models.TextField()
    score = models.FloatField(blank=True, null=True)
    change_note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [models.UniqueConstraint(fields=["prompt", "version_number"],
                                               name="uniq_prompt_version")]

    def __str__(self):
        return f"{self.prompt.title} v{self.version_number}"


class PromptAnalysis(models.Model):
    """Stored analyzer report for a specific prompt body."""
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="analyses",
                               blank=True, null=True)
    body = models.TextField()
    score = models.FloatField(default=0)
    report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Analysis {self.score:.0f}/100"


class PromptTemplate(models.Model):
    """Seeded/curated library template users can copy into their own prompts."""
    title = models.CharField(max_length=160, unique=True)
    category = models.CharField(max_length=30, choices=Prompt.CATEGORIES)
    description = models.CharField(max_length=240, blank=True)
    body = models.TextField()
    technique = models.CharField(max_length=60, blank=True)
    tags = models.CharField(max_length=240, blank=True)
    featured = models.BooleanField(default=False)
    use_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "title"]

    def __str__(self):
        return self.title


class AIRequestLog(models.Model):
    """Every provider call is logged: usage stats + failure diagnostics."""
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=20, default="compare",
                            choices=[("compare", "Compare"), ("workflow", "Workflow"),
                                     ("other", "Other")])
    status = models.CharField(max_length=12, default="ok",
                              choices=[("ok", "OK"), ("error", "Error")])
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.CharField(max_length=240, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(blank=True, null=True)
    completion_tokens = models.PositiveIntegerField(blank=True, null=True)
    total_tokens = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "AI request logs"

    def __str__(self):
        return f"{self.provider}:{self.model or '-'} {self.status} {self.latency_ms}ms"


class WorkflowRun(models.Model):
    """Stored result of one workflow execution."""
    name = models.CharField(max_length=160)
    preset = models.CharField(max_length=40)
    input_text = models.TextField()
    final_text = models.TextField(blank=True)
    final_score = models.FloatField(blank=True, null=True)
    used_ai = models.BooleanField(default=False)
    steps = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


