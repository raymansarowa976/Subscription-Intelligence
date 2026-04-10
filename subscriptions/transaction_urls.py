from django.urls import path

from .views import (
    add_subscription_view,
    candidate_list_view,
    confirm_candidate_view,
    ingest_transactions_view,
    reject_candidate_view,
)


app_name = "transactions"

urlpatterns = [
    path("ingest/", ingest_transactions_view, name="ingest"),
    path("candidates/", candidate_list_view, name="candidates"),
    path("candidates/<int:candidate_id>/confirm/", confirm_candidate_view, name="confirm_candidate"),
    path("candidates/<int:candidate_id>/reject/", reject_candidate_view, name="reject_candidate"),
    path("subscriptions/add/", add_subscription_view, name="add_subscription"),
]
