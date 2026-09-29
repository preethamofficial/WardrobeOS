"""Account self-service: city preferences, data export, account deletion."""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from allauth.account.models import EmailAddress
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from config.scoping import scoped_items, scoped_outfits, scoped_trips

from .export import build_export
from .forms import DeleteAccountForm, ProfileForm
from .models import Profile


@login_required
def preferences(request):
    """Set the home city used for weather, outfits and trip packing."""
    profile = Profile.for_user(request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved - weather now follows {profile.location_label}.")
            return redirect("preferences")
        messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileForm(instance=profile)
    counts = {
        "items": scoped_items(request.user).count(),
        "outfits": scoped_outfits(request.user).count(),
        "trips": scoped_trips(request.user).count(),
    }
    return render(request, "account/preferences.html",
                  {"form": form, "profile": profile, "counts": counts})


@login_required
def export_data(request):
    """Download everything we store about this account as one JSON file."""
    payload = build_export(request.user)
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    filename = f"wardrobeos-{request.user.username}-{stamp}.json"
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(body.encode("utf-8")))
    response["X-Content-Type-Options"] = "nosniff"
    messages.success(request, "Your data export has been downloaded.")
    return response


@login_required
def delete_account(request):
    """Permanently delete the account and all owned records (GDPR erasure)."""
    if request.method == "POST":
        form = DeleteAccountForm(request.POST, user=request.user)
        if form.is_valid():
            username = request.user.username
            user = request.user
            # Wardrobe photos on disk are removed by the Item post_delete signal;
            # every other table cascades from the User row.
            logout(request)
            user.delete()
            messages.success(request, f"Account “{username}” and all of its data were deleted.")
            return redirect("dashboard")
        messages.error(request, "Account not deleted - please check the fields below.")
    else:
        form = DeleteAccountForm(user=request.user)
    return render(request, "account/delete.html", {"form": form})


def verification_sent(request):
    """Anonymous landing page after signup and for users waiting on verification."""
    return render(request, "account/verification_sent.html")


@require_POST
def resend_verification(request):
    """Resend verification without exposing account existence."""
    email = (request.POST.get("email") or "").strip().lower()
    address = EmailAddress.objects.filter(
        email__iexact=email, user__is_active=True
    ).select_related("user").first()
    if address and not address.verified:
        address.send_confirmation(request, signup=False)
    messages.success(
        request,
        "If that email belongs to a WardrobeOS account, a fresh verification email has been sent. "
        "Check your inbox and spam folder."
    )
    return redirect("account_email_verification_sent_landing")
