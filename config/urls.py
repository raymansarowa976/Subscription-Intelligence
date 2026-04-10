from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('accounts:login')

urlpatterns = [
    path('', root_redirect, name='home'),
    path('admin/', admin.site.urls),  # Keep this one
    path('dashboard/', include('subscriptions.urls')),
    path('accounts/', include(('users.auth.urls', 'accounts'), namespace='accounts')),
]
