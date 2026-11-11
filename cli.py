"""
Learn With Communities Campaign - Rich CLI & TUI Tracker
"""
import sys
import os
import argparse
import asyncio
import json
from datetime import datetime

# Configure UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich import box
from rich.text import Text

# Ensure current folder is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.campaign import CAMPAIGN_BADGES, evaluate_candidate
from core.scraper import scrape_single_profile, scrape_batch
from core.csv_handler import parse_csv_data, export_results_csv
import httpx

console = Console(force_terminal=True)

BANNER = """[bold cyan]
========================================================================
   GOOGLE SKILLS TRACKER - LEARN WITH COMMUNITIES CAMPAIGN
========================================================================
[/bold cyan]
[bold yellow]* Track Candidate Skill Badges, Credentials & Completion Status *[/bold yellow]
"""



def print_banner():
    console.print(BANNER)


def display_results_table(results):
    table = Table(
        title="[bold green]Campaign Candidate Verification Results[/bold green]",
        box=box.ROUNDED,
        header_style="bold magenta",
        expand=True
    )

    table.add_column("#", justify="center", style="dim", width=4)
    table.add_column("Candidate Name", style="bold white", min_width=18)
    table.add_column("Status", justify="center", min_width=16)
    table.add_column("Campaign Badges", justify="center", min_width=15)
    table.add_column("Progress", justify="left", min_width=20)
    table.add_column("Total Badges", justify="center", style="cyan", width=12)
    table.add_column("Notes / Info", style="dim", min_width=15)

    for idx, r in enumerate(results, 1):
        status = r.get("status")
        pct = r.get("completion_percentage", 0.0)
        completed = r.get("campaign_completed", 0)

        # Style status
        if status == "COMPLETED":
            status_render = "[bold green]✅ 10/10 COMPLETED[/bold green]"
            bar_color = "green"
        elif status == "IN_PROGRESS":
            status_render = f"[bold yellow]⏳ {completed}/10 In Progress[/bold yellow]"
            bar_color = "yellow"
        elif status == "PRIVATE_PROFILE":
            status_render = "[bold red]🔒 Private Account[/bold red]"
            bar_color = "red"
        elif status == "NOT_STARTED":
            status_render = "[dim]⭕ 0/10 Not Started[/dim]"
            bar_color = "white"
        else:
            status_render = f"[bold red]⚠️ {r.get('name', 'Error')}[/bold red]"
            bar_color = "red"

        # Text progress bar
        bar_len = 10
        filled = int((pct / 100) * bar_len)
        bar_str = f"[{bar_color}]{'#' * filled}{'-' * (bar_len - filled)}[/] [bold]{pct}%[/bold]"

        table.add_row(
            str(idx),
            r.get("name", "Unknown"),
            status_render,
            f"[bold]{completed}[/bold] / 10",
            bar_str,
            str(r.get("total_badges", 0)),
            r.get("original_info", "")
        )

    console.print(table)


def display_summary_cards(results):
    total = len(results)
    completed = sum(1 for r in results if r.get("status") == "COMPLETED")
    in_progress = sum(1 for r in results if r.get("status") == "IN_PROGRESS")
    not_started = sum(1 for r in results if r.get("status") == "NOT_STARTED")
    private_count = sum(1 for r in results if r.get("status") == "PRIVATE_PROFILE")
    errors = sum(1 for r in results if r.get("status") == "ERROR")

    overall_rate = round((completed / total * 100), 1) if total > 0 else 0.0

    summary_text = f"""
[bold cyan]Total Students Evaluated:[/] [bold white]{total}[/]
[bold green]🏆 Completed All 10 Badges:[/] [bold green]{completed}[/] ({overall_rate}%)
[bold yellow]⏳ In Progress (1-9 Badges):[/] [bold yellow]{in_progress}[/]
[bold white]⭕ Not Started (0 Badges):[/] [dim white]{not_started}[/]
[bold red]🔒 Private Accounts:[/] [bold red]{private_count}[/] (Needs public access)
[bold magenta]⚠️ Errors / Invalid:[/] [bold magenta]{errors}[/]
"""
    panel = Panel(
        summary_text.strip(),
        title="[bold yellow]Campaign Verification Summary[/bold yellow]",
        border_style="cyan",
        box=box.ROUNDED
    )
    console.print(panel)


async def run_scan_csv(csv_path: str, output_path: str = None, delay: float = 0.8, concurrency: int = 2):
    """Scans students from CSV with rich progress animation."""
    if not os.path.exists(csv_path):
        console.print(f"[bold red]Error:[/] File not found: {csv_path}")
        return

    records = parse_csv_data(csv_path)
    if not records:
        console.print("[bold red]No valid candidate URLs found in CSV![/]")
        return

    console.print(f"\n[bold cyan]Found {len(records)} students in CSV.[/bold cyan] Starting verification (Rate delay: {delay}s, Concurrency: {concurrency})...\n")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="green", finished_style="bold green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Verifying Google Skills credentials...", total=len(records))

        def on_step(res, count, total_count):
            status_sym = "✅" if res.get("status") == "COMPLETED" else ("⏳" if res.get("status") == "IN_PROGRESS" else "🔒" if res.get("status") == "PRIVATE_PROFILE" else "⭕")
            progress.update(task, completed=count, description=f"[cyan]Checked: {res.get('name')} {status_sym} ({res.get('campaign_completed', 0)}/10)")

        results = await scrape_batch(records, progress_callback=on_step, delay_between_requests=delay, concurrency_limit=concurrency)

    console.print("\n")
    display_results_table(results)
    display_summary_cards(results)

    # Save to output file
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"campaign_report_{timestamp}.csv"

    if output_path.endswith(".json"):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        console.print(f"[bold green]✔ Results saved to JSON:[/] [underline]{output_path}[/]")
    else:
        export_results_csv(results, output_path)
        console.print(f"[bold green]✔ Results saved to CSV:[/] [underline]{output_path}[/]")


async def run_single_check(url: str):
    """Verifies a single candidate URL with full detailed badge breakdown."""
    console.print(f"\n[cyan]Inspecting Google Skills profile:[/] {url} ...")
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        res = await scrape_single_profile(client, url)

    name = res.get("name", "Unknown")
    status = res.get("status")
    completed = res.get("campaign_completed", 0)
    total_req = res.get("campaign_total", 10)
    pct = res.get("completion_percentage", 0.0)

    # Candidate profile card
    card_text = f"""
[bold white]Candidate Name:[/] [bold yellow]{name}[/]
[bold white]Status:[/] {res.get('status_label')}
[bold white]Campaign Progress:[/] [bold green]{completed}/{total_req} Badges ({pct}%)[/]
[bold white]Total Profile Badges:[/] [cyan]{res.get('total_badges', 0)}[/]
[bold white]Profile URL:[/] {res.get('url')}
"""
    console.print(Panel(card_text.strip(), title="[bold cyan]Candidate Profile[/bold cyan]", box=box.ROUNDED))

    # Badge breakdown table
    table = Table(
        title="[bold yellow]Official Learn With Communities Campaign Badges Checklist[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold magenta",
        expand=True
    )
    table.add_column("#", justify="center", width=4)
    table.add_column("Badge Title", style="bold white", min_width=35)
    table.add_column("Category", style="dim", min_width=20)
    table.add_column("Status", justify="center", min_width=14)
    table.add_column("Earned Date", justify="center", style="cyan", min_width=18)

    earned_dict = {b["title"]: b for b in res.get("earned_campaign_badges", [])}

    for idx, b in enumerate(CAMPAIGN_BADGES, 1):
        if b["title"] in earned_dict:
            earned_item = earned_dict[b["title"]]
            status_text = "[bold green]✅ Earned[/bold green]"
            date_text = earned_item.get("earned_date", "Completed")
        else:
            status_text = "[bold red]❌ Missing[/bold red]"
            date_text = "[dim]—[/dim]"

        table.add_row(str(idx), b["title"], b["category"], status_text, date_text)

    console.print(table)


def run_tui():
    """Interactive Terminal User Interface (TUI)."""
    print_banner()
    while True:
        console.print("\n[bold cyan]Interactive Campaign Tracker Menu:[/bold cyan]")
        console.print("1. [bold green]Scan CSV file[/bold green] (Customizable student list)")
        console.print("2. [bold yellow]Verify single profile URL[/bold yellow]")
        console.print("3. [bold blue]View official 10 campaign badges[/bold blue]")
        console.print("4. [bold magenta]Run default sample CSV (sample_students.csv)[/bold magenta]")
        console.print("5. [bold red]Exit[/bold red]")

        choice = Prompt.ask("\nSelect an option", choices=["1", "2", "3", "4", "5"], default="4")

        if choice == "1":
            csv_path = Prompt.ask("Enter CSV file path", default="sample_students.csv")
            delay = float(Prompt.ask("Enter rate limit delay in seconds", default="0.8"))
            out_file = Prompt.ask("Enter output report path", default="campaign_report.csv")
            asyncio.run(run_scan_csv(csv_path, output_path=out_file, delay=delay))

        elif choice == "2":
            url = Prompt.ask("Enter Google Skills Profile URL")
            asyncio.run(run_single_check(url))

        elif choice == "3":
            t = Table(title="Learn With Communities Campaign - 10 Required Badges", box=box.ROUNDED)
            t.add_column("#", justify="center", width=4)
            t.add_column("Badge Name", style="bold green", min_width=35)
            t.add_column("Category", style="cyan", min_width=20)
            t.add_column("Description", style="white")
            for idx, b in enumerate(CAMPAIGN_BADGES, 1):
                t.add_row(str(idx), b["title"], b["category"], b["description"])
            console.print(t)

        elif choice == "4":
            asyncio.run(run_scan_csv("sample_students.csv", output_path="campaign_report.csv", delay=0.6))

        elif choice == "5":
            console.print("[yellow]Exiting Campaign Tracker. Happy Tracking![/yellow]")
            break


def main():
    parser = argparse.ArgumentParser(description="Learn With Communities Campaign Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scan command
    scan_p = subparsers.add_parser("scan", help="Scan candidate credentials from CSV")
    scan_p.add_argument("csv_file", nargs="?", default="sample_students.csv", help="Path to input CSV file")
    scan_p.add_argument("-o", "--output", default="campaign_report.csv", help="Output report file path (.csv or .json)")
    scan_p.add_argument("-d", "--delay", type=float, default=0.8, help="Polite delay between requests (seconds)")
    scan_p.add_argument("-c", "--concurrency", type=int, default=2, help="Concurrency limit")

    # Check command
    check_p = subparsers.add_parser("check", help="Verify single Google Skills profile URL")
    check_p.add_argument("url", help="Google Skills Profile URL")

    # TUI command
    subparsers.add_parser("tui", help="Launch interactive Terminal UI")

    # Badges command
    subparsers.add_parser("badges", help="List official 10 campaign badges")

    args = parser.parse_args()

    if args.command == "scan":
        print_banner()
        asyncio.run(run_scan_csv(args.csv_file, args.output, delay=args.delay, concurrency=args.concurrency))
    elif args.command == "check":
        print_banner()
        asyncio.run(run_single_check(args.url))
    elif args.command == "badges":
        print_banner()
        t = Table(title="Official 10 Campaign Badges", box=box.ROUNDED)
        t.add_column("#", justify="center", width=4)
        t.add_column("Badge Name", style="bold green", min_width=35)
        t.add_column("Category", style="cyan", min_width=20)
        t.add_column("Description", style="white")
        for idx, b in enumerate(CAMPAIGN_BADGES, 1):
            t.add_row(str(idx), b["title"], b["category"], b["description"])
        console.print(t)
    elif args.command == "tui":
        run_tui()
    else:
        # Default if no arguments: launch TUI or prompt
        run_tui()


if __name__ == "__main__":
    main()
