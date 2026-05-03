from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from users.auth.forms import AccountRecoveryForm
from users.auth.views import _generate_temporary_password

User = get_user_model()

class UserSecurityTest(TestCase):

    def test_password_complexity_requirements(self):
        """Test that passwords must meet complexity requirements."""
        invalid_passwords = [
            'short',             # Too short
            'alllowercase1!',    # No uppercase
            'NoNumber!',         # No number
            'NoSpecialChar1',    # No special character
            'ONLYUPPERCASE1!',   # No lowercase
        ]
        
        user = User(username='testuser', email='test@example.com')
        
        for password in invalid_passwords:
            with self.subTest(password=password):
                # If this is failing, your settings.py might not have the validator registered
                with self.assertRaises(ValidationError):
                    validate_password(password, user)

    def test_password_is_hashed(self):
        """Test: The password must never be stored as plain text."""
        raw_password = "ComplexPassword123!"
        # Use a unique username to avoid collisions
        user = User.objects.create_user(
            username="secureuser_test", 
            email="secure_test@example.com", 
            password=raw_password
        )
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))

    def test_invalid_email_format(self):
        """Test: Ensure malformed emails are rejected."""
        user = User(username="bademail", email="not-an-email")
        with self.assertRaises(ValidationError):
            # clean_fields is safer than full_clean when the object is incomplete
            user.clean_fields(exclude=['password', 'last_login'])

    def test_account_recovery_form_normalizes_email(self):
        form = AccountRecoveryForm(data={"email": "  RECOVERY@GMAIL.COM  "})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["email"], "recovery@gmail.com")

    def test_account_recovery_form_rejects_invalid_email(self):
        form = AccountRecoveryForm(data={"email": "not-an-email"})

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_temporary_password_generator_meets_password_requirements(self):
        user = User(username="temporaryuser", email="temporary@gmail.com")

        temporary_password = _generate_temporary_password(user)

        validate_password(temporary_password, user)
        self.assertGreaterEqual(len(temporary_password), 8)
        self.assertRegex(temporary_password, r"[a-z]")
        self.assertRegex(temporary_password, r"[A-Z]")
        self.assertRegex(temporary_password, r"[0-9]")
        self.assertRegex(temporary_password, r'[!@#$%^&*(),.?":{}|<>]')
