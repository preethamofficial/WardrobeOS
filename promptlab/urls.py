from django.urls import path

from . import views

urlpatterns = [
    path("", views.lab_dashboard, name="lab_dashboard"),
    path("studio/", views.studio, name="studio"),
    path("analyze/", views.analyzer, name="analyzer"),
    path("optimize/", views.optimizer, name="optimizer"),
    path("library/", views.library, name="library"),
    path("prompts/add/", views.prompt_save, name="prompt_save"),
    path("prompts/<int:pk>/", views.prompt_detail, name="prompt_detail"),
    path("prompts/<int:pk>/edit/", views.prompt_edit, name="prompt_edit"),
    path("prompts/<int:pk>/delete/", views.prompt_delete, name="prompt_delete"),
    path("prompts/<int:pk>/favorite/", views.prompt_favorite, name="prompt_favorite"),
    path("prompts/<int:pk>/duplicate/", views.prompt_duplicate, name="prompt_duplicate"),
    path("prompts/<int:pk>/use/", views.prompt_use, name="prompt_use"),
    path("templates/<int:pk>/use/", views.template_use, name="template_use"),
    path("compare/", views.compare, name="compare"),
    path("workflows/", views.workflows, name="workflows"),
    path("api/analyze/", views.api_analyze, name="api_analyze"),
    path("api/status/", views.api_status, name="api_status"),
]
