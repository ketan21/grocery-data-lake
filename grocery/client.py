"""HTTP client with rate limiting, retries, and token refresh."""

from __future__ import annotations

import time
import uuid

import httpx

from . import config
from .auth import auth_headers, get_token
from .models import Category, Product


class AHClient:
    """Albert Heijn API client."""

    def __init__(self, search_delay: float = config.SEARCH_DELAY,
                 detail_delay: float = config.DETAIL_DELAY):
        self.search_delay = search_delay
        self.detail_delay = detail_delay
        self._last_search_time = 0.0
        self._last_detail_time = 0.0

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

    def get_categories(self) -> list[Category]:
        """Fetch 28 top-level categories."""
        self._rate_limit("search")
        resp = httpx.get(config.CATEGORIES_ENDPOINT, headers=self._search_headers(), timeout=15)
        resp.raise_for_status()
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

        resp = httpx.get(config.SEARCH_ENDPOINT, params=params,
                         headers=self._search_headers(), timeout=30)
        resp.raise_for_status()
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

        resp = httpx.get(config.SEARCH_ENDPOINT, params=params,
                         headers=self._search_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        products = [Product(**p) for p in data.get("products", [])]
        return products, data

    def bulk_lookup(self, webshop_ids: list[int]) -> list[Product]:
        """Look up products by webshopId (returns only found products)."""
        self._rate_limit("search")
        ids_str = ",".join(str(i) for i in webshop_ids)
        resp = httpx.get(
            config.BULK_LOOKUP_ENDPOINT,
            params={"ids": ids_str},
            headers=self._search_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return [Product(**p) for p in resp.json()]

    def get_product_detail(self, webshop_id: int) -> dict:
        """Get full product detail (nutrition, allergens, properties)."""
        self._rate_limit("detail")
        url = config.DETAIL_ENDPOINT.format(webshopId=webshop_id)
        resp = httpx.get(url, headers=self._search_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_bonus_metadata(self) -> dict:
        """Get bonus period metadata (weekly folders, dates, categories)."""
        self._rate_limit("search")
        resp = httpx.get(config.BONUS_METADATA_ENDPOINT,
                         headers=self._search_headers(), timeout=15)
        resp.raise_for_status()
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
        resp = httpx.get(url, params=params, headers=self._search_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()
