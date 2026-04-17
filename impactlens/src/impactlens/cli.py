"""ImpactLens CLI entry point."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

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
    """List all registered language adapters."""
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
@click.option("--json-out", type=click.Path(path_type=Path), default=None, help="Write results as JSON")
def analyze(repo_path: Path, base: str, head: str, json_out: Path | None) -> None:
    """Analyze impact of changes between two git refs in a repository."""
    from impactlens.core.diff import extract_changed_regions

    console.print(f"\n[bold]🎯 ImpactLens Analysis[/]")
    console.print(f"  Repository:  [cyan]{repo_path}[/]")
    console.print(f"  Base ref:    [yellow]{base}[/]")
    console.print(f"  Head ref:    [yellow]{head}[/]")
    console.print()

    # ── Step 1: Detect adapters ──
    adapters = registry.all()
    console.print(f"[green]Registered adapters:[/] {', '.join(a.language.value for a in adapters)}")
    console.print()

    # ── Step 2: Extract diff ──
    console.print("[bold]Step 1/4: Extracting changes...[/]")
    try:
        regions = extract_changed_regions(repo_path, base, head)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    if not regions:
        console.print("[yellow]No changes detected between the given refs.[/]")
        sys.exit(0)

    # Display changes in a table
    table = Table(title="Changed Regions", show_lines=False)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Change", style="yellow", width=10)
    table.add_column("Old Range", justify="center", width=12)
    table.add_column("New Range", justify="center", width=12)

    for r in regions:
        old_str = f"{r.old_range.start}-{r.old_range.end}" if r.old_range else "—"
        new_str = f"{r.new_range.start}-{r.new_range.end}" if r.new_range else "—"
        table.add_row(r.file_path, r.change_type.value, old_str, new_str)

    console.print(table)
    console.print()

    changed_files = sorted(set(r.file_path for r in regions))
    console.print(f"  [bold]{len(regions)}[/] changed regions across [bold]{len(changed_files)}[/] files")
    console.print()

    # ── Step 3: Parse symbols (Day 2 — if adapter supports it) ──
    console.print("[bold]Step 2/4: Parsing symbols...[/]")
    
    # Find which adapter handles the changed files
    from impactlens.core.models import SourceSymbol, CallEdge
    
    all_symbols: list[SourceSymbol] = []
    all_calls: list[CallEdge] = []
    
    for adapter in adapters:
        source_files = adapter.discover_source_files(repo_path)
        test_files = adapter.discover_test_files(repo_path)
        
        console.print(f"  [{adapter.language.value}] Found {len(source_files)} source files, {len(test_files)} test files")
        
        # Parse all source files for symbols
        for sf in source_files:
            try:
                symbols = adapter.parse_file(sf, repo_path)
                all_symbols.extend(symbols)
            except Exception as e:
                console.print(f"    [yellow]⚠ Parse error in {sf.name}: {e}[/]")
    
    if all_symbols:
        console.print(f"  Extracted [bold]{len(all_symbols)}[/] symbols")
        
        # Build known symbols map for call extraction
        known = {s.id: s for s in all_symbols}
        
        for adapter in adapters:
            source_files = adapter.discover_source_files(repo_path)
            for sf in source_files:
                try:
                    calls = adapter.extract_calls(sf, repo_path, known)
                    all_calls.extend(calls)
                except Exception as e:
                    console.print(f"    [yellow]⚠ Call extraction error in {sf.name}: {e}[/]")
        
        if all_calls:
            console.print(f"  Extracted [bold]{len(all_calls)}[/] call edges")
    else:
        console.print("  [yellow]No symbols extracted — adapter parsing not yet implemented for this language.[/]")
    
    console.print()

    # ── Step 3-4: Impact + test mapping (Day 3) ──
    console.print("[bold]Step 3/4: Computing impact...[/]")
    console.print("  [yellow]⏳ Impact analysis arrives Day 3[/]")
    console.print()
    console.print("[bold]Step 4/4: Mapping to tests...[/]")
    console.print("  [yellow]⏳ Test mapping arrives Day 3[/]")
    console.print()

    # ── JSON output ──
    if json_out:
        result = {
            "repo_path": str(repo_path),
            "base": base,
            "head": head,
            "changed_regions": [r.model_dump(mode="json") for r in regions],
            "symbols_count": len(all_symbols),
            "calls_count": len(all_calls),
        }
        json_out.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Results written to {json_out}[/]")


if __name__ == "__main__":
    main()