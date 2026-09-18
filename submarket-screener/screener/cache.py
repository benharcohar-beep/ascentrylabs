"""On-disk HTTP cache.

Everything the screener downloads is written to data/cache/ and never fetched
again unless the cache entry is older than its TTL or --refresh is passed.
That is what makes the interview demo work with the wifi off.

Each cache entry has a sidecar .meta.json recording the URL, the HTTP status,
the byte count and the UTC timestamp of the download, so the workbook can say
exactly when every figure was pulled.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

USER_AGENT = (
    "submarket-screener/0.1 (public-data research tool; contact via repository owner)"
)


class FetchError(RuntimeError):
    """Raised when a download fails. Callers turn this into a MISSING cell."""


class MissingCredential(RuntimeError):
    """Raised when a source needs a free API key that is not configured."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CachedResponse:
    body: bytes
    retrieved_at: str
    url: str
    from_cache: bool

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class Cache:
    def __init__(self, root: Path, *, refresh: bool = False, offline: bool = False,
                 request_timeout: int = 60, polite_delay: float = 0.4) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.offline = offline
        self.request_timeout = request_timeout
        self.polite_delay = polite_delay
        self._last_request_at = 0.0

    # ------------------------------------------------------------------ paths
    def _entry_paths(self, key: str) -> tuple[Path, Path]:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in key)[:120]
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        stem = f"{safe}__{digest}"
        return self.root / f"{stem}.bin", self.root / f"{stem}.meta.json"

    def forget(self, key: str) -> bool:
        """Delete a cache entry.

        Needed because some APIs answer an error with HTTP 200 and a body. The
        Census API returns an HTML page titled "Invalid Key" that way, and
        without this the bad page is cached and replayed for the whole TTL, so
        fixing the key changes nothing until the cache expires or someone runs
        with --refresh. A caller that can tell the body is not real data calls
        this before raising.
        """
        body_path, meta_path = self._entry_paths(key)
        removed = False
        for path in (body_path, meta_path):
            try:
                path.unlink()
                removed = True
            except FileNotFoundError:
                pass
        return removed

    def cached_entries(self) -> list[dict]:
        out = []
        for meta_path in sorted(self.root.glob("*.meta.json")):
            try:
                out.append(json.loads(meta_path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    # ------------------------------------------------------------------ fetch
    def get(
        self,
        url: str,
        *,
        key: str,
        params: dict | None = None,
        headers: dict | None = None,
        method: str = "GET",
        json_body: dict | None = None,
        ttl_days: int = 30,
        expect_content_type: str | None = None,
    ) -> CachedResponse:
        """Return the body for `url`, from disk when possible.

        `key` is the stable cache identity. Keep secrets out of it: the API key
        query parameter is deliberately excluded from the key so that rotating
        a key does not invalidate the whole cache, and so that no key is
        written into a filename.
        """
        body_path, meta_path = self._entry_paths(key)

        if body_path.exists() and meta_path.exists() and not self.refresh:
            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                meta = {}
            retrieved_at = meta.get("retrieved_at", "")
            fresh = True
            if ttl_days is not None and retrieved_at:
                try:
                    stamp = datetime.strptime(retrieved_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                    fresh = datetime.now(timezone.utc) - stamp < timedelta(days=ttl_days)
                except ValueError:
                    fresh = True
            if fresh or self.offline:
                return CachedResponse(
                    body_path.read_bytes(), retrieved_at, meta.get("url", url), True
                )

        if self.offline:
            raise FetchError(
                f"offline mode and nothing cached for '{key}'. "
                f"Run the fetch step once with a network connection."
            )

        full_url = url
        if params:
            full_url = f"{url}?{urlencode(params, doseq=True)}"

        # Be a good citizen with free public endpoints.
        gap = time.monotonic() - self._last_request_at
        if gap < self.polite_delay:
            time.sleep(self.polite_delay - gap)

        req_headers = {"User-Agent": USER_AGENT}
        if headers:
            req_headers.update(headers)

        try:
            resp = requests.request(
                method,
                url,
                params=params,
                headers=req_headers,
                json=json_body,
                timeout=self.request_timeout,
            )
        except requests.RequestException as exc:
            raise FetchError(f"{type(exc).__name__} fetching {full_url}: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()

        if resp.status_code != 200:
            snippet = resp.text[:200].replace("\n", " ")
            raise FetchError(
                f"HTTP {resp.status_code} from {full_url} :: {snippet}"
            )

        if expect_content_type and expect_content_type not in resp.headers.get(
            "Content-Type", ""
        ):
            raise FetchError(
                f"unexpected Content-Type "
                f"'{resp.headers.get('Content-Type')}' from {full_url}; "
                f"expected '{expect_content_type}'. The file layout may have moved."
            )

        retrieved_at = _utcnow_iso()
        body_path.write_bytes(resp.content)
        meta_path.write_text(
            json.dumps(
                {
                    "key": key,
                    "url": full_url.split("&key=")[0].split("?key=")[0],
                    "status": resp.status_code,
                    "bytes": len(resp.content),
                    "content_type": resp.headers.get("Content-Type", ""),
                    "retrieved_at": retrieved_at,
                },
                indent=2,
            )
        )
        return CachedResponse(resp.content, retrieved_at, full_url, False)


def require_key(env_name: str, how_to_get: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise MissingCredential(
            f"{env_name} is not set. {how_to_get}\n"
            f"Put it in submarket-screener/.env as {env_name}=..."
        )
    return value
