import shutil
import argparse
from strip_ansi import strip_ansi

from modern import Color, ProgressBar
from modern.progressbar import NamePart, PercentagePart, ProgressPart, MessagePart, ETAPart

from .lib import Callback

def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"

class CLICallback(Callback):
    def __init__(self):
        ...

    async def on_start(self, size: int, threads: int, http_version: str, url: str):
        left  = f"{http_version} GET {url}"
        right = f"{Color.from_name('grey')}{threads} thread{'s' if threads > 1 else ''} / {human_size(size) if size else 'Size unknown'}{Color.from_name('reset')}"

        left_len  = len(strip_ansi(left))
        right_len = len(strip_ansi(right))

        terminal_size = shutil.get_terminal_size((left_len + right_len + 1, 1))
        fit = (left_len + right_len + 1) <= terminal_size.columns

        print((left if fit else left[:(terminal_size.columns - right_len - 4)] + "...") + ((" " * (terminal_size.columns - left_len - right_len) if fit else " ") + right))

        ...

    async def on_update(self, thread: int, downloaded: int):
        ...

    async def on_complete(self):
        ...

    async def on_retry(self, thread: int, attempt: int, max_attempts: int, message: str):
        ...

    async def on_error(self, message: str):
        print(f"{Color.from_name('red')}ERROR{Color.from_name('reset')} {message}")

def main():
    parser = argparse.ArgumentParser(prog="fastget", description="High-speed File Downloading Tool")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Number of download threads (default: 4)")

    arg = parser.parse_args()

    ...

    print(f"{Color.from_name('bright_green')}Downloaded{Color.from_name('reset')} to {arg.output} {Color.from_name('grey')}{human_size(arg.output.stat().st_size)}{Color.from_name('reset')}")
