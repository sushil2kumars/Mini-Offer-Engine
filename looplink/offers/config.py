"""Offer catalogue loader.

Promotions are stored as a static JSON fixture that is loaded once at process
startup via :func:`functools.cache`. This avoids repeated disk reads on every
request while keeping the offer data outside the database for fast, simple
read access.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

_OFFERS_PATH = Path(__file__).resolve().parent.joinpath("fixtures", "offers.json")


@functools.cache
def load_offers() -> list[dict]:
    """Return the full list of active offer definitions.

    The result is cached process-wide after the first call. Restart the
    process to pick up changes to the underlying JSON fixture.
    """
    return json.loads(_OFFERS_PATH.read_text())["offers"]
