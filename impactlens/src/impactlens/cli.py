"""ImpactLens CLI entry point."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from impactlens.core.registry import register_all_adapters, registry

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
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
@click.option("--run-tests", is_flag=True, default=False, help="Execute selected tests via Maven")
@click.option("--json-out", type=click.Path(path_type=Path), default=None, help="Write results as JSON")
def analyze(repo_path: Path, base: str, head: str, run_tests: bool, json_out: Path | None) -> None:
    """Analyze impact of changes between two git refs in a repository."""
    from impactlens.core.pipeline import run_analysis, PipelineResult

    console.print()
    console.print(Panel(
        f"[bold]Repository:[/]  [cyan]{repo_path}[/]\n"
        f"[bold]Base ref:[/]    [yellow]{base}[/]\n"
        f"[bold]Head ref:[/]    [yellow]{head}[/]\n"
        f"[bold]Run tests:[/]   {'✅ Yes' if run_tests else '⏭️  No'}",
        title="🎯 ImpactLens Analysis",
        border_style="blue",
    ))
    console.print()

    try:
        result: PipelineResult = run_analysis(repo_path, base, head, run_tests=run_tests)
    except Exception as e:
        console.print(f"[red bold]Pipeline failed:[/] {e}")
        sys.exit(1)

    analysis = result.analysis
    impact = analysis.impact

    # ── Changed Regions ──
    if analysis.changed_regions:
        table = Table(title="📝 Changed Regions", show_lines=False)
        table.add_column("File", style="cyan", no_wrap=True, max_width=60)
        table.add_column("Change", style="yellow", width=10)
        table.add_column("Old Range", justify="center", width=12)
        table.add_column("New Range", justify="center", width=12)

        for r in analysis.changed_regions:
            old_str = f"{r.old_range.start}-{r.old_range.end}" if r.old_range else "—"
            new_str = f"{r.new_range.start}-{r.new_range.end}" if r.new_range else "—"
            table.add_row(r.file_path, r.change_type.value, old_str, new_str)

        console.print(table)
        console.print()

    # ── Impact Summary ──
    console.print(Panel(
        f"[bold]Symbols parsed:[/]       {analysis.total_symbols}\n"
        f"[bold]Call edges found:[/]     {result.graph.edge_count}\n"
        f"[bold]Directly changed:[/]    {len(impact.changed_symbols)} symbols\n"
        f"[bold]Transitively impacted:[/] {len(impact.impacted_symbols)} symbols\n"
        f"[bold]Impacted files:[/]      {len(impact.impacted_files)}",
        title="💥 Impact Analysis",
        border_style="red",
    ))
    console.print()

    # ── Impact Tree ──
    if impact.changed_symbols:
        tree = Tree("🔍 [bold]Blast Radius[/]")
        for sym_id in impact.changed_symbols:
            sym = result.graph.get_symbol(sym_id)
            label = sym.name if sym else sym_id
            changed_node = tree.add(f"[red bold]✏️  {label}[/] [dim](changed)[/]")

            # Show direct callers
            callers = result.graph.direct_callers(sym_id)
            for caller_id in sorted(callers):
                caller_sym = result.graph.get_symbol(caller_id)
                caller_label = caller_sym.name if caller_sym else caller_id
                caller_node = changed_node.add(f"[yellow]← {caller_label}[/] [dim](caller)[/]")

                # Show their callers too (one more level)
                grandcallers = result.graph.direct_callers(caller_id)
                for gc_id in sorted(grandcallers):
                    gc_sym = result.graph.get_symbol(gc_id)
                    gc_label = gc_sym.name if gc_sym else gc_id
                    caller_node.add(f"[dim]← {gc_label}[/]")

        console.print(tree)
        console.print()

    # ── Test Selection ──
    if impact.selected_tests:
        test_table = Table(title="🧪 Selected Tests", show_lines=False)
        test_table.add_column("#", style="dim", width=4)
        test_table.add_column("Test", style="green")
        test_table.add_column("File", style="dim", max_width=50)

        for i, t in enumerate(impact.selected_tests, 1):
            test_table.add_row(str(i), t.id, t.file_path)

        console.print(test_table)

        reduction = (1 - len(impact.selected_tests) / analysis.total_tests) * 100 if analysis.total_tests else 0
        console.print(
            f"\n  📊 [bold]{len(impact.selected_tests)}[/] of "
            f"[bold]{analysis.total_tests}[/] tests selected "
            f"([green bold]{reduction:.0f}% reduction[/])"
        )
        console.print()
    else:
        console.print("[yellow]No tests selected (no impacted test files found).[/]")
        console.print()

    # ── Test Results (if --run-tests) ──
    if result.test_results:
        results_table = Table(title="🏃 Test Results", show_lines=False)
        results_table.add_column("Test", style="cyan", max_width=60)
        results_table.add_column("Status", width=8)
        results_table.add_column("Duration", justify="right", width=10)

        for tr in result.test_results:
            if tr.status.value == "passed":
                status_str = "[green]✅ PASS[/]"
            elif tr.status.value == "failed":
                status_str = "[red]❌ FAIL[/]"
            elif tr.status.value == "error":
                status_str = "[red bold]💥 ERR[/]"
            else:
                status_str = "[yellow]⏭️  SKIP[/]"

            results_table.add_row(tr.test_id, status_str, f"{tr.duration_ms:.0f}ms")

        console.print(results_table)
        console.print()

        passed = sum(1 for r in result.test_results if r.status.value == "passed")
        failed = sum(1 for r in result.test_results if r.status.value == "failed")
        total_time = sum(r.duration_ms for r in result.test_results)

        console.print(
            f"  ✅ {passed} passed  ❌ {failed} failed  "
            f"⏱️  {total_time:.0f}ms total"
        )
        console.print()

    # ── Timings ──
    console.print(Panel(
        "\n".join(f"[bold]{k}:[/] {v}" for k, v in result.timings.summary().items()),
        title="⏱️  Pipeline Timings",
        border_style="dim",
    ))

    # ── Warnings & Errors ──
    if result.warnings:
        console.print()
        for w in result.warnings:
            console.print(f"  [yellow]⚠ {w}[/]")

    if result.errors:
        console.print()
        for e in result.errors:
            console.print(f"  [red]✗ {e}[/]")

    # ── JSON output ──
    if json_out:
        output = {
            "repo_path": str(repo_path),
            "base": base,
            "head": head,
            "changed_regions": [r.model_dump(mode="json") for r in analysis.changed_regions],
            "impact": {
                "changed_symbols": impact.changed_symbols,
                "impacted_symbols": impact.impacted_symbols,
                "impacted_files": impact.impacted_files,
                "selected_tests": [t.model_dump(mode="json") for t in impact.selected_tests],
            },
            "total_symbols": analysis.total_symbols,
            "total_tests": analysis.total_tests,
            "test_results": [r.model_dump(mode="json") for r in result.test_results] if result.test_results else [],
            "timings": result.timings.summary(),
        }
        json_out.write_text(json.dumps(output, indent=2))
        console.print(f"\n[green]📄 Results written to {json_out}[/]")

    console.print()


if __name__ == "__main__":
    main()