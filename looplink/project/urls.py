from django.conf import settings
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from looplink.django_ext.templatetags.common_tags import static as static_tag

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=static_tag("base/images/favicon.png"), permanent=True)),
    path("", include("looplink.ui.base.urls")),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("api/", include("looplink.transactions.urls")),
    path("api/shoppers/", include("looplink.shoppers.urls")),
    path("shoppers/", include("looplink.ui.shoppers.urls")),
    path("stats/", include("looplink.ui.stats.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
