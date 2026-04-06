from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSecurityTest(TestCase):

    def test_password_complexity_requirements(self):
        """
        Test that passwords must meet complexity: 
        Length, Number, Special Char, and Uppercase.
        """
        invalid_passwords = [
            'short',             # Too short
            'alllowercase1!',    # No uppercase
            'NoNumber!',         # No number
            'NoSpecialChar1',    # No special character
            'ONLYUPPERCASE1!',   # No lowercase (good to include)
        ]
        
        user = User(username='testuser', email='test@example.com')
        
        for password in invalid_passwords:
            with self.subTest(password=password):
                with self.assertRaises(ValidationError):
                    validate_password(password, user)

    def test_password_is_hashed(self):
        """Test: The password must never be stored as plain text."""
        raw_password = "ComplexPassword123!"
        user = User.objects.create_user(
            username="secureuser", 
            email="secure@example.com", 
            password=raw_password
        )
        
        # This proves the password is NOT the raw string
        self.assertNotEqual(user.password, raw_password)
        # This proves Django can still 'verify' it via hashing
        self.assertTrue(user.check_password(raw_password))

    def test_invalid_email_format(self):
        """Test: Ensure malformed emails are rejected."""
        user = User(username="bademail", email="not-an-email")
        with self.assertRaises(ValidationError):
            user.full_clean() # Triggers Django's built-in email validation