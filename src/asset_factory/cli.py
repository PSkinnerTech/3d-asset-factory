import typer

app = typer.Typer(help="Generate educational 3D asset bundles from science specs.")


@app.command()
def generate(spec_path: str) -> None:
    """Generate a complete asset run from an asset.yaml spec."""
    typer.echo(f"Generation pipeline is not wired yet: {spec_path}")


@app.command()
def qa(run_dir: str) -> None:
    """Run deterministic QA checks against an existing run directory."""
    typer.echo(f"QA pipeline is not wired yet: {run_dir}")


@app.command()
def export(run_dir: str, profile: str = "web") -> None:
    """Rebuild an export profile from an existing run directory."""
    typer.echo(f"Export pipeline is not wired yet: {run_dir} ({profile})")


@app.command()
def review(run_dir: str, port: int = 8765) -> None:
    """Open a local browser review dashboard for an existing run directory."""
    typer.echo(f"Review server is not wired yet: {run_dir} on port {port}")
