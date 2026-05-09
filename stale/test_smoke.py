"""Smoke tests for Task 1: Foundation — auth, client, config."""

import asyncio
import pytest

from grocery.config import settings
from grocery.auth import auth, AuthManager
from grocery.client import client, GroceryClient


@pytest.mark.asyncio
async def test_settings_defaults():
    """Settings load with sensible defaults."""
    assert settings.api_base == "https://api.ah.nl"
    assert settings.auth_client_id == "appie"
    assert settings.app_header == "AHWEBSHOP"
    assert settings.request_delay == 0.5
    assert settings.workers == 2
    assert settings.max_retries == 3
    assert settings.timeout == 10


@pytest.mark.asyncio
async def test_auth_token_fetch():
    """Anonymous token is fetched and valid."""
    manager = AuthManager()
    token = await manager.get_token()
    assert token is not None
    assert len(token) > 10
    assert manager._token.is_valid


@pytest.mark.asyncio
async def test_auth_token_cached():
    """Second call returns cached token without new request."""
    manager = AuthManager()
    t1 = await manager.get_token()
    t2 = await manager.get_token()
    assert t1 == t2


@pytest.mark.asyncio
async def test_auth_force_refresh():
    """Force refresh invalidates the token."""
    manager = AuthManager()
    t1 = await manager.get_token()
    manager.force_refresh()
    assert manager.access_token is None
    t2 = await manager.get_token()
    assert t2 is not None


@pytest.mark.asyncio
async def test_client_categories():
    """GET categories endpoint returns data."""
    resp = await client.get(
        f"{settings.api_base}/mobile-services/v1/product-shelves/categories"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Each category has id and name
    cat = data[0]
    assert "id" in cat
    assert "name" in cat


@pytest.mark.asyncio
async def test_client_search():
    """GET search endpoint returns products."""
    resp = await client.get(
        f"{settings.api_base}/mobile-services/product/search/v2",
        params={"query": "chocolate", "page": 0, "size": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "page" in data
    assert "products" in data
    products = data["products"]
    assert len(products) > 0
    # Check product structure
    p = products[0]
    assert "webshopId" in p
    assert "title" in p


@pytest.mark.asyncio
async def test_client_product_detail():
    """GET product detail returns full data."""
    # First get a product ID
    resp = await client.get(
        f"{settings.api_base}/mobile-services/product/search/v2",
        params={"query": "chocolate", "page": 0, "size": 1},
    )
    wid = resp.json()["products"][0]["webshopId"]

    # Fetch detail
    resp = await client.get(
        f"{settings.api_base}/mobile-services/product/detail/v4/fir/{wid}"
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert "productCard" in detail
    assert "tradeItem" in detail


@pytest.mark.asyncio
async def test_client_subcategories():
    """GET sub-categories returns nested structure."""
    # Get first category
    resp = await client.get(
        f"{settings.api_base}/mobile-services/v1/product-shelves/categories"
    )
    first_id = resp.json()[0]["id"]

    # Get sub-categories
    resp = await client.get(
        f"{settings.api_base}/mobile-services/v1/product-shelves/categories/{first_id}/sub-categories"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "parent" in data
    # API may return 'children' or 'subCategories' depending on version
    sub_list = data.get("children") or data.get("subCategories", [])
    assert len(sub_list) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
