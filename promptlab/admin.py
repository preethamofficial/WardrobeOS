from django.contrib import admin

from .models import AIRequestLog, Prompt, PromptAnalysis, PromptTemplate, PromptVersion, WorkflowRun


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "source", "favorite", "use_count", "updated_at")
    list_filter = ("category", "source", "favorite")
    search_fields = ("title", "body", "tags")


@admin.register(PromptVersion)
class PromptVersionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "version_number", "score", "created_at")
    search_fields = ("prompt__title",)


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "featured", "use_count")
    list_filter = ("category", "featured")
    search_fields = ("title", "body")


@admin.register(PromptAnalysis)
class PromptAnalysisAdmin(admin.ModelAdmin):
    list_display = ("prompt", "score", "created_at")


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "kind", "status", "latency_ms",
                    "total_tokens", "created_at")
    list_filter = ("provider", "status", "kind")


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = ("name", "preset", "used_ai", "final_score", "created_at")
