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


def _m004_add_price_history_dedupe_index(conn: sqlite3.Connection) -> None:
    """Add unique index on price_history(product_id, scrape_run_id) to prevent duplicates (v4)."""
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_price_history_product_run "
            "ON price_history(product_id, scrape_run_id)"
        )
        conn.commit()
    except Exception:
        pass


def _m005_add_unit_prices_and_price_metrics(conn: sqlite3.Connection) -> None:
    """Create normalized unit price and price metrics tables (v5)."""
    try:
        conn.execute("ALTER TABLE products ADD COLUMN unit_price_description VARCHAR(100)")
    except Exception:
        pass

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS unit_prices (
            id                             INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id                     INTEGER NOT NULL,
            normalized_price_eur_per_unit  FLOAT NOT NULL,
            base_unit                      VARCHAR(20) NOT NULL,
            original_description           VARCHAR(100) NOT NULL,
            raw_quantity                   FLOAT NOT NULL,
            created_at                     DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at                     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products (webshop_id)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_unit_prices_product "
        "ON unit_prices(product_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_unit_prices_unit_price "
        "ON unit_prices(base_unit, normalized_price_eur_per_unit)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_metrics (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id            INTEGER NOT NULL,
            cheapest_price        FLOAT,
            cheapest_date         DATETIME,
            most_expensive_price  FLOAT,
            most_expensive_date   DATETIME,
            avg_price             FLOAT,
            price_volatility      FLOAT,
            total_changes         INTEGER DEFAULT 0,
            first_seen            DATETIME,
            last_updated          DATETIME,
            FOREIGN KEY(product_id) REFERENCES products (webshop_id)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_price_metrics_product "
        "ON price_metrics(product_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_metrics_cheapest "
        "ON price_metrics(cheapest_price)"
    )
    conn.commit()


def _m006_add_dashboard_serving_tables(conn: sqlite3.Connection) -> None:
    """Create materialized dashboard serving tables (v6)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_category_metrics (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            category                 VARCHAR(255) NOT NULL,
            avg_price_change_pct     FLOAT,
            median_price_change_pct  FLOAT,
            products_with_increases  INTEGER DEFAULT 0,
            products_with_decreases  INTEGER DEFAULT 0,
            products_unchanged       INTEGER DEFAULT 0,
            total_products_tracked   INTEGER DEFAULT 0,
            computed_at              DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_dashboard_category_metrics_category "
        "ON dashboard_category_metrics(category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_dashboard_category_metrics_avg_change "
        "ON dashboard_category_metrics(avg_price_change_pct)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_brand_metrics (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            brand                    VARCHAR(255) NOT NULL,
            avg_price_change_pct     FLOAT,
            products_with_increases  INTEGER DEFAULT 0,
            products_with_decreases  INTEGER DEFAULT 0,
            products_unchanged       INTEGER DEFAULT 0,
            total_products_tracked   INTEGER DEFAULT 0,
            computed_at              DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_dashboard_brand_metrics_brand "
        "ON dashboard_brand_metrics(brand)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_dashboard_brand_metrics_avg_change "
        "ON dashboard_brand_metrics(avg_price_change_pct)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_bonus_metrics (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            group_by                 VARCHAR(20) NOT NULL,
            group_key                VARCHAR(255) NOT NULL,
            product_count            INTEGER DEFAULT 0,
            bonus_count              INTEGER DEFAULT 0,
            bonus_share_pct          FLOAT,
            avg_discount_depth_pct   FLOAT,
            max_discount_depth_pct   FLOAT,
            computed_at              DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_dashboard_bonus_metrics_group "
        "ON dashboard_bonus_metrics(group_by, group_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_dashboard_bonus_metrics_bonus_count "
        "ON dashboard_bonus_metrics(bonus_count)"
    )
    conn.commit()


def _m007_add_category_price_rankings(conn: sqlite3.Connection) -> None:
    """Create analytics_category_price_rankings table (v7)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_category_price_rankings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            main_category       VARCHAR(255) NOT NULL,
            sub_category        VARCHAR(255),
            ranking_type        VARCHAR(50) NOT NULL,
            product_id          INTEGER NOT NULL,
            product_title       VARCHAR(500),
            brand               VARCHAR(255),
            current_price       FLOAT,
            unit_price          FLOAT,
            base_unit           VARCHAR(20),
            rank                INTEGER NOT NULL,
            product_count       INTEGER DEFAULT 0,
            computed_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id       INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_cat_rank_type "
        "ON analytics_category_price_rankings(ranking_type, main_category, rank)"
    )
    conn.commit()


def _m008_add_deal_quality_scores(conn: sqlite3.Connection) -> None:
    """Create analytics_deal_quality_scores table (v8)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_deal_quality_scores (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id              INTEGER NOT NULL,
            current_price           FLOAT,
            price_before_bonus      FLOAT,
            discount_pct            FLOAT,
            avg_price               FLOAT,
            historical_low_price    FLOAT,
            current_vs_avg_pct      FLOAT,
            current_vs_low_pct      FLOAT,
            price_volatility        FLOAT,
            deal_score              FLOAT,
            deal_label              VARCHAR(50),
            computed_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id           INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_deal_score "
        "ON analytics_deal_quality_scores(deal_score DESC)"
    )
    conn.commit()


def _m009_add_nutrition_scores(conn: sqlite3.Connection) -> None:
    """Create analytics_nutrition_scores table (v9)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_nutrition_scores (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id                  INTEGER NOT NULL,
            calories_per_100g           FLOAT,
            sugar_per_100g              FLOAT,
            salt_per_100g               FLOAT,
            saturated_fat_per_100g      FLOAT,
            protein_per_100g            FLOAT,
            fiber_per_100g              FLOAT,
            nutriscore                  VARCHAR(10),
            health_score                FLOAT,
            protein_per_euro            FLOAT,
            fiber_per_euro              FLOAT,
            sugar_risk_level            VARCHAR(20),
            salt_risk_level             VARCHAR(20),
            saturated_fat_risk_level    VARCHAR(20),
            computed_at                 DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id               INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_nutr_health_score "
        "ON analytics_nutrition_scores(health_score DESC)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_nutr_product "
        "ON analytics_nutrition_scores(product_id)"
    )
    conn.commit()


def _m010_add_health_value_rankings(conn: sqlite3.Connection) -> None:
    """Create analytics_health_value_rankings table (v10)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_health_value_rankings (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id              INTEGER NOT NULL,
            main_category           VARCHAR(255),
            sub_category            VARCHAR(255),
            current_price           FLOAT,
            unit_price              FLOAT,
            health_score            FLOAT,
            health_value_score      FLOAT,
            protein_per_euro        FLOAT,
            fiber_per_euro          FLOAT,
            rank_in_category        INTEGER,
            rank_in_subcategory     INTEGER,
            computed_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id           INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_hv_rank_cat "
        "ON analytics_health_value_rankings(main_category, rank_in_category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_hv_score "
        "ON analytics_health_value_rankings(health_value_score DESC)"
    )
    conn.commit()


def _m011_add_product_promotion_frequency(conn: sqlite3.Connection) -> None:
    """Create analytics_product_promotion_frequency table (v11)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_product_promotion_frequency (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id                  INTEGER NOT NULL,
            total_observations          INTEGER DEFAULT 0,
            bonus_observations          INTEGER DEFAULT 0,
            bonus_frequency_pct         FLOAT,
            avg_discount_pct            FLOAT,
            max_discount_pct            FLOAT,
            latest_bonus_start_date     VARCHAR(20),
            latest_bonus_end_date       VARCHAR(20),
            computed_at                 DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id               INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_promo_freq_product "
        "ON analytics_product_promotion_frequency(product_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_promo_freq_bonus_pct "
        "ON analytics_product_promotion_frequency(bonus_frequency_pct DESC)"
    )
    conn.commit()


def _m012_add_ingredient_flags(conn: sqlite3.Connection) -> None:
    """Create analytics_ingredient_flags table (v12)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_ingredient_flags (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id                INTEGER NOT NULL,
            ingredient_count          INTEGER DEFAULT 0,
            contains_added_sugar      BOOLEAN DEFAULT 0,
            contains_palm_oil         BOOLEAN DEFAULT 0,
            contains_sweeteners       BOOLEAN DEFAULT 0,
            contains_preservatives    BOOLEAN DEFAULT 0,
            contains_emulsifiers      BOOLEAN DEFAULT 0,
            contains_colourants       BOOLEAN DEFAULT 0,
            contains_seed_oils        BOOLEAN DEFAULT 0,
            contains_caffeine         BOOLEAN DEFAULT 0,
            possible_vegan            BOOLEAN DEFAULT 0,
            possible_vegetarian       BOOLEAN DEFAULT 0,
            clean_label_score         FLOAT,
            ultra_processed_score     FLOAT,
            matched_terms_json        TEXT,
            computed_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id             INTEGER
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_ingr_flags_product "
        "ON analytics_ingredient_flags(product_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_ingr_clean_label "
        "ON analytics_ingredient_flags(clean_label_score DESC)"
    )
    conn.commit()


def _m013_add_allergen_summary(conn: sqlite3.Connection) -> None:
    """Create analytics_allergen_summary table (v13)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_allergen_summary (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id              INTEGER NOT NULL,
            contains_gluten         BOOLEAN DEFAULT 0,
            contains_milk           BOOLEAN DEFAULT 0,
            contains_nuts           BOOLEAN DEFAULT 0,
            contains_peanuts        BOOLEAN DEFAULT 0,
            contains_soy            BOOLEAN DEFAULT 0,
            contains_egg            BOOLEAN DEFAULT 0,
            contains_fish           BOOLEAN DEFAULT 0,
            contains_shellfish      BOOLEAN DEFAULT 0,
            may_contain_count       INTEGER DEFAULT 0,
            contains_count          INTEGER DEFAULT 0,
            allergen_risk_score     FLOAT,
            computed_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id           INTEGER
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_allergen_product "
        "ON analytics_allergen_summary(product_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_allergen_risk "
        "ON analytics_allergen_summary(allergen_risk_score DESC)"
    )
    conn.commit()


def _m014_add_product_alternatives(conn: sqlite3.Connection) -> None:
    """Create analytics_product_alternatives table (v14)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_product_alternatives (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id                INTEGER NOT NULL,
            alternative_product_id    INTEGER NOT NULL,
            alternative_type          VARCHAR(50) NOT NULL,
            price_saving_pct          FLOAT,
            unit_price_saving_pct     FLOAT,
            health_score_delta        FLOAT,
            confidence                FLOAT,
            explanation               TEXT,
            computed_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id             INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_alt_product_type "
        "ON analytics_product_alternatives(product_id, alternative_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_alt_confidence "
        "ON analytics_product_alternatives(confidence DESC)"
    )
    conn.commit()


def _m015_add_basket_tables(conn: sqlite3.Connection) -> None:
    """Create basket intelligence tables (v15)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS basket_definitions (
            basket_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            basket_name   VARCHAR(255) NOT NULL,
            description   TEXT,
            active        BOOLEAN DEFAULT 1,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS basket_items (
            basket_item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            basket_id         INTEGER NOT NULL,
            main_category     VARCHAR(255),
            sub_category      VARCHAR(255),
            product_rule      VARCHAR(500),
            quantity          INTEGER DEFAULT 1,
            preferred_product_id INTEGER,
            FOREIGN KEY(basket_id) REFERENCES basket_definitions(basket_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_basket_items_basket "
        "ON basket_items(basket_id)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS basket_snapshots (
            basket_snapshot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            basket_id             INTEGER NOT NULL,
            snapshot_date         DATE NOT NULL,
            total_current_price   FLOAT,
            total_regular_price   FLOAT,
            bonus_savings         FLOAT,
            item_count            INTEGER DEFAULT 0,
            computed_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id         INTEGER,
            FOREIGN KEY(basket_id) REFERENCES basket_definitions(basket_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_basket_snapshots_date "
        "ON basket_snapshots(basket_id, snapshot_date)"
    )
    conn.commit()


def _m016_add_brand_intelligence(conn: sqlite3.Connection) -> None:
    """Create analytics_brand_intelligence table (v16)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_brand_intelligence (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            brand                   VARCHAR(255) NOT NULL,
            product_count           INTEGER DEFAULT 0,
            category_count          INTEGER DEFAULT 0,
            avg_price               FLOAT,
            avg_unit_price          FLOAT,
            avg_health_score        FLOAT,
            bonus_share_pct         FLOAT,
            avg_discount_pct        FLOAT,
            price_volatility        FLOAT,
            private_label_candidate BOOLEAN DEFAULT 0,
            computed_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_run_id           INTEGER
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_brand_intel_brand "
        "ON analytics_brand_intelligence(brand)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_brand_intel_avg_price "
        "ON analytics_brand_intelligence(avg_price)"
    )
    conn.commit()


MIGRATIONS: list[tuple[int, str, callable]] = [
    (1, "add raw_json.sub_source column", _m001_add_raw_json_sub_source),
    (2, "add product extra detail columns", _m002_add_product_extra_columns),
    (3, "allergen level normalization marker", _m003_add_allergen_level_column),
    (4, "add price_history dedupe index", _m004_add_price_history_dedupe_index),
    (5, "add unit prices and price metrics", _m005_add_unit_prices_and_price_metrics),
    (6, "add dashboard serving metric tables", _m006_add_dashboard_serving_tables),
    (7, "add category price rankings", _m007_add_category_price_rankings),
    (8, "add deal quality scores", _m008_add_deal_quality_scores),
    (9, "add nutrition scores", _m009_add_nutrition_scores),
    (10, "add health value rankings", _m010_add_health_value_rankings),
    (11, "add product promotion frequency", _m011_add_product_promotion_frequency),
    (12, "add ingredient flags", _m012_add_ingredient_flags),
    (13, "add allergen summary", _m013_add_allergen_summary),
    (14, "add product alternatives", _m014_add_product_alternatives),
    (15, "add basket intelligence tables", _m015_add_basket_tables),
    (16, "add brand intelligence", _m016_add_brand_intelligence),
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
