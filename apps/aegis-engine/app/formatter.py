"""Presentation layer for Aegis SLO reports (Rich CLI Tables & JSON)."""

from __future__ import annotations

import json
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .slo_engine import ServiceSLOReport, ComplianceStatus


def print_cli_report(report: ServiceSLOReport) -> None:
    """Renders a formatted SRE assessment report in the terminal."""
    if not RICH_AVAILABLE:
        _print_plain_report(report)
        return

    console = Console()

    # Determine status styling
    status_colors = {
        ComplianceStatus.HEALTHY: "bold green",
        ComplianceStatus.AT_RISK: "bold yellow",
        ComplianceStatus.VIOLATED: "bold red",
        ComplianceStatus.NO_DATA: "bold cyan",
    }
    status_color = status_colors.get(report.overall_status, "white")

    # Header Panel
    header_text = Text()
    header_text.append("AEGIS SRE CONTROL PLANE — SLO & ERROR BUDGET EVALUATION\n", style="bold cyan")
    header_text.append(f"Target API: {report.api_name}  |  Namespace: {report.namespace}  |  Window: {report.window}\n", style="dim")
    header_text.append("Overall Compliance: ", style="bold white")
    header_text.append(f"[{report.overall_status.value}]", style=status_color)

    console.print(Panel(header_text, border_style="cyan", box=box.ROUNDED))

    # SLI Table
    table = Table(title="Service Level Indicators (SLIs)", box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta")
    table.add_column("SLI Metric", style="cyan", no_wrap=True)
    table.add_column("Target (SLO)", justify="right", style="white")
    table.add_column("Current SLI", justify="right", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Assessment Note", style="dim")

    for name, sli in report.sli_results.items():
        if sli.actual_value is None:
            actual_str = "No Data"
            status_badge = "[cyan]NO DATA[/cyan]"
        else:
            actual_str = f"{sli.actual_value} {sli.unit}"
            if sli.status == ComplianceStatus.HEALTHY:
                status_badge = "[green]✓ MET[/green]"
            elif sli.status == ComplianceStatus.AT_RISK:
                status_badge = "[yellow]! AT RISK[/yellow]"
            else:
                status_badge = "[red]✗ VIOLATED[/red]"

        target_str = f"{sli.target} {sli.unit}"
        table.add_row(sli.name, target_str, actual_str, status_badge, sli.details)

    console.print(table)

    # Error Budget Panel
    if report.error_budget:
        eb = report.error_budget
        eb_table = Table(box=box.SIMPLE, show_header=False)
        eb_table.add_column("Property", style="bold white")
        eb_table.add_column("Value", style="bold")

        # Progress bar representation for remaining budget
        rem = eb.remaining_budget_percent
        bar_len = 20
        filled = int((rem / 100.0) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        if rem >= 50:
            bar_styled = f"[green]{bar} {rem}%[/green]"
        elif rem > 0:
            bar_styled = f"[yellow]{bar} {rem}%[/yellow]"
        else:
            bar_styled = f"[red]{bar} 0.0% (EXHAUSTED)[/red]"

        burn_styled = f"[green]{eb.burn_rate}x[/green]" if eb.burn_rate <= 1.0 else f"[red]{eb.burn_rate}x (ACCELERATED)[/red]"

        eb_table.add_row("Total Error Budget (100% - Target)", f"{eb.total_budget_percent}%")
        eb_table.add_row("Consumed Unreliability (Error Rate)", f"{eb.consumed_budget_percent}%")
        eb_table.add_row("Remaining Error Budget", bar_styled)
        eb_table.add_row("Error Budget Burn Rate", burn_styled)
        if eb.time_to_exhaustion:
            eb_table.add_row("Estimated Time to Exhaustion", f"[bold red]{eb.time_to_exhaustion}[/bold red]")

        eb_panel = Panel(eb_table, title="[bold yellow]Error Budget & Burn Rate Accounting[/bold yellow]", border_style="yellow", box=box.ROUNDED)
        console.print(eb_panel)


def _print_plain_report(report: ServiceSLOReport) -> None:
    """Fallback plain-text printer if Rich is not installed."""
    print("=" * 70)
    print(f"AEGIS SRE SLO REPORT — {report.api_name} (Window: {report.window})")
    print(f"Overall Status: {report.overall_status.value}")
    print("-" * 70)
    for name, sli in report.sli_results.items():
        actual = f"{sli.actual_value} {sli.unit}" if sli.actual_value is not None else "No Data"
        print(f"  * {sli.name:<20} Target: {sli.target:>6} {sli.unit} | Actual: {actual:>10} | [{sli.status.value}]")
    if report.error_budget:
        eb = report.error_budget
        print("-" * 70)
        print(f"  Error Budget Total:     {eb.total_budget_percent}%")
        print(f"  Error Budget Remaining: {eb.remaining_budget_percent}%")
        print(f"  Burn Rate:              {eb.burn_rate}x")
    print("=" * 70)


def format_json_report(report: ServiceSLOReport) -> str:
    """Serializes the report to structured JSON."""
    return json.dumps(report.to_dict(), indent=2)
