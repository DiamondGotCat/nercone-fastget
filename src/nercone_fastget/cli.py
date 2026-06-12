import sys
import asyncio
import argparse
from pathlib import Path
from urllib.parse import urlparse

from nercone_modern import Color, ProgressBar

from .lib import Callback, FastGet

progress_threshold = 10 * 1024

def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

class CLICallback(Callback):
    def __init__(self):
        self.bars: list[ProgressBar] = []
        self.total_bar: ProgressBar | None = None
        self.merge_bar: ProgressBar | None = None
        self._unknown_size = False
        self._unknown_rendered = 0

    async def on_start(self, size: int, threads: int, http_version: int, url: str) -> None:
        print(f"HTTP/{http_version} GET {url} {Color.from_name('grey')}{threads} thread{'s' if threads > 1 else ''} / {human_size(size) if size else 'Size unknown'}{Color.from_name('reset')}")

        if size == 0:
            if threads == 1:
                self._unknown_size = True
                bar = ProgressBar(process_name="Downloading", total=1)
                self.bars.append(bar)
            return

        chunk_size = size // threads
        chunk_sizes = [chunk_size] * threads
        if threads > 1:
            chunk_sizes[-1] = size - chunk_size * (threads - 1)

        if threads > 1:
            self.total_bar = ProgressBar(process_name="Download", total=size if size > 0 else 1, primary_color="bright_blue")

        for i in range(threads):
            bar = ProgressBar(process_name=f"Thread {i + 1}" if threads > 1 else "Downloading", total=chunk_sizes[i])
            self.bars.append(bar)

    async def on_update(self, thread: int, downloaded: int) -> None:
        if thread >= len(self.bars):
            return
        bar = self.bars[thread]
        if self._unknown_size:
            if downloaded >= self._unknown_rendered + progress_threshold:
                self._unknown_rendered = downloaded
                bar.set_message(human_size(downloaded))
                bar.render()
            return
        delta = downloaded - bar.current
        if len(self.bars) == 1 or delta >= progress_threshold:
            bar.set_message(human_size(downloaded))
            bar.update(delta)
            if self.total_bar is not None:
                self.total_bar.update(delta)

    async def on_complete(self) -> None:
        if self.total_bar is not None and not self.total_bar.completed:
            self.total_bar.finish()
        for bar in self.bars:
            if not bar.completed:
                bar.finish()

    async def on_merge_start(self, size: int) -> None:
        self.merge_bar = ProgressBar(process_name="Merging", total=size if size > 0 else 1, bar_length=50, primary_color="green")

    async def on_merge_update(self, downloaded: int) -> None:
        if self.merge_bar is None:
            return
        delta = downloaded - self.merge_bar.current
        if delta >= progress_threshold:
            self.merge_bar.set_message(human_size(downloaded))
            self.merge_bar.update(delta)

    async def on_merge_complete(self) -> None:
        if self.merge_bar is None:
            return
        if not self.merge_bar.completed:
            self.merge_bar.finish()

    async def on_error(self, message: str) -> None:
        print(f"{Color.from_name('red')}ERROR{Color.from_name('reset')} {message}")

def main():
    parser = argparse.ArgumentParser(prog="fastget", description="High-speed File Downloading Tool")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("-o", "--output", help="Output file path (default: filename from URL)")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Number of download threads (default: 8)")

    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        parsed = urlparse(args.url)
        filename = Path(parsed.path).name or "download"
        output_path = Path(filename)

    try:
        response = asyncio.run(FastGet.get(args.url, threads=args.threads, callback=CLICallback()))
    except KeyboardInterrupt:
        print(f"{Color.from_name('yellow')}Interrupted{Color.from_name('reset')}")
        sys.exit(1)
    except Exception:
        sys.exit(1)

    output_path.write_bytes(response.content)
    print(f"{Color.from_name('green')}Downloaded{Color.from_name('reset')} to {output_path} {Color.from_name('grey')}{human_size(len(response.content))}{Color.from_name('reset')}")
