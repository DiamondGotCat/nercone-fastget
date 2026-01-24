# ╭──────────────────────────────────────╮
# │ __main__.py on nercone-fastget       │
# │ Nercone <nercone@diamondgotcat.net>  │
# │ Made by Nercone / MIT License        │
# │ Copyright (c) 2025 DiamondGotCat     │
# ╰──────────────────────────────────────╯

import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse, unquote
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.filesize import decimal
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

from .fastget import (
    FastGetSession,
    ProgressCallback,
    FastGetError,
    DEFAULT_THREADS,
    VERSION,
)

class RichProgressCallback(ProgressCallback):
    def __init__(self, console: "Console", progress: "Progress"):
        self.console = console
        self.progress = progress
        self.overall_task: Optional[int] = None
        self.worker_tasks: List[int] = []
        self.merge_task: Optional[int] = None

    async def on_start(self, total_size: int, threads: int, http_version: str, final_url: str, verify_was_enabled: bool) -> None:
        self.console.print(Panel(
            f"[bold]URL[/bold]: {final_url}\n"
            f"[bold]File Size[/bold]: {decimal(total_size)}\n"
            f"[bold]Threads[/bold]: {threads}\n"
            f"[bold]HTTP Version[/bold]: {http_version}\n"
            f"[bold]SSL/TLS Verify[/bold]: {'Enabled' if verify_was_enabled else '[yellow]Disabled[/yellow]'}",
            title="Download Information",
            border_style="green",
            expand=False
        ))
        self.overall_task = self.progress.add_task("[bold green]Download", total=total_size)
        if threads > 1:
            part_size = total_size // threads
            for i in range(threads):
                task_total = total_size - (part_size * i) if i == threads - 1 else part_size
                self.worker_tasks.append(self.progress.add_task(f"Worker {i+1}", total=task_total))

    async def on_update(self, worker_id: int, loaded: int) -> None:
        if self.overall_task is not None:
            self.progress.update(self.overall_task, advance=loaded)
        if self.worker_tasks and worker_id < len(self.worker_tasks):
            self.progress.update(self.worker_tasks[worker_id], advance=loaded)

    async def on_merge_start(self, total_size: int) -> None:
        self.merge_task = self.progress.add_task("[bold cyan]Merge", total=total_size)

    async def on_merge_update(self, loaded: int) -> None:
        if self.merge_task is not None:
            self.progress.update(self.merge_task, advance=loaded)

    async def on_slowdown(self, msg: str) -> None:
        self.console.print(f"[yellow]W[/yellow] {msg}")

    async def on_error(self, msg: str) -> None:
        if not self.progress.finished:
            self.progress.stop()
        self.console.print(f"[bold red]E[/bold red] {msg}")

class SilentProgressCallback(ProgressCallback):
    def __init__(self, console: "Console"):
        self.console = console

    async def on_error(self, msg: str) -> None:
        self.console.print(f"[bold red]E[/bold red] {msg}")

async def main():
    parser = argparse.ArgumentParser(prog="fastget", description=f"High-speed File Downloading Tool", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("url", help="URL to download from.")
    parser.add_argument("-o", "--output", help="Path to save the file. If not specified, it's inferred from the URL.")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help=f"Number of parallel connections. (default: {DEFAULT_THREADS})")
    parser.add_argument( "-X", "--request", default="GET", choices=["GET", "POST"], help="HTTP method to use. (default: GET)")
    parser.add_argument( "-H", "--header", action="append", help="Custom header to send with the request (e.g., 'User-Agent: my-app/1.0').\nCan be specified multiple times.")
    parser.add_argument("-d", "--data", help="Data to send in a POST request.")
    parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable SSL/TLS certificate verification.")
    parser.add_argument("--no-info", action="store_true", help="Silent mode. Suppress progress bar and other info.\nErrors are still printed to stderr.")
    parser.add_argument("--no-http1", action="store_false", dest="http1", help="Disable HTTP/1.x and force HTTP/2.")
    parser.add_argument("--no-http2", action="store_false", dest="http2", help="Disable HTTP/2 and force HTTP/1.x.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()

    if args.no_info:
        console = Console(stderr=True, quiet=True)
        callback = SilentProgressCallback(console)
        progress = None
    else:
        console = Console()
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TextColumn("ETA:"),
            TimeRemainingColumn(),
            console=console,
            transient=True
        )
        callback = RichProgressCallback(console, progress)

    output_path = args.output
    if not output_path:
        try:
            parsed_url = urlparse(args.url)
            filename = os.path.basename(unquote(parsed_url.path))
            if not filename:
                console.print("[bold red]E[/bold red] Cannot determine output filename from URL. Please specify it with the -o/--output option.")
                sys.exit(1)
            output_path = filename
        except Exception as e:
            console.print(f"[bold red]E[/bold red] Invalid URL provided: {e}")
            sys.exit(1)

    headers: Dict[str, str] = {}
    if args.header:
        for h in args.header:
            if ":" in h:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()
            elif "=" in h:
                key, value = h.split("=", 1)
                headers[key.strip()] = value.strip()
            else:
                console.print(f"[yellow]W[/yellow] Ignoring malformed header: {h}")

    session = FastGetSession(
        max_threads=args.threads,
        http1=args.http1,
        http2=args.http2,
        verify=args.verify,
    )

    try:
        downloader = session.process(
            method=args.request.upper(),
            url=args.url,
            output=output_path,
            data=args.data,
            headers=headers,
            callback=callback,
        )

        if progress:
            with progress:
                result = await downloader
        else:
            result = await downloader

        if not args.no_info:
            console.print(f"[bold green]✔ Downloaded[/bold green] Saved to '{result}'")

    except (FastGetError, Exception) as e:
        if not isinstance(callback, RichProgressCallback) or (isinstance(callback, RichProgressCallback) and callback.progress.finished):
            console.print(f"[bold red]E[/bold red] {e}")

        if output_path:
            if os.path.exists(output_path):
                try: os.remove(output_path)
                except OSError: pass

            out_dir = os.path.dirname(output_path) or '.'
            out_base = os.path.basename(output_path)
            for i in range(args.threads):
                part_path = os.path.join(out_dir, f"{out_base}.part{i}")
                if os.path.exists(part_path):
                    try: os.remove(part_path)
                    except OSError: pass
        sys.exit(1)

def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Console().print("\n[yellow]W[/yellow] Aborted.")
        sys.exit(130)

if __name__ == "__main__":
    run()
