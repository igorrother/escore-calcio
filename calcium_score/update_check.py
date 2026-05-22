"""Check GitHub Releases for a newer version of the app.

Pure stdlib (urllib + threading). No Qt imports here — UI code wires the
result into a dialog. Network failures are returned as ``None`` so callers
can stay silent in the background-check case.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from . import __version__

log = logging.getLogger(__name__)

GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/igorrother/escore-calcio/releases/latest"
)
RELEASES_PAGE_URL = "https://github.com/igorrother/escore-calcio/releases"
USER_AGENT = f"escore-calcio/{__version__} (+{RELEASES_PAGE_URL})"
REQUEST_TIMEOUT_SECONDS = 6.0


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    release_url: str


def parse_version(text: str) -> tuple[int, ...] | None:
    """Parse a version string like ``v1.2``, ``1.2.3``, ``v1.2.3-beta`` into a
    tuple of ints. Trailing non-numeric suffixes (pre-release tags) are dropped.
    Returns ``None`` if no numeric components are found.
    """
    if not text:
        return None
    cleaned = text.strip().lstrip("vV")
    # Keep leading dotted-numeric chunk only: "1.2.3-beta+meta" -> "1.2.3"
    m = re.match(r"^(\d+(?:\.\d+)*)", cleaned)
    if not m:
        return None
    parts = m.group(1).split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def is_newer_version(latest: str, current: str) -> bool:
    """Return True iff ``latest`` is strictly greater than ``current``.

    Unparseable inputs return False — we'd rather miss an update than nag
    the user about a bogus tag.
    """
    lv = parse_version(latest)
    cv = parse_version(current)
    if lv is None or cv is None:
        return False
    # Pad with zeros so (1, 1) and (1, 1, 0) compare equal.
    n = max(len(lv), len(cv))
    lv_padded = lv + (0,) * (n - len(lv))
    cv_padded = cv + (0,) * (n - len(cv))
    return lv_padded > cv_padded


def parse_release_payload(payload: dict) -> UpdateInfo | None:
    """Extract version + URL from a GitHub /releases/latest JSON payload."""
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    url = payload.get("html_url")
    if not isinstance(url, str) or not url:
        url = RELEASES_PAGE_URL
    return UpdateInfo(latest_version=tag, release_url=url)


def fetch_latest_release(
    url: str = GITHUB_LATEST_RELEASE_URL,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> UpdateInfo | None:
    """Query GitHub for the latest release. Returns ``None`` on any failure."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.info("update check: network error: %s", exc)
        return None

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        log.info("update check: bad JSON: %s", exc)
        return None
    if not isinstance(payload, dict):
        return None
    return parse_release_payload(payload)


def fetch_latest_release_async(
    callback: Callable[[UpdateInfo | None], None],
) -> threading.Thread:
    """Run :func:`fetch_latest_release` on a background thread and pass
    its result (an ``UpdateInfo`` or ``None`` on any failure) to
    ``callback`` on that thread. Qt callers should marshal back to the GUI
    thread via a signal — touching widgets from the worker is undefined.
    """
    def _run() -> None:
        try:
            result = fetch_latest_release()
        except Exception:
            log.exception("update check: unexpected error")
            result = None
        try:
            callback(result)
        except Exception:
            log.exception("update check: callback raised")

    thread = threading.Thread(target=_run, name="update-check", daemon=True)
    thread.start()
    return thread
