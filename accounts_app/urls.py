from django.shortcuts import redirect
from django.urls import path

from . import views

urlpatterns = [
    path("verification-sent/", views.verification_sent, name="verification_sent"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
    path("", lambda request: redirect("preferences", permanent=False), name="profile_index"),
    path("preferences/", views.preferences, name="preferences"),
    path("export/", views.export_data, name="export_data"),
    path("delete/", views.delete_account, name="delete_account"),
]