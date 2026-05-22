"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..db import init_db
from . import analytics, bonus, categories, intelligence, price_history, products, raw_json, stats, viz

def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title="Grocery Data Lake",
        description="Albert Heijn product catalog API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    # Serve React SPA dashboard (new v2)
    dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard"

    @app.get("/dashboard/{path:path}")
    async def serve_dashboard_path(path: str):
        """Serve dashboard static files or fall back to index.html for SPA routing."""
        full_path = dashboard_dir / path
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        # SPA: unknown paths fall back to index.html for client-side routing
        return FileResponse(dashboard_dir / "index.html")

    @app.get("/dashboard")
    async def serve_dashboard_root():
        return FileResponse(dashboard_dir / "index.html")

    # Legacy dashboard (intelligence.html)
    @app.get("/intelligence")
    async def serve_legacy_intelligence():
        intel_path = dashboard_dir / "intelligence.html"
        if intel_path.exists():
            return FileResponse(intel_path)
        return FileResponse(dashboard_dir / "index.html")

    return app
