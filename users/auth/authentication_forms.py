from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


User = get_user_model()


class SubscriptionAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": (
            "Please enter a correct username and password. "
            "Both fields are case-sensitive."
        ),
        "inactive": "This account is inactive.",
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            user = User.objects.filter(username=username).first()
            if user and user.check_password(password) and not user.is_active:
                raise ValidationError(
                    self.error_messages["inactive"],
                    code="inactive",
                )

        return super().clean()
