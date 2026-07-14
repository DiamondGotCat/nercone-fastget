import sys
import time
import shutil
import asyncio
import argparse
from typing import Optional, List, Dict
from pathlib import Path
from strip_ansi import strip_ansi
from urllib.parse import urlparse, unquote
from modern import Color, ProgressBar
from modern.progressbar import NamePart, PercentagePart, ProgressPart, ETAPart, MessagePart

from .lib import Callback, FastGet

update_interval = 0.2 # 200ms

def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"

class CLICallback(Callback):
    def __init__(self):
        self.bars: List[ProgressBar] = []
        self.total_bar: Optional[ProgressBar] = None

        self.unknown_size = False

        self.last_update_time: Dict[int, float] = {}

    async def on_start(self, size: int, threads: int, http_version: int, url: str):
        left  = f"HTTP/{http_version} GET {url}"
        right = f"{Color.from_name('grey')}{threads} thread{'s' if threads > 1 else ''} / {human_size(size) if size else 'Size unknown'}{Color.from_name('reset')}"

        left_len  = len(strip_ansi(left))
        right_len = len(strip_ansi(right))

        terminal_size = shutil.get_terminal_size((left_len + right_len + 1, 1))
        fit = (left_len + right_len + 1) <= terminal_size.columns

        print((left if fit else left[:(terminal_size.columns - right_len - 4)] + "...") + ((" " * (terminal_size.columns - left_len - right_len) if fit else " ") + right))

        if size == 0:
            if threads == 1:
                self.unknown_size = True
                bar = ProgressBar(name="Download", total=1, suffix=[NamePart(), PercentagePart(), ProgressPart(), ETAPart(), MessagePart()])
                self.bars.append(bar)
            return

        chunk_size = size // threads
        chunk_sizes = [chunk_size] * threads
        if threads > 1:
            chunk_sizes[-1] = size - chunk_size * (threads - 1)

        if threads > 1:
            self.total_bar = ProgressBar(name="Download", total=size if size > 0 else 1, primary_color="bright_blue", suffix=[NamePart(), PercentagePart(), ProgressPart(), ETAPart(), MessagePart()])

        for i in range(threads):
            bar = ProgressBar(name=f"Thread {i + 1}" if threads > 1 else "Download", total=chunk_sizes[i], suffix=[NamePart(), PercentagePart(), ProgressPart(), ETAPart(), MessagePart()])
            self.bars.append(bar)

    async def on_update(self, thread: int, downloaded: int):
        if thread >= len(self.bars):
            return

        bar = self.bars[thread]

        if self.unknown_size:
            now = time.monotonic()
            if now - self.last_update_time.get(thread, 0.0) >= update_interval:
                self.last_update_time[thread] = now
                bar.set_message(human_size(downloaded))
            return

        delta = downloaded - bar.current
        if delta <= 0:
            return

        now = time.monotonic()
        if downloaded < bar.total and now - self.last_update_time.get(thread, 0.0) < update_interval:
            return
        self.last_update_time[thread] = now

        bar.set_message(human_size(downloaded))
        bar.update(delta)
        if self.total_bar is not None:
            self.total_bar.update(delta)

    async def on_complete(self):
        if self.total_bar is not None:
            self.total_bar.finish()
        for bar in self.bars:
            bar.finish()

    async def on_retry(self, thread: int, attempt: int, max_attempts: int, message: str):
        if thread >= len(self.bars):
            return
        self.bars[thread].set_message(f"{Color.from_name('yellow')}retry {attempt}/{max_attempts}: {message}{Color.from_name('reset')}")

    async def on_error(self, message: str):
        print(f"{Color.from_name('red')}ERROR{Color.from_name('reset')} {message}")

def main():
    parser = argparse.ArgumentParser(prog="fastget", description="High-speed File Downloading Tool")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("-o", "--output", help="Output file path (default: filename from URL)")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Number of download threads (default: 8)")
    parser.add_argument("-r", "--retries", type=int, default=5, help="Max retries per thread on transient errors (default: 5)")

    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(unquote(Path(urlparse(args.url).path).name) or "fastget-downloaded")

    temp_path = output_path.with_name(output_path.name + ".part")

    try:
        asyncio.run(FastGet.get(args.url, threads=args.threads, callback=CLICallback(), temp_path=temp_path, max_retries=args.retries))
    except KeyboardInterrupt:
        print(f"{Color.from_name('yellow')}Interrupted{Color.from_name('reset')}")
        sys.exit(1)
    except Exception:
        sys.exit(1)

    temp_path.replace(output_path)
    print(f"{Color.from_name('bright_green')}Downloaded{Color.from_name('reset')} to {output_path} {Color.from_name('grey')}{human_size(output_path.stat().st_size)}{Color.from_name('reset')}")
