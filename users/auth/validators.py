import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[a-z]', password): # <--- Added this!
            raise ValidationError(
                _("The password must contain at least one lowercase letter (a-z)."),
                code='password_no_lower',
            )
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter (A-Z)."),
                code='password_no_upper',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("The password must contain at least one number (0-9)."),
                code='password_no_number',
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _("The password must contain at least one special character."),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least one lowercase letter, one uppercase letter, "
            "one number, and one special character."
        )