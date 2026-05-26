from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
import re


User = get_user_model()

BASE_CURRENCY_CHOICES = [
    ("USD", "USD - US Dollar"),
    ("CAD", "CAD - Canadian Dollar"),
    ("EUR", "EUR - Euro"),
    ("GBP", "GBP - British Pound"),
]


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
        for name in ["password", "confirm_password"]:
            self.fields[name].widget.attrs["class"] = (
                f"{self.fields[name].widget.attrs.get('class', input_classes)} pr-12"
            )
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
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginTokenVerificationForm(forms.Form):
    token = forms.CharField(max_length=6, min_length=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        for _, field in self.fields.items():
            field.widget.attrs.setdefault("class", input_classes)
            field.widget.attrs.setdefault("placeholder", field.label)
        self.fields["token"].help_text = "Enter the 6-digit verification token from your email."
        self.fields["token"].widget.attrs["inputmode"] = "numeric"
        self.fields["token"].widget.attrs["autocomplete"] = "one-time-code"

    def clean_token(self):
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Enter a 6-digit numeric token.")
        return token


class ResendTokenForm(forms.Form):
    pass


class BaseCurrencyForm(forms.Form):
    base_currency = forms.ChoiceField(
        choices=BASE_CURRENCY_CHOICES,
        label="Base reporting currency",
        error_messages={"invalid_choice": "Choose a supported reporting currency."},
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["base_currency"].initial = user.base_currency
        self.fields["base_currency"].widget.attrs.update(
            {
                "class": (
                    "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
                    "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
                ),
                "aria-label": "Base reporting currency",
            }
        )

    def clean_base_currency(self):
        return self.cleaned_data["base_currency"].strip().upper()


class AccountRecoveryForm(forms.Form):
    email = forms.EmailField(label="Account email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        self.fields["email"].widget.attrs.setdefault("class", input_classes)
        self.fields["email"].widget.attrs.setdefault("placeholder", "Enter your account email")
        self.fields["email"].widget.attrs["autocomplete"] = "email"

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class UsernameChangeRequestForm(forms.Form):
    new_username = forms.CharField(max_length=150, label="New username")
    confirm_username = forms.CharField(max_length=150, label="Confirm new username")
    current_password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", input_classes)
            field.widget.attrs.setdefault("placeholder", field.label)
            if name != "current_password":
                field.widget.attrs["autocomplete"] = "username"
            else:
                field.widget.attrs["class"] = f"{field.widget.attrs.get('class', input_classes)} pr-12"
        self.fields["new_username"].help_text = "Enter the username you want to use going forward."
        self.fields["current_password"].help_text = "Confirm your current password before we send a username change token."

    def clean_new_username(self):
        username = self.cleaned_data["new_username"].strip()
        if self.user and username == self.user.username:
            raise forms.ValidationError("Enter a different username than your current one.")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("An account with this username already exists.")
        return username

    def clean_confirm_username(self):
        return self.cleaned_data["confirm_username"].strip()

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]
        if self.user and not self.user.check_password(current_password):
            raise forms.ValidationError("Enter your current password.")
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("new_username")
        confirm_username = cleaned_data.get("confirm_username")
        if username and confirm_username and username != confirm_username:
            self.add_error("confirm_username", "Usernames do not match.")
        return cleaned_data


class UsernameChangeTokenForm(forms.Form):
    token = forms.CharField(max_length=6, min_length=6, label="Confirmation token")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        self.fields["token"].widget.attrs.setdefault("class", input_classes)
        self.fields["token"].widget.attrs.setdefault("placeholder", "Enter the 6-digit token")
        self.fields["token"].widget.attrs["inputmode"] = "numeric"
        self.fields["token"].widget.attrs["autocomplete"] = "one-time-code"

    def clean_token(self):
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Enter a 6-digit numeric token.")
        return token


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        for _, field in self.fields.items():
            field.widget.attrs.setdefault("class", input_classes)
            field.widget.attrs.setdefault("placeholder", field.label)
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', input_classes)} pr-12"
        self.fields["new_password"].help_text = (
            "Use at least 8 characters with uppercase, lowercase, a number, and a special character."
        )

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]
        if self.user and not self.user.check_password(old_password):
            raise forms.ValidationError("Enter your current password.")
        return old_password

    def clean_new_password(self):
        new_password = self.cleaned_data.get("new_password")
        if new_password:
            password_validation.validate_password(new_password, self.user)
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class PasswordResetConfirmForm(forms.Form):
    new_password = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        input_classes = (
            "block w-full rounded-2xl border-black/10 bg-stone-50 px-4 py-3 "
            "text-sm shadow-sm transition focus:border-pine focus:ring-pine"
        )
        for _, field in self.fields.items():
            field.widget.attrs.setdefault("class", input_classes)
            field.widget.attrs.setdefault("placeholder", field.label)
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', input_classes)} pr-12"
        self.fields["new_password"].help_text = (
            "Use at least 8 characters with uppercase, lowercase, a number, and a special character."
        )

    def clean_new_password(self):
        new_password = self.cleaned_data.get("new_password")
        if new_password:
            password_validation.validate_password(new_password, self.user)
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data
