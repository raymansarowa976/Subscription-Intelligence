from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()

class RegistrationTest(TestCase):
    def setUp(self):
        # FIX 1: Corrected string syntax (no extra quotes around colon)
        self.signup_url = reverse('accounts:signup')
        self.user_data = {
            'first_name': 'Taylor',
            'last_name': 'Jordan',
            'username': 'tester',
            'email': 'tester@gmail.com',
            'password': 'Complex123!',
            'confirm_password': 'Complex123!'
        }

    def test_signup_creates_inactive_user(self):
        """Test: Users must be inactive until they verify email."""
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.assertFalse(user.is_active)

    def test_signup_sends_email(self):
        """Test: An activation email is triggered on signup."""
        self.client.post(self.signup_url, self.user_data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Activate your account', mail.outbox[0].subject)

    def test_signup_rejects_unsupported_email_domain(self):
        payload = self.user_data.copy()
        payload['email'] = 'tester@company.org'

        response = self.client.post(self.signup_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Use a valid email from a supported provider like gmail.com, hotmail.com, or outlook.com.',
        )
        self.assertFalse(User.objects.filter(email='tester@company.org').exists())

    def test_activation_with_valid_token(self):
        """Test: Clicking the email link actually activates the user."""
        # FIX 2: Clean data for User.objects.create_user
        data = self.user_data.copy()
        data.pop('confirm_password', None) 

        user = User.objects.create_user(**data)
        user.is_active = False
        user.save()

        # Generate the real token logic Django uses
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # FIX 3: Added 'accounts:' namespace
        activation_url = reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(activation_url)
        
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        # FIX 4: Added 'accounts:' namespace (Ensure this exists in your urls.py!)
        self.assertRedirects(response, reverse('accounts:login'))

    def test_activation_with_invalid_token(self):
        """Test: Malicious or broken links do not activate accounts."""
        # FIX 5: Clean data here as well
        data = self.user_data.copy()
        data.pop('confirm_password', None)

        user = User.objects.create_user(**data)
        user.is_active = False
        user.save()

        # FIX 6: Added 'accounts:' namespace
        activation_url = reverse('accounts:activate', kwargs={'uidb64': 'wrong-id', 'token': 'wrong-token'})
        self.client.get(activation_url)
        
        user.refresh_from_db()
        self.assertFalse(user.is_active)
