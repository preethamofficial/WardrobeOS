from django import forms
from django.core.exceptions import ValidationError

from allauth.account.forms import LoginForm
from allauth.account.models import EmailAddress


class WardrobeLoginForm(LoginForm):
    """Email-first login with a clear message for unverified accounts."""

    def clean(self):
        try:
            return super().clean()
        except ValidationError:
            email = (self.data.get("login") or "").strip().lower()
            password = self.data.get("password") or ""
            if email and password:
                address = (
                    EmailAddress.objects.filter(
                        email__iexact=email,
                        user__is_active=True,
                    )
                    .select_related("user")
                    .first()
                )
                if (
                    address
                    and not address.verified
                    and address.user.check_password(password)
                ):
                    self.add_error(
                        "login",
                        forms.ValidationError(
                            "Your password is correct, but your email is not verified yet. "
                            "Check your inbox or use the verification link below.",
                            code="unverified_email",
                        ),
                    )
                    # The original allauth validation exception is intentionally
                    # suppressed here: it describes the sign-in failure as a
                    # generic credential error even when the password is right.
                    return self.cleaned_data
            raise
