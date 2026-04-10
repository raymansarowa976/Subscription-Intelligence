from django.contrib.auth.forms import AuthenticationForm


class SubscriptionAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": (
            "Please enter a correct username and password. "
            "Both fields are case-sensitive."
        ),
        "inactive": "This account is inactive.",
    }
