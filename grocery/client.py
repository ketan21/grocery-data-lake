"""HTTP client with rate limiting, retries, and token refresh."""

from __future__ import annotations

import time
import uuid

import httpx

from . import config
from .auth import auth_headers, get_token
from .models import Category, Product

# HTTP status codes that indicate transient failures worth retrying.
TRANSIENT_STATUS_CODES = {401, 408, 429, 500, 502, 503, 504}
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds — backoff: 1, 2, 4…


class AHClient:
    """Albert Heijn API client."""

    def __init__(self, search_delay: float = config.SEARCH_DELAY,
                 detail_delay: float = config.DETAIL_DELAY):
        self.search_delay = search_delay
        self.detail_delay = detail_delay
        self._last_search_time = 0.0
        self._last_detail_time = 0.0
        self._retry_stats = {"retried": 0, "failed_after_retries": 0}

    def _search_headers(self) -> dict:
        h = auth_headers()
        h["x-fraud-detection-installation-id"] = str(uuid.uuid4())
        h["x-correlation-id"] = str(uuid.uuid4())
        return h

    def _rate_limit(self, kind: str) -> None:
        if kind == "search":
            elapsed = time.time() - self._last_search_time
            if elapsed < self.search_delay:
                time.sleep(self.search_delay - elapsed)
            self._last_search_time = time.time()
        elif kind == "detail":
            elapsed = time.time() - self._last_detail_time
            if elapsed < self.detail_delay:
                time.sleep(self.detail_delay - elapsed)
            self._last_detail_time = time.time()

    def _request_with_retry(self, fn, *, max_retries: int = MAX_RETRIES,
                            backoff_base: float = RETRY_BASE_DELAY) -> httpx.Response:
        """Execute *fn*() with exponential backoff for transient HTTP errors.

        Handles 401 (stale token), 429 (rate limit), 408/500/502/503/504
        and httpx timeouts.  On 401 the token is refreshed before retrying.
        """
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = fn()
                if resp.status_code in TRANSIENT_STATUS_CODES:
                    if resp.status_code == 401:
                        # Refresh anonymous token on 401
                        get_token(force=True)
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.TimeoutException,
                    httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = backoff_base * (2 ** attempt)
                    self._retry_stats["retried"] += 1
                    time.sleep(delay)
                continue

        self._retry_stats["failed_after_retries"] += 1
        if isinstance(last_exc, httpx.HTTPStatusError):
            raise last_exc
        raise last_exc  # type: ignore[misc]

    def retry_stats(self) -> dict:
        """Return retry statistics for this client session."""
        return dict(self._retry_stats)

    def get_categories(self) -> list[Category]:
        """Fetch 28 top-level categories."""
        self._rate_limit("search")
        resp = self._request_with_retry(
            lambda: httpx.get(config.CATEGORIES_ENDPOINT,
                              headers=self._search_headers(), timeout=15)
        )
        return [Category(**c) for c in resp.json()]

    def search_products(
        self,
        query: str = "",
        page: int = 0,
        size: int = config.PAGE_SIZE,
        taxonomy_id: int | None = None,
    ) -> list[Product]:
        """Search products by keyword or category."""
        self._rate_limit("search")
        params: dict[str, object] = {"query": query, "page": page, "size": size}
        if taxonomy_id is not None:
            params["taxonomyId"] = taxonomy_id

        resp = self._request_with_retry(
            lambda: httpx.get(config.SEARCH_ENDPOINT, params=params,
                              headers=self._search_headers(), timeout=30)
        )
        data = resp.json()
        return [Product(**p) for p in data.get("products", [])]

    def search_products_raw(
        self,
        query: str = "",
        page: int = 0,
        size: int = config.PAGE_SIZE,
        taxonomy_id: int | None = None,
    ) -> tuple[list[Product], dict]:
        """Search products, returning both parsed Products and raw JSON response.

        Returns:
            (list of Product, raw API response dict)
        """
        self._rate_limit("search")
        params: dict[str, object] = {"query": query, "page": page, "size": size}
        if taxonomy_id is not None:
            params["taxonomyId"] = taxonomy_id

        resp = self._request_with_retry(
            lambda: httpx.get(config.SEARCH_ENDPOINT, params=params,
                              headers=self._search_headers(), timeout=30)
        )
        data = resp.json()
        products = [Product(**p) for p in data.get("products", [])]
        return products, data

    def bulk_lookup(self, webshop_ids: list[int]) -> list[Product]:
        """Look up products by webshopId (returns only found products)."""
        self._rate_limit("search")
        ids_str = ",".join(str(i) for i in webshop_ids)
        resp = self._request_with_retry(
            lambda: httpx.get(
                config.BULK_LOOKUP_ENDPOINT,
                params={"ids": ids_str},
                headers=self._search_headers(),
                timeout=30,
            )
        )
        return [Product(**p) for p in resp.json()]

    def get_product_detail(self, webshop_id: int) -> dict:
        """Get full product detail (nutrition, allergens, properties)."""
        self._rate_limit("detail")
        url = config.DETAIL_ENDPOINT.format(webshopId=webshop_id)
        resp = self._request_with_retry(
            lambda: httpx.get(url, headers=self._search_headers(), timeout=15)
        )
        return resp.json()

    def get_bonus_metadata(self) -> dict:
        """Get bonus period metadata (weekly folders, dates, categories)."""
        self._rate_limit("search")
        resp = self._request_with_retry(
            lambda: httpx.get(config.BONUS_METADATA_ENDPOINT,
                              headers=self._search_headers(), timeout=15)
        )
        return resp.json()

    def get_bonus_section(self, date: str, category: str = None) -> dict:
        """Get bonus/promotion items for a date and optional category.

        Args:
            date: Date string (e.g., "2026-05-04")
            category: Category name (e.g., "Groente, aardappelen"). If None, fetches spotlight.

        Returns:
            Raw bonus section response dict.
        """
        self._rate_limit("search")
        if category:
            url = f"{config.BASE_URL}/mobile-services/bonuspage/v2/section"
            params = {
                "application": config.APPLICATION,
                "date": date,
                "promotionType": "NATIONAL",
                "category": category,
            }
        else:
            url = f"{config.BASE_URL}/mobile-services/bonuspage/v2/section/spotlight"
            params = {
                "application": config.APPLICATION,
                "date": date,
            }
        resp = self._request_with_retry(
            lambda: httpx.get(url, params=params,
                              headers=self._search_headers(), timeout=15)
        )
        return resp.json()
