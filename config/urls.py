from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Keep this one
    path('accounts/', include(('users.auth.urls', 'accounts'), namespace='accounts')),
]
