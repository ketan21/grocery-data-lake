"""FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from ..db import init_db
from . import products, categories, stats, price_history, raw_json, bonus

def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title="Grocery Data Lake",
        description="Albert Heijn product catalog API",
        version="0.1.0",
    )

    app.include_router(products.router, prefix="/api", tags=["products"])
    app.include_router(categories.router, prefix="/api", tags=["categories"])
    app.include_router(stats.router, prefix="/api", tags=["stats"])
    app.include_router(price_history.router, prefix="/api", tags=["price-history"])
    app.include_router(raw_json.router, tags=["raw-json"])
    app.include_router(bonus.router, tags=["bonus"])

    return app
