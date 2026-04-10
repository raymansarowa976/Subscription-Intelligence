from django.urls import path

from .views import candidate_list_view, confirm_candidate_view, ingest_transactions_view


app_name = "transactions"

urlpatterns = [
    path("ingest/", ingest_transactions_view, name="ingest"),
    path("candidates/", candidate_list_view, name="candidates"),
    path("candidates/<int:candidate_id>/confirm/", confirm_candidate_view, name="confirm_candidate"),
]
