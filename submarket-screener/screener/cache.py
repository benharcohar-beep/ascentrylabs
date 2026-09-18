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
from contextlib import contextmanager
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
        self._deadline: float | None = None

    # ---------------------------------------------------------------- budget
    @contextmanager
    def budget(self, seconds: float | None, label: str = "this source"):
        """Cap the wall-clock time one source may spend downloading.

        request_timeout does not cover this. It is a per-socket timeout, so a
        download that keeps trickling bytes never trips it, and a source that
        pulls a very large file can hold up a run that is otherwise seconds
        from finishing. One column is never worth that, so the budget turns an
        overrun into a MISSING column with an honest reason attached and lets
        the rest of the screen complete.

        Nested budgets take the earlier deadline, so an inner one can tighten
        an outer one but never extend past it.
        """
        previous = self._deadline
        if seconds is not None:
            proposed = time.monotonic() + seconds
            self._deadline = proposed if previous is None else min(previous, proposed)
        self._budget_label = label
        self._budget_seconds = seconds
        try:
            yield
        finally:
            self._deadline = previous

    def _check_deadline(self, url: str, downloaded: int | None = None) -> None:
        if self._deadline is None or time.monotonic() <= self._deadline:
            return
        so_far = "" if downloaded is None else f" after {downloaded:,} bytes"
        raise FetchError(
            f"{getattr(self, '_budget_label', 'this source')} ran past its "
            f"{getattr(self, '_budget_seconds', '?')} second download budget"
            f"{so_far} on {url}. Nothing was guessed: the columns this source "
            f"fills are reported MISSING and the rest of the screen completed. "
            f"Raise the budget, or run once with a warm cache."
        )

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

        self._check_deadline(full_url)

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
                stream=True,
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

        # Read the body in chunks so the budget can stop a download that is
        # still arriving. Buffering it whole first would defeat the point: the
        # oversized file is exactly the one that needs interrupting.
        chunks: list[bytes] = []
        downloaded = 0
        try:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if not chunk:
                    continue
                chunks.append(chunk)
                downloaded += len(chunk)
                self._check_deadline(full_url, downloaded)
        except requests.RequestException as exc:
            raise FetchError(
                f"{type(exc).__name__} while reading {full_url} after "
                f"{downloaded:,} bytes: {exc}"
            ) from exc
        body = b"".join(chunks)

        if expect_content_type and expect_content_type not in resp.headers.get(
            "Content-Type", ""
        ):
            raise FetchError(
                f"unexpected Content-Type "
                f"'{resp.headers.get('Content-Type')}' from {full_url}; "
                f"expected '{expect_content_type}'. The file layout may have moved."
            )

        retrieved_at = _utcnow_iso()
        body_path.write_bytes(body)
        meta_path.write_text(
            json.dumps(
                {
                    "key": key,
                    "url": full_url.split("&key=")[0].split("?key=")[0],
                    "status": resp.status_code,
                    "bytes": len(body),
                    "content_type": resp.headers.get("Content-Type", ""),
                    "retrieved_at": retrieved_at,
                },
                indent=2,
            )
        )
        return CachedResponse(body, retrieved_at, full_url, False)


def optional_key(env_name: str) -> str:
    """Read a credential that the caller can do without.

    Some hosts serve the same data with or without a key, and only meter you
    differently. The Census API is the case that matters here: it answers
    unauthenticated requests up to a published daily quota per IP address, so
    demanding a key would turn a working screen into no screen at all. Sources
    that genuinely cannot run without a credential keep using require_key.
    """
    return os.environ.get(env_name, "").strip()


def require_key(env_name: str, how_to_get: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise MissingCredential(
            f"{env_name} is not set. {how_to_get}\n"
            f"Put it in submarket-screener/.env as {env_name}=..."
        )
    return value
