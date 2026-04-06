from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

def root_redirect(request):
    return redirect('accounts:signup')

urlpatterns = [
    path('', root_redirect, name='home'),
    path('admin/', admin.site.urls),  # Keep this one
    path('accounts/', include(('users.auth.urls', 'accounts'), namespace='accounts')),
]
