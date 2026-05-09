"""Additive SQLite migrations for the grocery data lake.

Each migration is a (version, description, fn) tuple. The migration system
tracks applied versions in an `alembic_version` table (lightweight, no
dependency on the alembic package). Migrations are applied in order on
`migrate()` and are idempotent — they use `ALTER TABLE IF NOT EXISTS` or
catch `sqlite3.OperationalError` for already-existing columns.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import DB_PATH


class _MigrationEngine:
    """Minimal migration tracker using a single SQLite table."""

    VERSION_TABLE = "alembic_version"

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._ensure_version_table()

    # ------------------------------------------------------------------
    def _ensure_version_table(self) -> None:
        with self._conn() as c:
            c.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.VERSION_TABLE} (
                    version       INTEGER PRIMARY KEY,
                    description   TEXT    NOT NULL,
                    applied_at    TEXT    NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def applied_versions(self) -> set[int]:
        with self._conn() as c:
            rows = c.execute(
                f"SELECT version FROM {self.VERSION_TABLE}"
            ).fetchall()
        return {r[0] for r in rows}

    def record(self, version: int, description: str) -> None:
        with self._conn() as c:
            c.execute(
                f"INSERT OR IGNORE INTO {self.VERSION_TABLE} (version, description) VALUES (?, ?)",
                (version, description),
            )

    # ------------------------------------------------------------------
    def migrate(self, migrations: list[tuple[int, str, callable]]) -> list[int]:
        """Apply pending migrations in order. Returns list of applied versions."""
        applied = self.applied_versions()
        pending = [(v, desc, fn) for v, desc, fn in migrations if v not in applied]
        if not pending:
            return []

        applied_versions: list[int] = []
        for version, description, fn in pending:
            # Each migration runs against its own connection for safety.
            with self._conn() as conn:
                fn(conn)
            self.record(version, description)
            applied_versions.append(version)

        return applied_versions


# ======================================================================
# Migration definitions
# ======================================================================

def _m001_add_raw_json_sub_source(conn: sqlite3.Connection) -> None:
    """Add raw_json.sub_source column if missing (v1)."""
    try:
        conn.execute("ALTER TABLE raw_json ADD COLUMN sub_source VARCHAR(100)")
        conn.commit()
    except Exception:
        # Already exists or table doesn't exist yet — skip.
        pass


def _m002_add_product_extra_columns(conn: sqlite3.Connection) -> None:
    """Add extra detail columns to products table if missing (v2)."""
    extra_cols = [
        ("ingredients", "TEXT"),
        ("food_name", "VARCHAR(500)"),
        ("product_type", "VARCHAR(255)"),
        ("origin_country", "VARCHAR(100)"),
        ("barcode", "VARCHAR(50)"),
        ("manufacturer", "VARCHAR(255)"),
    ]
    for col_name, col_type in extra_cols:
        try:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass
    conn.commit()


def _m003_add_allergen_level_column(conn: sqlite3.Connection) -> None:
    """Ensure allergens.level column exists (v3).

    The column already exists but was always set to 'CONTAINS'.
    This migration is a no-op placeholder for future level normalization.
    """
    # Column already exists in the schema; this is a marker migration.
    pass


MIGRATIONS: list[tuple[int, str, callable]] = [
    (1, "add raw_json.sub_source column", _m001_add_raw_json_sub_source),
    (2, "add product extra detail columns", _m002_add_product_extra_columns),
    (3, "allergen level normalization marker", _m003_add_allergen_level_column),
]


def migrate(db_path: Path | None = None) -> list[int]:
    """Run all pending additive migrations. Returns list of applied versions."""
    target = Path(db_path) if db_path else DB_PATH
    engine = _MigrationEngine(target)
    return engine.migrate(MIGRATIONS)


def migration_status(db_path: Path | None = None) -> dict:
    """Return migration status: total, applied, pending."""
    target = Path(db_path) if db_path else DB_PATH
    engine = _MigrationEngine(target)
    applied = engine.applied_versions()
    total = len(MIGRATIONS)
    return {
        "total": total,
        "applied": sorted(applied),
        "pending": [v for v, _, _ in MIGRATIONS if v not in applied],
    }
