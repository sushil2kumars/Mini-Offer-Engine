import json

from django.conf import settings


class WebpackManifestNotFoundError(Exception):
    pass


def get_webpack_manifest(filename=None, is_css=False):
    if not filename:
        default_filename = "manifest.css.json" if is_css else "manifest.json"
        path = settings.WEBPACK_BUILD_DIR / default_filename
    else:
        path = settings.WEBPACK_BUILD_DIR / filename
    if not path.is_file():
        raise WebpackManifestNotFoundError

    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)

    return manifest
