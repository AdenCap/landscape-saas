"""
Custom allauth adapters for Tradevo.
Handles the Business-creation requirement for new social signups
and routes social logins through the existing 2FA post-login check.
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):

    def get_login_redirect_url(self, request):
        """Route all logins (including social) through the 2FA post-login check."""
        return reverse("post_login_check")

    def get_signup_redirect_url(self, request):
        """New social users need to complete business setup."""
        return reverse("social_signup_complete")

    def is_open_for_signup(self, request):
        return True


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def is_open_for_signup(self, request, sociallogin):
        return True

    def save_user(self, request, sociallogin, form=None):
        """
        Create a new User from social login.
        Set role=owner and flag the session for business completion.
        """
        user = super().save_user(request, sociallogin, form)
        user.role = "owner"
        user.save(update_fields=["role"])
        request.session["social_signup_pending"] = True
        return user

    def populate_user(self, request, sociallogin, data):
        """Generate a unique username from the email prefix."""
        user = super().populate_user(request, sociallogin, data)

        if not user.username and user.email:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            base = user.email.split("@")[0].lower()
            base = "".join(c for c in base if c.isalnum() or c == "_") or "user"
            username = base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            user.username = username

        return user

    def pre_social_login(self, request, sociallogin):
        """
        Auto-link social account when email matches an existing user.
        Prevents duplicate accounts when someone signs up with email/password
        then later tries "Continue with Google" using the same email.
        """
        if sociallogin.is_existing:
            return

        email = sociallogin.account.extra_data.get("email", "").lower().strip()
        if not email:
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            existing_user = User.objects.get(email__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return

        sociallogin.connect(request, existing_user)

    def get_connect_redirect_url(self, request, socialaccount):
        """After linking a social account from settings, redirect back."""
        return reverse("business_settings")

    def authentication_error(self, request, provider_id, error=None,
                             exception=None, extra_context=None):
        messages.error(
            request,
            f"There was a problem signing in with {provider_id.title()}. "
            "Please try again or use your username and password."
        )
        return redirect("login")
