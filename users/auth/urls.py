from django.urls import path
from .views import (
    SubscriptionLoginView,
    account_settings_view,
    activate_view,
    cancel_token_verification_view,
    change_password_view,
    change_username_view,
    confirm_username_change_view,
    connect_gmail_view,
    disconnect_email_connection_view,
    forgot_password_view,
    forgot_username_view,
    gmail_oauth_callback_view,
    reactivate_legacy_account_view,
    reset_password_confirm_view,
    resend_token_view,
    signup_view,
    verify_token_view,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('forgot-username/', forgot_username_view, name='forgot_username'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', reset_password_confirm_view, name='reset_password_confirm'),
    path('account/settings/', account_settings_view, name='account_settings'),
    path('email/gmail/connect/', connect_gmail_view, name='connect_gmail'),
    path('email/gmail/callback/', gmail_oauth_callback_view, name='gmail_oauth_callback'),
    path(
        'email/connections/<int:connection_id>/disconnect/',
        disconnect_email_connection_view,
        name='disconnect_email_connection',
    ),
    path('account/change-username/', change_username_view, name='change_username'),
    path('account/change-username/confirm/', confirm_username_change_view, name='confirm_username_change'),
    path('account/change-password/', change_password_view, name='change_password'),
    path('verify-token/', verify_token_view, name='verify_token'),
    path('resend-token/', resend_token_view, name='resend_token'),
    path('cancel-verification/', cancel_token_verification_view, name='cancel_verification'),
    path('reactivate-account/', reactivate_legacy_account_view, name='reactivate_account'),
    path('activate/<uidb64>/<token>/', activate_view, name='activate'),
    path('login/', SubscriptionLoginView.as_view(), name='login'),
]
