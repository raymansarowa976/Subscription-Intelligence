from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Once you're ready, you'll likely add your apps here:
    # path('subscriptions/', include('subscriptions.urls')),
    # path('users/', include('users.urls')),
]
