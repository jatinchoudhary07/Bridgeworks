# core/adapter.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    1) Normalize email
    2) Accept 'email' instead of 'login' for auth
    3) Hash & save password on signup (password1/password2)
    """

    def clean_email(self, email):
        return email.strip().lower()

    def authenticate(self, request, **credentials):
        # Frontend sends "email" instead of "login"
        if "email" in credentials and "login" not in credentials:
            credentials["login"] = credentials.pop("email")
        return super().authenticate(request, **credentials)

    def save_user(self, request, user, form, commit=True):
        """
        Called by allauth during signup.
        We make sure the password is hashed (set_password).
        """
        user = super().save_user(request, user, form, commit=False)
        password = form.cleaned_data.get("password1")
        if password:
            user.set_password(password)  # hashes + stores
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Handles Google (and any other OAuth) social login.

    Key behaviour:
    - If the Google account is already connected to a Django user → allow.
    - If a Django user with the same email exists → connect the Google account
      to that existing user automatically (no separate invite needed).
    - Only genuinely NEW users (no matching email) go through the normal
      allauth invite-only signup gate.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called right after the OAuth provider authenticates the user but
        BEFORE allauth decides whether to create / log-in / error.

        We short-circuit here to connect an existing Django account so that
        INVITATIONS_INVITE_ONLY does not block returning users.
        """
        # Already linked to a Django user — nothing to do
        if sociallogin.is_existing:
            return

        # Try to find an existing user by email from the provider payload
        email = (
            sociallogin.account.extra_data.get("email", "")
            or sociallogin.email_addresses[0].email
            if sociallogin.email_addresses
            else ""
        )
        if not email:
            return

        try:
            existing_user = User.objects.get(email__iexact=email.strip().lower())
            # Connect the Google social-account record to the existing user
            # so allauth treats this as a LOGIN rather than a SIGNUP
            sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            # Genuinely new user — let allauth's normal invite-only gate handle it
            pass

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Allow auto-signup via Google OAuth for users whose email already
        exists in the system.  New users still need an invitation.
        """
        email = (
            sociallogin.account.extra_data.get("email", "")
        )
        if email and User.objects.filter(email__iexact=email.strip().lower()).exists():
            return True
        # Fall back to default behaviour (respects INVITATIONS_INVITE_ONLY)
        return super().is_auto_signup_allowed(request, sociallogin)
