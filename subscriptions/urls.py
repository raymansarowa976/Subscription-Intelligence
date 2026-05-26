from django.urls import path

from .views import (
    analytics_monthly_report_view,
    analytics_view,
    dashboard_view,
    data_sources_view,
    gmail_integrations_view,
    scan_inbox_view,
    subscription_results_view,
)


urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("gmail/", gmail_integrations_view, name="gmail_integrations"),
    path("analytics/", analytics_view, name="analytics"),
    path("analytics/monthly-report/", analytics_monthly_report_view, name="analytics_monthly_report"),
    path("data-sources/", data_sources_view, name="data_sources"),
    path("subscriptions/", subscription_results_view, name="subscription_results"),
    path("email/scan/", scan_inbox_view, name="scan_inbox"),
]
