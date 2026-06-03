"""Template views for the shopper search and detail portal."""

from __future__ import annotations

from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView

from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action
from looplink.shoppers.models import ShopperProfile, StickerRedemption, get_rewards
from looplink.transactions.models import AppliedOffer, Transaction

_SHOPPER_SEARCH_LIMIT = 20
_TRANSACTION_HISTORY_LIMIT = 50


class ShopperSearchView(TemplateView):
    """Landing page with a live HTMX-powered shopper search."""

    template_name = "shoppers/search.html"

    def get(self, request, *args, **kwargs):
        """Return search results partial for HTMX requests; full page otherwise."""
        if request.htmx:
            q = request.GET.get("q", "").strip()
            latest_store = (
                Transaction.objects.filter(shopper_id=OuterRef("shopper_id"))
                .order_by("-timestamp")
                .values("store_id")[:1]
            )
            shoppers = (
                ShopperProfile.objects.filter(shopper_id__icontains=q).annotate(store_id=Subquery(latest_store))
            )[:_SHOPPER_SEARCH_LIMIT]
            return render(request, "shoppers/partials/search_results.html", {"shoppers": shoppers})
        return super().get(request, *args, **kwargs)


class ShopperDetailView(DjangoHtmxActionMixin, TemplateView):
    """Detail page showing a shopper's balance, transaction history and redemptions."""

    template_name = "shoppers/shopper_detail.html"
    urlname = "shoppers_portal_detail"
    container_id = "shopper-detail-container"

    def get_context_data(self, **kwargs) -> dict:
        """Build context with the shopper, their recent transactions and redemptions."""
        context = super().get_context_data(**kwargs)
        shopper = get_object_or_404(ShopperProfile, shopper_id=kwargs["shopper_id"])
        transactions = (
            Transaction.objects.filter(shopper_id=kwargs["shopper_id"])
            .order_by("-timestamp")[:_TRANSACTION_HISTORY_LIMIT]
        )
        redemptions = StickerRedemption.objects.filter(shopper_id=kwargs["shopper_id"])
        context["shopper"] = shopper
        context["transactions"] = transactions
        context["redemptions"] = redemptions
        context["rewards"] = get_rewards()
        return context

    @dj_hx_action("get")
    def transaction_detail(self, request, *args, **kwargs):
        """Return the applied-offers partial for a single transaction."""
        tx_id = request.GET.get("transaction_id")
        tx = get_object_or_404(Transaction, transaction_id=tx_id)
        offers = AppliedOffer.objects.filter(transaction=tx)
        return self.render_htmx_partial_response(
            request,
            "shoppers/partials/transaction_detail.html",
            {"transaction": tx, "offers": offers},
        )
