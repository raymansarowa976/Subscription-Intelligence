from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
import re

User = get_user_model()

class RegistrationTest(TestCase):
    def setUp(self):
        self.signup_url = reverse('accounts:signup')
        self.verify_url = reverse('accounts:verify_token')
        self.resend_url = reverse('accounts:resend_token')
        self.login_url = reverse('accounts:login')
        self.user_data = {
            'first_name': 'Taylor',
            'last_name': 'Jordan',
            'username': 'tester',
            'email': 'tester@gmail.com',
            'password': 'Complex123!',
            'confirm_password': 'Complex123!'
        }

    def test_signup_creates_inactive_user(self):
        """Test: Users can sign up, then verify after login."""
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.assertTrue(user.is_active)

    def test_signup_does_not_send_email_until_login(self):
        """Test: Verification email is triggered after login, not signup."""
        self.client.post(self.signup_url, self.user_data)
        self.assertEqual(len(mail.outbox), 0)

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
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})
        token = re.search(r'(\d{6})', mail.outbox[0].body).group(1)

        response = self.client.post(self.verify_url, {'token': token})

        self.assertRedirects(response, reverse('dashboard'))

    def test_activation_with_invalid_token(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})

        response = self.client.post(self.verify_url, {'token': '999999'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The verification token is invalid or has expired.')

    def test_resend_token_sends_new_email(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})
        response = self.client.post(self.resend_url)

        self.assertRedirects(response, self.verify_url)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('login token', mail.outbox[-1].subject.lower())
