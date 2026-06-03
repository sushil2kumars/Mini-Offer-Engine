from django.urls import path

from . import views

urlpatterns = [
    path("transactions/", views.ingest_transaction, name="ingest_transaction"),
    path("stats/", views.transaction_stats, name="transaction_stats"),
]
