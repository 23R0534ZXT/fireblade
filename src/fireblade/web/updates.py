"""Is there a newer Kogarasu? The check, and the words that tell the analyst what to run.

A container cannot replace itself, and it should not pretend to: a tool that produces
destruction certificates changes version when someone decides to, not between two queries.
So this module answers one question — "is there a newer release?" — and gives the command
that does the rest.

The answer is cached: the registry is queried at most once per ``TTL``, and a failure is
never reported as "up to date".
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

RELEASES = "https://api.github.com/repos/23R0534ZXT/kogarasu/releases/latest"
REGISTRY = "ghcr.io/23r0534zxt"
HOST_IMAGE = f"{REGISTRY}/kogarasu"
DRIVER_IMAGE = f"{REGISTRY}/kogarasu-driver"
TTL = 6 * 3600
RETRY = 30 * 60
TIMEOUT = 3.0


def version_tuple(text: str) -> tuple:
    """ "0.8.1" ranks before "0.9.0"; anything unreadable ranks lowest."""
    numbers = []
    for part in (text or "").lstrip("v").split("."):
        digits = "".join(char for char in part if char.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers) if numbers else (0,)


def parse(payload: dict) -> dict:
    """The release payload, reduced to what a banner needs."""
    tag = (payload.get("tag_name") or "").strip().lstrip("v")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("The release does not have a stable version tag.")
    return {
        "version": tag,
        "url": (payload.get("html_url") or "").strip(),
        "name": (payload.get("name") or "").strip(),
        "published": (payload.get("published_at") or "").strip(),
    }


def command(edition: str, tag: str) -> list:
    """Pull the release images while preserving the operator's running deployment."""
    tag = tag or "latest"
    case = f"docker pull {HOST_IMAGE}:{tag}"
    if edition == "driver":
        return [f"docker pull {DRIVER_IMAGE}:{tag}", case]
    return [case]


def guidance(edition: str) -> str:
    if edition in {"case", "driver"}:
        return (
            "Recreate the driver with the matching case image, original volume paths, network "
            "and certificate directory. See the upgrade guide in deploy/host/README.md."
        )
    return (
        "After the pull, recreate Host with its existing case and plugin mounts, port and settings. "
        "See the upgrade guide in deploy/host/README.md."
    )


def disabled() -> bool:
    """FIREBLADE_UPDATE_CHECK=off: the service never asks anyone whether a release exists."""
    return os.environ.get("FIREBLADE_UPDATE_CHECK", "").strip().lower() in {
        "0",
        "off",
        "false",
        "no",
    }


class Checker:
    """One cached answer per process, refreshed when it is old enough."""

    def __init__(
        self,
        current: str = "",
        edition: str = "host",
        *,
        fetch=None,
        ttl: float = TTL,
        retry: float = RETRY,
        now=None,
    ):
        self.current = current
        self.edition = edition
        self.fetch = fetch or self._fetch
        self.ttl = ttl
        self.retry = retry
        self.now = now or time.time
        self.lock = threading.Lock()
        self.checked_at = 0.0
        self.latest = ""
        self.url = ""
        self.name = ""
        self.failure = ""

    def _fetch(self) -> dict:
        request = urllib.request.Request(
            RELEASES,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "fireblade-host"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310
            return json.loads(answer.read().decode("utf-8"))

    def version(self) -> str:
        return self.current or "0"

    def available(self) -> bool:
        return bool(self.latest) and version_tuple(self.latest) > version_tuple(self.version())

    def info(self, *, refresh: bool = True) -> dict:
        """The banner's data. A stale answer is refreshed once; a failure keeps the last one."""
        if disabled():
            return {
                "current": self.version(),
                "latest": "",
                "available": False,
                "url": "",
                "name": "",
                "command": [],
                "note": "",
                "checked": "",
                "error": "",
                "disabled": True,
            }
        with self.lock:
            age = self.now() - self.checked_at
            interval = self.retry if self.failure else self.ttl
            due = (self.checked_at == 0) or (age > interval)
            if refresh and due:
                try:
                    release = parse(self.fetch())
                    self.latest = release["version"]
                    self.url = release["url"]
                    self.name = release["name"]
                    self.failure = ""
                except (urllib.error.URLError, ValueError, OSError, KeyError) as exc:
                    # Keep the previous answer, and say why: nobody may read a failed
                    # check as "you are up to date".
                    self.failure = str(exc)
                finally:
                    self.checked_at = self.now()
            return {
                "current": self.version(),
                "latest": self.latest,
                "available": self.available(),
                "url": self.url,
                "name": self.name,
                "command": command(self.edition, self.latest),
                "note": guidance(self.edition),
                "disabled": False,
                "checked": (
                    datetime.fromtimestamp(self.checked_at, UTC).isoformat()
                    if self.checked_at
                    else ""
                ),
                "error": self.failure,
            }
