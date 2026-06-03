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
    from looplink.django_ext.js_entry import WebpackManifestNotFoundError, get_webpack_manifest

    try:
        manifest = get_webpack_manifest(is_css=is_css)
        webpack_folder = settings.WEBPACK_BUILT_ASSETS_FOLDER
    except WebpackManifestNotFoundError:
        raise TemplateSyntaxError(
            f"No webpack manifest found!\n"
            f"'{entry_name}' will not load correctly.\n\n"
            f"Did you run `inv npm` / `npm run build` / `npm run watch`?\n\n\n"
        )

    bundles = manifest.get(entry_name, [])
    if not bundles:
        webpack_error = (
            f"No webpack manifest entry found for '{entry_name}'.\n\n"
            f"Is this a newly added entry point?\n"
            f"Did you try restarting `inv npm` / `npm run build` / `npm run watch`?\n\n\n"
        )
        raise TemplateSyntaxError(webpack_error)
    return [f"{webpack_folder}/{bundle}" for bundle in bundles]
