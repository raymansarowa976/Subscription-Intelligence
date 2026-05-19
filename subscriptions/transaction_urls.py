from django.urls import path

from .views import (
    add_subscription_view,
    bulk_dismiss_inbox_leads_view,
    bulk_update_inbox_leads_view,
    candidate_list_view,
    confirm_candidate_view,
    dismiss_inbox_lead_view,
    ingest_transactions_view,
    mark_inbox_lead_newsletter_view,
    reject_candidate_view,
    restore_inbox_lead_view,
)


app_name = "transactions"

urlpatterns = [
    path("ingest/", ingest_transactions_view, name="ingest"),
    path("candidates/", candidate_list_view, name="candidates"),
    path("candidates/inbox/bulk-dismiss/", bulk_dismiss_inbox_leads_view, name="bulk_dismiss_inbox_leads"),
    path("candidates/inbox/bulk-update/", bulk_update_inbox_leads_view, name="bulk_update_inbox_leads"),
    path("candidates/inbox/<int:lead_id>/dismiss/", dismiss_inbox_lead_view, name="dismiss_inbox_lead"),
    path("candidates/inbox/<int:lead_id>/newsletter/", mark_inbox_lead_newsletter_view, name="mark_inbox_lead_newsletter"),
    path("candidates/inbox/<int:lead_id>/restore/", restore_inbox_lead_view, name="restore_inbox_lead"),
    path("candidates/<int:candidate_id>/confirm/", confirm_candidate_view, name="confirm_candidate"),
    path("candidates/<int:candidate_id>/reject/", reject_candidate_view, name="reject_candidate"),
    path("subscriptions/add/", add_subscription_view, name="add_subscription"),
]
