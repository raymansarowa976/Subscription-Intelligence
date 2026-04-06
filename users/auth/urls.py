from django.contrib.auth.views import LoginView
from django.urls import path
from .views import signup_view, activate_view

app_name = 'accounts'

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('activate/<uidb64>/<token>/', activate_view, name='activate'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
]
