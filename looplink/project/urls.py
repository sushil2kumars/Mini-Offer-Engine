from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from looplink.django_ext.templatetags.common_tags import static

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=static("base/images/favicon.png"), permanent=True)),
    path("", include("looplink.ui.base.urls")),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
]
