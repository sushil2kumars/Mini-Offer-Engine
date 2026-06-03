"""Template views for the base layout and HTMX interaction demo."""

from __future__ import annotations

from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import TemplateView

from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action
from looplink.offers.config import load_offers
from looplink.transactions.models import AppliedOffer, Transaction


def default(request):
    """Render the default landing page with navigation URLs injected."""
    return render(
        request,
        "base/default.html",
        {
            "htmx_example_url": reverse(HtmxExampleView.urlname),
            "stats_url": reverse("stats_portal"),
            "shoppers_url": reverse("shoppers_search"),
        },
    )


class HtmxExampleView(DjangoHtmxActionMixin, TemplateView):
    """Multi-step HTMX interaction demo used to validate the action dispatch layer."""

    template_name = "base/htmx_example.html"
    urlname = "base_htmx_example"
    container_id = "main-htmx-content"

    @dj_hx_action("get")
    def initial_state(self, request, *args, **kwargs):
        """Return the initial step partial."""
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/initial_state.html",
            {"container_id": self.container_id},
        )

    @dj_hx_action("post")
    def step_two(self, request, *args, **kwargs):
        """Return the second-step partial."""
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/step_two.html",
            {"container_id": self.container_id},
        )

    @dj_hx_action("post")
    def step_three(self, request, *args, **kwargs):
        """Return the third-step partial."""
        return self.render_htmx_partial_response(
            request,
            "base/partials/htmx_example/step_three.html",
            {"container_id": self.container_id},
        )


class TransactionTraceView(TemplateView):
    """Debug page showing raw transaction data, applied offers, and final amounts."""
    template_name = "base/transaction_trace.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        transaction_id = kwargs["transaction_id"]
        tx = get_object_or_404(Transaction, transaction_id=transaction_id)
        applied_offers = list(tx.applied_offers.all())
        all_offers = load_offers()
        applied_ids = {o.offer_id for o in applied_offers}
        non_applied_offers = [o for o in all_offers if o["offer_id"] not in applied_ids]
        context["transaction"] = tx
        context["applied_offers"] = applied_offers
        context["non_applied_offers"] = non_applied_offers
        context["all_offer_count"] = len(all_offers)
        return context
