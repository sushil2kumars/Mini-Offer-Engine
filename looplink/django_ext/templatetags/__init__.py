from django import template
from django.conf import settings
from django.template import TemplateSyntaxError

register = template.Library()


@register.filter
def webpack_js_bundles(entry_name):
    return _get_webpack_bundles(entry_name)


@register.filter
def webpack_css_bundles(entry_name):
    return _get_webpack_bundles(entry_name, is_css=True)


def _get_webpack_bundles(entry_name, is_css=False):
    """
    Get the webpack bundles for a given entry name. This is used to
    include the correct javascript and css files in the template.

    :param entry_name: The name of the entry point in the webpack manifest.
    :param is_css: Whether to get the css bundles or not.
    :return: A list of the bundles for the given entry name.

    :raises TemplateSyntaxError: If the webpack manifest is not found or
        if the entry name is not found in the manifest.
    :raises WebpackManifestNotFoundError: If the webpack manifest is not found.
    """
    from looplink.django_ext.manifest import WebpackManifestNotFoundError, get_webpack_manifest

    try:
        manifest = get_webpack_manifest(is_css=is_css)
        webpack_folder = settings.WEBPACK_BUILT_ASSETS_FOLDER
    except WebpackManifestNotFoundError:
        # If we're in tests, the manifest genuinely may not be available,
        # as it's only generated for the test job that includes javascript.
        if settings.UNIT_TESTING:
            return []

        raise TemplateSyntaxError(
            f"No webpack manifest found!\n"
            f"'{entry_name}' will not load correctly.\n\n"
            f"Did you run `yarn dev` or `yarn build`?\n\n\n"
        )

    bundles = manifest.get(entry_name, [])
    if not bundles:
        webpack_error = (
            f"No webpack manifest entry found for '{entry_name}'.\n\n"
            f"Is this a newly added entry point?\n"
            f"Did you try restarting `npm run dev`?\n\n\n"
        )
        raise TemplateSyntaxError(webpack_error)
    return [f"{webpack_folder}/{bundle}" for bundle in bundles]
