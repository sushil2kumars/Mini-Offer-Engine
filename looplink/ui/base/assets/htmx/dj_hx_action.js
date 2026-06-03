/**
 * Usage Instructions:
 *
 * 1) In your page's entry point, import HTMX and this module, for example:
 *    import 'htmx.org';
 *    import 'web/htmx/dj_hx_action';
 *
 * 2) Ensure that your class-based view extends the `DjangoHtmxActionMixin`.
 *
 * 3) Apply the `@dj_hx_action()` decorator to the methods you want to expose to
 *    `dj-hx-action` attributes.
 *
 * 4) Reference the decorated method in the `dj-hx-action` attribute alongside
 *    `hx-get`, `hx-post`, or any equivalent HTMX attribute.
 */
document.body.addEventListener('htmx:configRequest', (evt) => {
    // Require that the dj-hx-action attribute is present
    if (evt.detail.elt.hasAttribute('dj-hx-action')) {
        const action = evt.detail.elt.getAttribute('dj-hx-action');
        // insert DJ-HX-Actionin the header to be processed by the `DjangoHtmxActionMixin`
        evt.detail.headers['DJ-HX-Action'] = action;

        // namespace the URL so the browser keys the cache separately
        // this flag will be removed by `HtmxActionMiddleware`
        const url = new URL(evt.detail.path, window.location.origin);
        url.searchParams.set('_dj-hx-action', action);
        evt.detail.path = url.pathname + url.search;
    }
});
