"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..db import init_db
from . import analytics, bonus, categories, intelligence, price_history, products, raw_json, stats, viz

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
    app.include_router(intelligence.router)
    app.include_router(bonus.router, tags=["bonus"])
    app.include_router(analytics.router)
    app.include_router(viz.router, prefix="/api")

    dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard"
    if dashboard_dir.exists():
        app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")

    return app
