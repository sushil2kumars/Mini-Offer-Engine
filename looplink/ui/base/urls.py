from django.urls import path

from looplink.ui.base.views import (
    HtmxExampleView,
    TransactionTraceView,
    default,
)

urlpatterns = [
    path("", default, name="default"),
    path("htmx-example/", HtmxExampleView.as_view(), name=HtmxExampleView.urlname),
    path("debug/tx/<str:transaction_id>/", TransactionTraceView.as_view(), name="transaction_trace"),
]
