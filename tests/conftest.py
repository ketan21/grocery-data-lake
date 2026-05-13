"""Pytest configuration."""

import os
import sys

import pytest

# Ensure the package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grocery.db import Base, get_engine, get_session, init_db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a temporary in-disk SQLite database with all tables initialized."""
    db_path = tmp_path / "test.db"

    # Monkeypatch the config module so db.py picks up the temp path
    monkeypatch.setattr("grocery.config.DB_PATH", db_path)
    monkeypatch.setattr("grocery.config.DB_DIR", tmp_path)
    # Also patch the db module's imported references
    monkeypatch.setattr("grocery.db.DB_PATH", db_path)
    monkeypatch.setattr("grocery.db.DB_DIR", tmp_path)

    init_db()
    session = get_session()

    yield session

    session.close()
