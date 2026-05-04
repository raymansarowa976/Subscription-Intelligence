from django.test import Client, TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.core import mail
from django.core.cache import cache
import re

User = get_user_model()

class RegistrationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.signup_url = reverse('accounts:signup')
        self.verify_url = reverse('accounts:verify_token')
        self.resend_url = reverse('accounts:resend_token')
        self.login_url = reverse('accounts:login')
        self.forgot_username_url = reverse('accounts:forgot_username')
        self.forgot_password_url = reverse('accounts:forgot_password')
        self.change_username_url = reverse('accounts:change_username')
        self.confirm_username_change_url = reverse('accounts:confirm_username_change')
        self.change_password_url = reverse('accounts:change_password')
        self.user_data = {
            'first_name': 'Taylor',
            'last_name': 'Jordan',
            'username': 'tester',
            'email': 'tester@gmail.com',
            'password': 'Complex123!',
            'confirm_password': 'Complex123!'
        }

    def login_verified(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['login_token_verified'] = True
        session.save()

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

    def test_login_token_verification_is_rate_limited_after_repeated_failures(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})

        for _ in range(5):
            response = self.client.post(self.verify_url, {'token': '999999'})
            self.assertContains(response, 'The verification token is invalid or has expired.')

        limited_response = self.client.post(self.verify_url, {'token': '999999'})

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, 'Too many attempts. Please wait a few minutes and try again.')

    def test_resend_token_sends_new_email(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})
        response = self.client.post(self.resend_url)

        self.assertRedirects(response, self.verify_url)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('login token', mail.outbox[-1].subject.lower())

    def test_resend_token_is_rate_limited(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')
        self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})

        for _ in range(3):
            response = self.client.post(self.resend_url, follow=True)
            self.assertContains(response, 'A new verification token has been sent.')

        limited_response = self.client.post(self.resend_url, follow=True)

        self.assertRedirects(limited_response, self.verify_url)
        self.assertContains(limited_response, 'Too many attempts. Please wait a few minutes and try again.')
        self.assertEqual(len(mail.outbox), 4)

    @override_settings(SHOW_LOGIN_TOKEN_IN_UI=True)
    def test_login_still_sends_email_when_development_token_is_visible(self):
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(email='tester@gmail.com')

        response = self.client.post(self.login_url, {'username': user.username, 'password': 'Complex123!'})

        self.assertRedirects(response, self.verify_url)
        self.assertEqual(len(mail.outbox), 1)

    def test_login_is_rate_limited_after_repeated_invalid_attempts(self):
        User.objects.create_user(
            username='ratelimited',
            email='ratelimited@gmail.com',
            password='Complex123!',
            is_active=True,
        )

        for _ in range(5):
            response = self.client.post(
                self.login_url,
                {'username': 'ratelimited', 'password': 'Wrong123!'},
            )
            self.assertContains(response, 'Please enter a correct username and password.')

        limited_response = self.client.post(
            self.login_url,
            {'username': 'ratelimited', 'password': 'Complex123!'},
        )

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, 'Too many attempts. Please wait a few minutes and try again.')
        self.assertEqual(len(mail.outbox), 0)

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

    def test_forgot_username_is_rate_limited(self):
        User.objects.create_user(
            username='recoverlimit',
            email='recoverlimit@gmail.com',
            password='Complex123!',
            is_active=True,
        )

        for _ in range(5):
            response = self.client.post(
                self.forgot_username_url,
                {'email': 'recoverlimit@gmail.com'},
                follow=True,
            )
            self.assertContains(response, 'Your username has been sent')

        limited_response = self.client.post(
            self.forgot_username_url,
            {'email': 'recoverlimit@gmail.com'},
        )

        self.assertContains(limited_response, 'Too many attempts. Please wait a few minutes and try again.')
        self.assertEqual(len(mail.outbox), 5)

    def test_forgot_password_sends_reset_link_and_changes_password_after_confirm(self):
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
        self.assertContains(response, 'A password reset link has been sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset', mail.outbox[0].subject.lower())
        self.assertNotIn('Complex123!', mail.outbox[0].body)
        self.assertIn('/accounts/reset-password/', mail.outbox[0].body)

        user.refresh_from_db()
        self.assertTrue(user.check_password('Complex123!'))

        reset_path = re.search(r'http://testserver(/[^\s]+)', mail.outbox[0].body).group(1)
        confirm_response = self.client.post(
            reset_path,
            {
                'new_password': 'Reset456!',
                'confirm_password': 'Reset456!',
            },
            follow=True,
        )

        self.assertRedirects(confirm_response, self.login_url)
        self.assertContains(confirm_response, 'Your password has been reset. Sign in with your new password.')
        user.refresh_from_db()
        self.assertFalse(user.check_password('Complex123!'))
        self.assertTrue(user.check_password('Reset456!'))

        login_response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': 'Reset456!'},
        )
        self.assertRedirects(login_response, self.verify_url)

    def test_password_reset_invalidates_existing_sessions(self):
        user = User.objects.create_user(
            username='resetloggedin',
            email='resetloggedin@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        logged_in_client = Client()
        logged_in_client.force_login(user)
        session = logged_in_client.session
        session['login_token_verified'] = True
        session.save()
        session_key = session.session_key

        self.client.post(
            self.forgot_password_url,
            {'email': 'resetloggedin@gmail.com'},
        )
        reset_path = re.search(r'http://testserver(/[^\s]+)', mail.outbox[0].body).group(1)
        self.client.post(
            reset_path,
            {
                'new_password': 'Reset456!',
                'confirm_password': 'Reset456!',
            },
        )

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        dashboard_response = logged_in_client.get(reverse('dashboard'))
        self.assertRedirects(dashboard_response, f"{self.login_url}?next={reverse('dashboard')}")

    def test_password_reset_rejects_invalid_link(self):
        response = self.client.get(
            reverse('accounts:reset_password_confirm', kwargs={'uidb64': 'bad-uid', 'token': 'bad-token'}),
            follow=True,
        )

        self.assertRedirects(response, self.forgot_password_url)
        self.assertContains(response, 'The password reset link is invalid or has expired.')

    def test_forgot_password_tells_user_when_email_has_no_account(self):
        response = self.client.post(
            self.forgot_password_url,
            {'email': 'missing@gmail.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account is associated with this email address.')
        self.assertEqual(len(mail.outbox), 0)

    def test_forgot_password_is_rate_limited(self):
        User.objects.create_user(
            username='resetlimit',
            email='resetlimit@gmail.com',
            password='Complex123!',
            is_active=True,
        )

        for _ in range(5):
            response = self.client.post(
                self.forgot_password_url,
                {'email': 'resetlimit@gmail.com'},
                follow=True,
            )
            self.assertContains(response, 'A password reset link has been sent')

        limited_response = self.client.post(
            self.forgot_password_url,
            {'email': 'resetlimit@gmail.com'},
        )

        self.assertContains(limited_response, 'Too many attempts. Please wait a few minutes and try again.')
        self.assertEqual(len(mail.outbox), 5)

    def test_username_change_requires_matching_usernames(self):
        user = User.objects.create_user(
            username='currentuser',
            email='current@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)

        response = self.client.post(
            self.change_username_url,
            {
                'new_username': 'newuser',
                'confirm_username': 'differentuser',
                'current_password': 'Complex123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usernames do not match.')
        self.assertEqual(len(mail.outbox), 0)

    def test_username_change_sends_token_and_confirms_change(self):
        user = User.objects.create_user(
            username='olduser',
            email='olduser@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)

        response = self.client.post(
            self.change_username_url,
            {
                'new_username': 'newuser',
                'confirm_username': 'newuser',
                'current_password': 'Complex123!',
            },
            follow=True,
        )

        self.assertRedirects(response, self.confirm_username_change_url)
        self.assertContains(response, 'A confirmation token has been sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('username change', mail.outbox[0].subject.lower())
        self.assertIn('Requested username: newuser', mail.outbox[0].body)
        token = re.search(r'(\d{6})', mail.outbox[0].body).group(1)

        confirm_response = self.client.post(
            self.confirm_username_change_url,
            {'token': token},
            follow=True,
        )

        self.assertRedirects(confirm_response, reverse('dashboard'))
        self.assertContains(confirm_response, 'Your username has been updated.')
        user.refresh_from_db()
        self.assertEqual(user.username, 'newuser')

    def test_username_change_rejects_invalid_token(self):
        user = User.objects.create_user(
            username='tokenold',
            email='tokenold@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)
        self.client.post(
            self.change_username_url,
            {
                'new_username': 'tokennew',
                'confirm_username': 'tokennew',
                'current_password': 'Complex123!',
            },
        )

        response = self.client.post(
            self.confirm_username_change_url,
            {'token': '999999'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The confirmation token is invalid or has expired.')
        user.refresh_from_db()
        self.assertEqual(user.username, 'tokenold')

    def test_username_change_requires_current_password(self):
        user = User.objects.create_user(
            username='passwordprotected',
            email='passwordprotected@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)

        response = self.client.post(
            self.change_username_url,
            {
                'new_username': 'passwordprotectednew',
                'confirm_username': 'passwordprotectednew',
                'current_password': 'Wrong123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter your current password.')
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn('pending_username_change', self.client.session)

    def test_password_change_updates_password_and_ends_current_session(self):
        user = User.objects.create_user(
            username='passworduser',
            email='password@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)
        session_key = self.client.session.session_key

        response = self.client.post(
            self.change_password_url,
            {
                'old_password': 'Complex123!',
                'new_password': 'Better456!',
                'confirm_password': 'Better456!',
            },
            follow=True,
        )

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, 'Your password has been updated. Sign in with your new password.')
        self.assertEqual(len(mail.outbox), 0)
        user.refresh_from_db()
        self.assertFalse(user.check_password('Complex123!'))
        self.assertTrue(user.check_password('Better456!'))
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

        login_response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': 'Better456!'},
        )
        self.assertRedirects(login_response, self.verify_url)

    def test_password_change_invalidates_all_user_sessions(self):
        user = User.objects.create_user(
            username='multisession',
            email='multisession@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)
        current_session_key = self.client.session.session_key

        other_client = Client()
        other_client.force_login(user)
        other_session = other_client.session
        other_session['login_token_verified'] = True
        other_session.save()
        other_session_key = other_session.session_key

        response = self.client.post(
            self.change_password_url,
            {
                'old_password': 'Complex123!',
                'new_password': 'Better456!',
                'confirm_password': 'Better456!',
            },
            follow=True,
        )

        self.assertRedirects(response, self.login_url)
        self.assertFalse(Session.objects.filter(session_key=current_session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=other_session_key).exists())
        other_response = other_client.get(reverse('dashboard'))
        self.assertRedirects(other_response, f"{self.login_url}?next={reverse('dashboard')}")

    def test_password_change_requires_current_password(self):
        user = User.objects.create_user(
            username='wrongold',
            email='wrongold@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)

        response = self.client.post(
            self.change_password_url,
            {
                'old_password': 'Wrong123!',
                'new_password': 'Better456!',
                'confirm_password': 'Better456!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter your current password.')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Complex123!'))

    def test_password_change_requires_matching_valid_new_password(self):
        user = User.objects.create_user(
            username='badnewpassword',
            email='badnewpassword@gmail.com',
            password='Complex123!',
            is_active=True,
        )
        self.login_verified(user)

        mismatch_response = self.client.post(
            self.change_password_url,
            {
                'old_password': 'Complex123!',
                'new_password': 'Better456!',
                'confirm_password': 'Different456!',
            },
        )
        weak_response = self.client.post(
            self.change_password_url,
            {
                'old_password': 'Complex123!',
                'new_password': 'weak',
                'confirm_password': 'weak',
            },
        )

        self.assertContains(mismatch_response, 'Passwords do not match.')
        self.assertContains(weak_response, 'The password must contain at least 8 characters')
        self.assertContains(weak_response, 'The password must contain at least one uppercase letter')
        self.assertContains(weak_response, 'The password must contain at least one number')
        self.assertContains(weak_response, 'The password must contain at least one special character')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Complex123!'))
