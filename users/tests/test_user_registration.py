from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
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
        self.forgot_username_url = reverse('accounts:forgot_username')
        self.forgot_password_url = reverse('accounts:forgot_password')
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

    @override_settings(SHOW_LOGIN_TOKEN_IN_UI=True)
    def test_login_still_sends_email_when_development_token_is_visible(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')

        response = self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})

        self.assertRedirects(response, self.verify_url)
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_username_emails_associated_username(self):
        User.objects.create_user(
            username='recoveruser',
            email='recover@gmail.com',
            password='Complex123!',
            is_active=True,
        )

        response = self.client.post(
            self.forgot_username_url,
            {'email': 'RECOVER@gmail.com'},
            follow=True,
        )

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, 'Your username has been sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('username', mail.outbox[0].subject.lower())
        self.assertIn('recoveruser', mail.outbox[0].body)
        self.assertNotIn('Complex123!', mail.outbox[0].body)

    def test_forgot_username_tells_user_when_email_has_no_account(self):
        response = self.client.post(
            self.forgot_username_url,
            {'email': 'missing@gmail.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account is associated with this email address.')
        self.assertEqual(len(mail.outbox), 0)

    def test_forgot_password_sends_temporary_password_and_replaces_old_password(self):
        user = User.objects.create_user(
            username='resetuser',
            email='reset@gmail.com',
            password='Complex123!',
            is_active=True,
        )

        response = self.client.post(
            self.forgot_password_url,
            {'email': 'reset@gmail.com'},
            follow=True,
        )

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, 'A temporary password has been sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('temporary', mail.outbox[0].subject.lower())
        self.assertNotIn('Complex123!', mail.outbox[0].body)

        temporary_password = re.search(r'Your temporary password is: ([^\n]+)', mail.outbox[0].body).group(1)
        validate_password(temporary_password, user)
        user.refresh_from_db()
        self.assertFalse(user.check_password('Complex123!'))
        self.assertTrue(user.check_password(temporary_password))

        login_response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': temporary_password},
        )
        self.assertRedirects(login_response, self.verify_url)

    def test_forgot_password_tells_user_when_email_has_no_account(self):
        response = self.client.post(
            self.forgot_password_url,
            {'email': 'missing@gmail.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account is associated with this email address.')
        self.assertEqual(len(mail.outbox), 0)
