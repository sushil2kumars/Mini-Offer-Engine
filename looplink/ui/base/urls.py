from django.urls import path

from looplink.ui.base.views import (
    HtmxExampleView,
    default,
)

urlpatterns = [
    path("", default, name="default"),
    path("htmx-example/", HtmxExampleView.as_view(), name=HtmxExampleView.urlname),
]
