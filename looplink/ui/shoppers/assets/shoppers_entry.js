import "../../../../styles/looplink.css";
import "base/common";

document.addEventListener("htmx:beforeRequest", function (e) {
  var el = e.detail.elt;
  if (!el || el.getAttribute("dj-hx-action") !== "transaction_detail") return;

  var targetId = el.getAttribute("hx-target");
  if (!targetId) return;
  var target = document.querySelector(targetId);
  if (!target) return;

  var indicator = target.querySelector('[id^="tx-indicator-"]');
  if (!indicator) {
    e.preventDefault();
    var txId = target.id.replace("tx-detail-", "");
    target.innerHTML =
      '<div id="tx-indicator-' +
      txId +
      '" class="htmx-request:block hidden text-center py-2 text-sm text-stone-400">Loading details...</div>';
  }
});
