from django.urls import path

from .views import dashboard_view, scan_inbox_view


urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("email/scan/", scan_inbox_view, name="scan_inbox"),
]
