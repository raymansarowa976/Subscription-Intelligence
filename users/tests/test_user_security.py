from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from users.auth.forms import AccountRecoveryForm, PasswordChangeForm, UsernameChangeRequestForm
from users.auth.token_service import issue_email_token, verify_email_token

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

    def test_username_change_form_requires_available_matching_username(self):
        user = User.objects.create_user(
            username="currentuser",
            email="currentuser@gmail.com",
            password="Complex123!",
        )
        User.objects.create_user(
            username="takenuser",
            email="takenuser@gmail.com",
            password="Complex123!",
        )

        valid_form = UsernameChangeRequestForm(
            data={"new_username": "freshuser", "confirm_username": "freshuser"},
            user=user,
        )
        current_form = UsernameChangeRequestForm(
            data={"new_username": "currentuser", "confirm_username": "currentuser"},
            user=user,
        )
        taken_form = UsernameChangeRequestForm(
            data={"new_username": "takenuser", "confirm_username": "takenuser"},
            user=user,
        )
        mismatch_form = UsernameChangeRequestForm(
            data={"new_username": "freshuser", "confirm_username": "otheruser"},
            user=user,
        )

        self.assertTrue(valid_form.is_valid())
        self.assertFalse(current_form.is_valid())
        self.assertFalse(taken_form.is_valid())
        self.assertFalse(mismatch_form.is_valid())
        self.assertIn("confirm_username", mismatch_form.errors)

    def test_password_change_form_validates_old_password_and_new_password_rules(self):
        user = User.objects.create_user(
            username="passwordform",
            email="passwordform@gmail.com",
            password="Complex123!",
        )

        valid_form = PasswordChangeForm(
            data={
                "old_password": "Complex123!",
                "new_password": "Better456!",
                "confirm_password": "Better456!",
            },
            user=user,
        )
        wrong_old_form = PasswordChangeForm(
            data={
                "old_password": "Wrong123!",
                "new_password": "Better456!",
                "confirm_password": "Better456!",
            },
            user=user,
        )
        mismatch_form = PasswordChangeForm(
            data={
                "old_password": "Complex123!",
                "new_password": "Better456!",
                "confirm_password": "Different456!",
            },
            user=user,
        )

        self.assertTrue(valid_form.is_valid())
        self.assertFalse(wrong_old_form.is_valid())
        self.assertIn("old_password", wrong_old_form.errors)
        self.assertFalse(mismatch_form.is_valid())
        self.assertIn("confirm_password", mismatch_form.errors)

    def test_email_tokens_are_scoped_by_purpose(self):
        login_token = issue_email_token("scoped@gmail.com")
        username_token = issue_email_token("scoped@gmail.com", purpose="username-change")

        self.assertTrue(verify_email_token("scoped@gmail.com", login_token))
        self.assertTrue(
            verify_email_token("scoped@gmail.com", username_token, purpose="username-change")
        )
        self.assertFalse(verify_email_token("scoped@gmail.com", username_token))
        self.assertFalse(
            verify_email_token("scoped@gmail.com", login_token, purpose="username-change")
        )
