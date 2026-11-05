#!/usr/bin/env python3
"""
Pinterest Downloader CLI
Blazing-fast Pinterest image and video downloader with parallel chunk acceleration.
"""

import sys
import os
import argparse
import asyncio
from typing import List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt
from rich.text import Text

from downloader import extract_media_from_pin, download_file_parallel

console = Console(force_terminal=True)

BANNER = """
[bold red]+============================================================+[/bold red]
[bold red]|[/bold red]   [bold white]PINTEREST ULTRA-FAST MEDIA DOWNLOADER CLI[/bold white]                [bold red]|[/bold red]
[bold red]|[/bold red]   [dim]Original Res Images * High-Definition Videos * Parallel[/dim]  [bold red]|[/bold red]
[bold red]+============================================================+[/bold red]
"""

async def process_single_pin(
    url: str,
    output_dir: str,
    chunks: int = 4
) -> Optional[str]:
    """Extract and download a single pin with Rich visual feedback."""
    console.print(f"\n[cyan]>> Fetching pin info for:[/cyan] [dim]{url}[/dim]")

    with console.status("[bold yellow]Extracting highest quality media URL...", spinner="dots"):
        try:
            info = await extract_media_from_pin(url)
        except Exception as e:
            console.print(f"[bold red][X] Failed to extract media:[/bold red] {e}")
            return None

    # Summary table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    media_badge = "[bold green][VIDEO][/bold green]" if info["media_type"] == "video" else "[bold blue][IMAGE][/bold blue]"
    table.add_row("Type:", media_badge)
    table.add_row("Title:", info["title"] or "Untitled")
    if info.get("pin_id"):
        table.add_row("Pin ID:", info["pin_id"])
    table.add_row("Media URL:", f"[dim]{info['media_url'][:70]}...[/dim]")

    console.print(Panel(table, title="[bold white]Media Details[/bold white]", border_style="red"))

    # Prepare download destination
    os.makedirs(output_dir, exist_ok=True)
    dest_path = os.path.join(output_dir, info["filename"])

    # Prevent overwriting existing file with identical name
    base_name, ext = os.path.splitext(dest_path)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = f"{base_name}_{counter}{ext}"
        counter += 1

    # Progress bar setup
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(f"Downloading {os.path.basename(dest_path)}", total=None)

        def on_progress(chunk_len: int, total_len: int):
            if total_len > 0 and progress.tasks[task_id].total is None:
                progress.update(task_id, total=total_len)
            progress.update(task_id, advance=chunk_len)

        try:
            saved_file = await download_file_parallel(
                url=info["media_url"],
                dest_path=dest_path,
                progress_callback=on_progress,
                num_chunks=chunks,
            )
            abs_path = os.path.abspath(saved_file)
            console.print(f"[bold green][OK] Successfully saved to:[/bold green] [underline white]{abs_path}[/underline white]")
            return abs_path
        except Exception as e:
            console.print(f"[bold red][X] Download failed:[/bold red] {e}")
            return None


async def run_batch(urls: List[str], output_dir: str, chunks: int = 4):
    """Download multiple pins sequentially or concurrently."""
    console.print(f"[bold green]>> Processing {len(urls)} pin(s)...[/bold green]")
    success_count = 0
    for idx, u in enumerate(urls, 1):
        console.rule(f"[bold]Pin {idx} of {len(urls)}[/bold]")
        result = await process_single_pin(u, output_dir, chunks)
        if result:
            success_count += 1

    console.print(f"\n[bold green][DONE] Successfully downloaded {success_count}/{len(urls)} pin(s).[/bold green]")
    console.print(f"[dim]Saved in: {os.path.abspath(output_dir)}[/dim]\n")


async def interactive_loop(output_dir: str, chunks: int = 4):
    """Continuous interactive prompt for pasting URLs."""
    console.print(BANNER)
    console.print(f"[dim]Downloads will be saved to: [white]{os.path.abspath(output_dir)}[/white][/dim]\n")
    console.print("[yellow]Paste any Pinterest URL (e.g. https://pin.it/... or https://pinterest.com/pin/...) or type 'exit' / 'q' to quit.[/yellow]\n")

    while True:
        try:
            user_input = Prompt.ask("\n[bold red][*] Paste Pinterest URL[/bold red]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting. Goodbye![/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q"]:
            console.print("[bold yellow]Goodbye![/bold yellow]")
            break

        # Check if user entered multiple URLs separated by spaces/commas
        urls = [u.strip() for u in user_input.split() if "pinterest" in u.lower() or "pin.it" in u.lower()]
        if not urls:
            # Fallback to whatever user entered if it looks like a URL
            if user_input.startswith("http"):
                urls = [user_input]
            else:
                console.print("[red][!] Please enter a valid Pinterest or pin.it link.[/red]")
                continue

        for u in urls:
            await process_single_pin(u, output_dir, chunks)


def main():
    parser = argparse.ArgumentParser(
        description="Pinterest Ultra-Fast Media Downloader CLI (Images, Videos, GIFs)"
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more Pinterest URLs (https://pin.it/... or https://pinterest.com/pin/...)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Directory where media will be saved (default: ./downloads)",
    )
    parser.add_argument(
        "-c",
        "--chunks",
        type=int,
        default=4,
        help="Number of parallel chunks for large downloads (default: 4)",
    )

    args = parser.parse_args()

    # If URLs provided via CLI args, run batch
    if args.urls:
        console.print(BANNER)
        asyncio.run(run_batch(args.urls, args.output, args.chunks))
    else:
        # Otherwise start friendly interactive mode
        asyncio.run(interactive_loop(args.output, args.chunks))


if __name__ == "__main__":
    main()
