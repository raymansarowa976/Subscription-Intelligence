from django.urls import path

from .views import dashboard_view, scan_inbox_view, subscription_results_view


urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("subscriptions/", subscription_results_view, name="subscription_results"),
    path("email/scan/", scan_inbox_view, name="scan_inbox"),
]
