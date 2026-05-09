"""CLI entry point."""

from __future__ import annotations

import typer

from . import scrape, query, serve, enrich, bonus, jobs

main = typer.Typer(
    name="grocery",
    help="Albert Heijn product data lake",
    add_completion=False,
)

main.add_typer(scrape.app, name="scrape", help="Scrape AH product catalog")
main.add_typer(query.app, name="query", help="Query the local database")
main.add_typer(enrich.app, name="enrich", help="Enrich products with detail data")
main.add_typer(bonus.app, name="bonus", help="Scrape bonus/promotion data")
main.add_typer(serve.app, name="serve", help="Serve the data lake via HTTP API")
main.add_typer(jobs.app, name="jobs", help="Run operational data jobs")


if __name__ == "__main__":
    main()
