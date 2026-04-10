from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
import re


User = get_user_model()


class SignupForm(forms.ModelForm):
    NAME_PATTERN = re.compile(r"^[A-Za-z]{2,}$")
    ALLOWED_EMAIL_DOMAINS = {
        "gmail.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
    }
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        label="Confirm password",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "password", "confirm_password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", input_classes)
            field.widget.attrs.setdefault("placeholder", field.label)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["first_name"].help_text = "Letters only, at least 2 characters."
        self.fields["last_name"].help_text = "Letters only, at least 2 characters."
        self.fields["email"].help_text = (
            "Use a valid personal email from a supported provider like gmail.com or outlook.com."
        )
        self.fields["password"].help_text = (
            "Use at least 8 characters with uppercase, lowercase, a number, and a special character."
        )

    def _clean_name(self, field_name):
        value = self.cleaned_data[field_name].strip()
        if not self.NAME_PATTERN.fullmatch(value):
            raise ValidationError("Use letters only with no numbers or special characters.")
        return value.title()

    def clean_first_name(self):
        return self._clean_name("first_name")

    def clean_last_name(self):
        return self._clean_name("last_name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if domain not in self.ALLOWED_EMAIL_DOMAINS:
            raise forms.ValidationError(
                "Use a valid email from a supported provider like gmail.com, hotmail.com, or outlook.com."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            password_validation.validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
