from django import forms
from django.core.exceptions import ValidationError

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import LoginForm
from allauth.account.models import EmailAddress


class WardrobeLoginForm(LoginForm):
    """Email-only login with an actionable verification message."""

    def clean(self):
        try:
            return super().clean()
        except ValidationError:
            email = (self.data.get("login") or "").strip().lower()
            password = self.data.get("password") or ""
            if email and password:
                address = EmailAddress.objects.filter(
                    email__iexact=email, user__is_active=True
                ).select_related("user").first()
                if address and not address.verified and address.user.check_password(password):
                    self.add_error(
                        "login",
                        forms.ValidationError(
                            "Your password is correct, but your email is not verified yet. "
                            "Check your inbox or resend the verification email below.",
                            code="unverified_email",
                        ),
                    )
            raise


class WardrobeAccountAdapter(DefaultAccountAdapter):
    """Keep account creation successful when transactional email is unavailable.

    SMTP is an optional deployment dependency. If a provider is temporarily
    unavailable or credentials are not configured, signup should not become a
    generic HTTP 500; the account remains usable because verification is
    configured as optional. Password-reset email still uses the configured
    SMTP provider when available.
    """

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        try:
            return super().send_confirmation_mail(request, emailconfirmation, signup)
        except Exception:
            import logging
            logging.getLogger("accounts_app").exception(
                "Verification email could not be sent; signup will continue.")
            return None
