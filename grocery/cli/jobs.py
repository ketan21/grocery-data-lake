"""Operational job commands."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from ..analytics import compute_price_metrics
from ..client import AHClient
from ..config import DB_PATH
from ..db import get_session, init_db
from ..health import run_quality_checks
from ..intelligence import compute_all_intelligence
from ..scraper import scrape_full_catalog
from ..serving import refresh_serving_metrics
from ..unit_price import normalize_unit_prices

app = typer.Typer(add_completion=False)
console = Console()


def create_database_backup(db_path: Path | None = None) -> Path | None:
    """Create a timestamped backup of the SQLite database and sidecar files."""
    db_path = db_path or DB_PATH
    if not db_path.exists():
        return None

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}-{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            shutil.copy2(sidecar, Path(f"{backup_path}{suffix}"))
    return backup_path


def restore_database_backup(backup_path: Path, db_path: Path | None = None) -> None:
    """Restore the SQLite database from a backup created by daily-snapshot."""
    db_path = db_path or DB_PATH
    shutil.copy2(backup_path, db_path)
    for suffix in ("-wal", "-shm"):
        backup_sidecar = Path(f"{backup_path}{suffix}")
        live_sidecar = Path(f"{db_path}{suffix}")
        if backup_sidecar.exists():
            shutil.copy2(backup_sidecar, live_sidecar)
        elif live_sidecar.exists():
            live_sidecar.unlink()


def _rebuild_derived_tables(session) -> dict:
    unit_prices = normalize_unit_prices(session)
    price_metrics = compute_price_metrics(session)
    serving_metrics = refresh_serving_metrics(session)
    session.commit()
    return {
        "unitPrices": unit_prices,
        "priceMetrics": price_metrics,
        **serving_metrics,
    }


@app.command("rebuild-derived")
def rebuild_derived():
    """Rebuild deterministic derived and serving tables from stored data."""
    init_db()
    session = get_session()
    result = _rebuild_derived_tables(session)

    console.print("[green]Rebuilt derived tables.[/]")
    console.print(f"  Unit prices: {result['unitPrices']}")
    console.print(f"  Price metrics: {result['priceMetrics']}")
    console.print(f"  Category serving metrics: {result['categoryMetrics']}")
    console.print(f"  Brand serving metrics: {result['brandMetrics']}")
    console.print(f"  Bonus serving metrics: {result['bonusMetrics']}")


@app.command("daily-snapshot")
def daily_snapshot(
    details: bool = typer.Option(False, "--details/--no-details", help="Fetch detail enrichment during scrape"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Only rebuild derived/serving tables and run checks"),
    fail_on_quality: bool = typer.Option(False, "--fail-on-quality", help="Exit nonzero if any quality check fails"),
    no_restore: bool = typer.Option(False, "--no-restore", help="Do not restore the pre-run backup if scrape/checks fail"),
):
    """Run the daily scrape, rebuild, and health-check workflow safely."""
    init_db()
    backup_path = None
    if not skip_scrape:
        backup_path = create_database_backup()
        if backup_path:
            console.print(f"[dim]Created pre-run database backup: {backup_path}[/]")

    session = None
    try:
        if skip_scrape:
            console.print("[yellow]Skipping scrape; rebuilding from existing local data.[/]")
        else:
            console.print("[bold]Running full catalog scrape...[/]")
            total = scrape_full_catalog(AHClient(), fetch_details=details, record_prices=True)
            console.print(f"[green]Scrape completed: {total} products processed.[/]")

        session = get_session()
        result = _rebuild_derived_tables(session)
        checks = run_quality_checks(session)
        failed_checks = [check for check in checks if not check.passed]
        if failed_checks:
            raise RuntimeError(
                "quality checks failed: "
                + ", ".join(check.name for check in failed_checks)
            )
    except Exception as exc:
        if session is not None:
            session.close()
        if backup_path and not no_restore:
            restore_database_backup(backup_path)
            console.print(f"[red]Daily snapshot failed; restored database backup: {backup_path}[/]")
        else:
            console.print("[red]Daily snapshot failed; no database restore was performed.[/]")
        console.print(f"[red]Failure reason: {exc}[/]")
        raise typer.Exit(1)

    console.print("[green]Daily snapshot pipeline completed.[/]")
    console.print(f"  Unit prices: {result['unitPrices']}")
    console.print(f"  Price metrics: {result['priceMetrics']}")
    console.print(f"  Category serving metrics: {result['categoryMetrics']}")
    console.print(f"  Brand serving metrics: {result['brandMetrics']}")
    console.print(f"  Bonus serving metrics: {result['bonusMetrics']}")
    console.print("\n[bold]Quality checks:[/]")
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        console.print(f"  {marker} {check.name}: {check.value} ({check.message})")

    if fail_on_quality and any(not check.passed for check in checks):
        raise typer.Exit(1)
