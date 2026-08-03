from allauth.account.forms import SignupForm
from django import forms

class SimpleSignupForm(SignupForm):
    """
    Custom Allauth signup form to ensure password is saved
    and username = email for internal consistency.
    """
    email = forms.EmailField(label="Email", required=True)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, required=True)

    def save(self, request):
        user = super().save(request)
        # Always set username = email for Allauth consistency
        user.username = self.cleaned_data["email"]
        # Explicitly set password to ensure hashed save
        user.set_password(self.cleaned_data["password1"])
        user.save()
        return user
