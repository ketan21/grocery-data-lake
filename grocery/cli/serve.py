"""Serve commands."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(add_completion=False)


@app.command()
def run_server(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to serve on")] = 8000,
):
    """Start the FastAPI server."""
    import uvicorn
    from ..api.app import create_app

    app = create_app()
    typer.echo(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
