"""ImpactLens CLI entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from impactlens.core.registry import register_all_adapters, registry

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=verbose)],
    )


@click.group()
@click.version_option(version="0.1.0", prog_name="impactlens")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """ImpactLens — impact analysis and selective test execution."""
    _setup_logging(verbose)
    register_all_adapters()
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@main.command()
def languages() -> None:
    """List supported languages."""
    adapters = registry.all()
    if not adapters:
        console.print("[yellow]No adapters registered.[/]")
        return
    console.print("[bold]Supported languages:[/]")
    for a in adapters:
        exts = ", ".join(a.source_extensions)
        console.print(f"  • [cyan]{a.language.value}[/] ({exts})")


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--base", required=True, help="Base git ref (e.g. HEAD~1, main)")
@click.option("--head", default="HEAD", help="Head git ref (default: HEAD)")
def analyze(repo_path: Path, base: str, head: str) -> None:
    """Analyze a repo's test impact between two git refs.

    Day 1: stub — prints configuration and exits. Full pipeline Day 3.
    """
    console.print(f"[bold]Repository:[/] {repo_path}")
    console.print(f"[bold]Base:[/] {base}")
    console.print(f"[bold]Head:[/] {head}")
    console.print()

    adapters = registry.all()
    console.print(f"[green]Registered adapters:[/] {len(adapters)}")
    for a in adapters:
        console.print(f"  • {a.language.value}")

    console.print()
    console.print("[yellow]Pipeline not yet implemented — scheduled for Day 3.[/]")
    sys.exit(0)


if __name__ == "__main__":
    main()