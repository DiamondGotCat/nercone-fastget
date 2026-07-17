import os
import shutil
import asyncio
import pathlib
import argparse
from typing import Optional, List
from strip_ansi import strip_ansi
from urllib.parse import urlsplit, unquote

from modern import Color, ProgressBar
from modern.progressbar import NamePart, PercentagePart, ProgressPart, MessagePart, SpeedPart, ETAPart

from .lib import FastGet, Callback

def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"

class CLICallback(Callback):
    def __init__(self):
        self.progress: List[int] = []
        self.bars: List[ProgressBar] = []
        self.total_bar: Optional[ProgressBar] = None

    async def on_start(self, size: int, threads: int, url: str, http_version: str):
        left  = f"{http_version} GET {url}"
        right = f"{Color.from_name('grey')}{threads} thread{'s' if threads > 1 else ''} / {human_size(size) if size else 'Size unknown'}{Color.from_name('reset')}"

        left_len  = len(strip_ansi(left))
        right_len = len(strip_ansi(right))

        terminal_size = shutil.get_terminal_size((left_len + right_len + 1, 1))
        fit = (left_len + right_len + 1) <= terminal_size.columns

        print((left if fit else left[:(terminal_size.columns - right_len - 4)] + "...") + ((" " * (terminal_size.columns - left_len - right_len) if fit else " ") + right))

        self.progress = [0] * (threads + 1)
        self.bars = [None] * (threads + 1)

        self.total_bar = ProgressBar("Download", size or 1, suffix=[NamePart(), PercentagePart(), ProgressPart(), SpeedPart(), ETAPart(), MessagePart()])

        if threads > 1:
            per_thread = -(-size // threads)
            for thread in range(1, threads + 1):
                self.bars[thread] = ProgressBar(f"Thread {thread}", per_thread, suffix=[NamePart(), PercentagePart(), ProgressPart(), SpeedPart(), ETAPart(), MessagePart()])

    async def on_update(self, thread: int, downloaded: int):
        delta = downloaded - self.progress[thread]
        if delta <= 0:
            return
        self.progress[thread] = downloaded

        self.total_bar.update(delta)

        bar = self.bars[thread]
        if bar is not None:
            bar.update(delta)

    async def on_complete(self):
        for bar in self.bars:
            if bar is not None:
                bar.set_message(human_size(bar.current))

        for bar in self.bars:
            if bar is not None:
                bar.finish()

        self.total_bar.finish()

    async def on_retry(self, thread: int, attempt: int, max_attempts: int):
        bar = self.bars[thread]
        if bar is None:
            print(f"{Color.from_name('yellow')}RETRY{Color.from_name('reset')} attempt {attempt}/{max_attempts}")
            return
        bar.set_message(f"{Color.from_name('yellow')}retry {attempt}/{max_attempts}{Color.from_name('reset')}")

    async def on_error(self, message: str):
        print(f"{Color.from_name('red')}ERROR{Color.from_name('reset')} {message}")

def main():
    parser = argparse.ArgumentParser(prog="fastget", description="High-speed File Downloading Tool")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Number of download threads (default: 4)")

    arg = parser.parse_args()

    if arg.output:
        output = pathlib.Path(arg.output)
    else:
        output = pathlib.Path(unquote(os.path.basename(urlsplit(arg.url).path)) or "fastget-download")

    try:
        asyncio.run(FastGet.get(arg.url, threads=arg.threads, callback=CLICallback(), filepath=str(output)))
    except Exception:
        raise SystemExit(1)

    print(f"{Color.from_name('bright_green')}Downloaded{Color.from_name('reset')} to {output} {Color.from_name('grey')}{human_size(output.stat().st_size)}{Color.from_name('reset')}")
