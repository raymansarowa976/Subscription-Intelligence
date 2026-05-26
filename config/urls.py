from django.contrib import admin
from django.shortcuts import render
from django.urls import path, include

def landing_page(request):
    return render(request, "landing.html")

def contact_page(request):
    return render(request, "contact.html")

urlpatterns = [
    path('', landing_page, name='home'),
    path('contact/', contact_page, name='contact'),
    path('admin/', admin.site.urls),  # Keep this one
    path('dashboard/', include('subscriptions.urls')),
    path('transactions/', include(('subscriptions.transaction_urls', 'transactions'), namespace='transactions')),
    path('accounts/', include(('users.auth.urls', 'accounts'), namespace='accounts')),
]
