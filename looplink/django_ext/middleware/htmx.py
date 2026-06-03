class HtmxActionMiddleware:
    """
    Middleware to remove the HTMX action fragment from the request.

    This is necessary because using dj-hx-action adds the query parameter
    to the request URL, which is not needed in the view.

    IMPORTANT:
    We need this fragment to be in place to force browsers to cache the partial responses
    separately from the main view response. Otherwise, navigation with the browser's
    back/forward buttons will not work as expected and result in unstyled, javascript-less
    partial template responses.

    It becomes a mess without this middleware and without the fragment in place.

    ADDITIONAL BENEFITS:
    - Makes the request URL cleaner and easier to read in logs
    """

    _FRAG = "_dj-hx-action"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._FRAG in request.GET:
            q = request.GET.copy()
            q.pop(self._FRAG, None)
            request.GET = q
        return self.get_response(request)
