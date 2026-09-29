from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_EMAIL_VERIFICATION="mandatory",
)
class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="preetham-test",
            email="preetham-test@example.com",
            password="StrongPass123!",
        )
        self.email = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=False,
        )

    def test_authentication_is_email_only_and_email_is_required(self):
        self.assertEqual(settings.ACCOUNT_LOGIN_METHODS, {"email"})
        self.assertEqual(settings.ACCOUNT_SIGNUP_FIELDS, ["email*", "password1*", "password2*"])
        response = self.client.post(
            reverse("account_login"),
            {"login": "preetham-test", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION="optional")
    def test_new_unverified_email_can_sign_in_with_correct_password(self):
        user = get_user_model().objects.create_user(
            username="optional-login",
            email="optional-login@example.com",
            password="StrongPass123!",
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=False,
        )
        response = self.client.post(
            reverse("account_login"),
            {"login": user.email, "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_verified_email_can_sign_in(self):
        self.email.verified = True
        self.email.save(update_fields=["verified"])
        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.email, "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.pk))

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse("account_reset_password"),
            {"email": self.user.email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset", mail.outbox[0].subject)
        self.assertIn("password reset", mail.outbox[0].body.lower())


    def test_unverified_correct_password_shows_verification_guidance(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.email, "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "your email is not verified yet")
        self.assertContains(response, "Resend verification email")

    def test_password_reset_page_is_public(self):
        response = self.client.get(reverse("account_reset_password"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")

    def test_resend_verification_is_public_and_sends_mail(self):
        response = self.client.post(
            reverse("resend_verification"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("account_email_verification_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirm", mail.outbox[0].subject)

    def test_verification_landing_is_public(self):
        response = self.client.get(reverse("account_email_verification_sent"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verify your email")

    def test_auth_redirect_includes_security_headers(self):
        response = self.client.get("/wardrobe/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Permissions-Policy"], "camera=(self), microphone=(self), geolocation=(), payment=(), usb=()")
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
