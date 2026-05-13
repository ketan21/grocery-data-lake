"""FastAPI database dependencies.

This module keeps a small compatibility surface for API routers that expect
``grocery.database.get_db`` while the application stores its SQLAlchemy setup
in ``grocery.db``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from .db import get_session


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for FastAPI dependencies."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
