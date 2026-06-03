from django.shortcuts import render
from django.urls import reverse
from django.views.generic import TemplateView

from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action


def default(request):
    return render(
        request,
        "base/default.html",
        {
            "htmx_example_url": reverse(HtmxExampleView.urlname),
        },
    )


class HtmxExampleView(DjangoHtmxActionMixin, TemplateView):
    template_name = "base/htmx_example.html"
    urlname = "base_htmx_example"
    container_id = "main-htmx-content"

    @dj_hx_action("get")
    def initial_state(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/initial_state.html",
            {
                "container_id": self.container_id,
            },
        )

    @dj_hx_action("post")
    def step_two(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/step_two.html",
            {
                "container_id": self.container_id,
            },
        )

    @dj_hx_action("post")
    def step_three(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/step_three.html",
            {
                "container_id": self.container_id,
            },
        )
