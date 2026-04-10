from django.urls import path
from .views import (
    SubscriptionLoginView,
    activate_view,
    cancel_token_verification_view,
    reactivate_legacy_account_view,
    resend_token_view,
    signup_view,
    verify_token_view,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('verify-token/', verify_token_view, name='verify_token'),
    path('resend-token/', resend_token_view, name='resend_token'),
    path('cancel-verification/', cancel_token_verification_view, name='cancel_verification'),
    path('reactivate-account/', reactivate_legacy_account_view, name='reactivate_account'),
    path('activate/<uidb64>/<token>/', activate_view, name='activate'),
    path('login/', SubscriptionLoginView.as_view(), name='login'),
]
