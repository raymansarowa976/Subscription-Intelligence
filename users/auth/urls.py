from django.urls import path
from .views import SubscriptionLoginView, signup_view, activate_view

app_name = 'accounts'

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('activate/<uidb64>/<token>/', activate_view, name='activate'),
    path('login/', SubscriptionLoginView.as_view(), name='login'),
]
