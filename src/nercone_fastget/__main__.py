import os
import sys
import math
import argparse
import asyncio
from . import fastget
from urllib.parse import urlparse
from nercone_modern.logging import ModernLogging
from nercone_modern.progressbar import ModernProgressBar

class CLIProgress(fastget.ProgressCallback):
    def __init__(self, logger: ModernLogging):
        self.logger = logger
        self.all_bar = None
        self.thread_bars = []
        self.chunk_size_display = 1024 * 128
        self.merge_accumulated = 0
        self.merge_bar = None

        self.worker_progress = []
        self.total_loaded = 0
        self.last_worker_steps = []
        self.last_total_steps = 0

    async def on_start(self, total_size: int, threads: int, http_version: str, final_url: str, verify_was_enabled: bool) -> None:
        self.logger.log(f"File size: {total_size:,} bytes")
        parsed_url = urlparse(final_url)
        protocol = "HTTPS" if parsed_url.scheme.lower() == 'https' else "HTTP"
        details = [http_version.upper()]
        if protocol == "HTTPS":
            details.append("TLS")
            details.append("Verified" if verify_was_enabled else "Unverified")
        connection_type = f"{protocol} ({', '.join(details)})"
        self.logger.log(f"Connection Type: {connection_type}")
        self.logger.log(f"Threads: {threads}")

        self.worker_progress = [0] * threads
        self.total_loaded = 0
        self.last_worker_steps = [0] * threads
        self.last_total_steps = 0

        if total_size > 0:
            total_steps = max(1, math.ceil(total_size / self.chunk_size_display))
            self.all_bar = ModernProgressBar(total=total_steps, process_name="Total", spinner_mode=False)
            self.all_bar.start()
            if threads > 1:
                part_size = total_size // threads
                for i in range(threads):
                    start = part_size * i
                    end = total_size - 1 if i == threads - 1 else start + part_size - 1
                    size_for_this_thread = end - start + 1

                    total_progress_units = max(1, math.ceil(size_for_this_thread / self.chunk_size_display))
                    bar = ModernProgressBar(total=total_progress_units, process_name=f"DL #{i+1}", spinner_mode=False)
                    bar.start()
                    self.thread_bars.append(bar)

    async def on_update(self, worker_id: int, loaded: int) -> None:
        if self.thread_bars and worker_id < len(self.thread_bars):
            self.worker_progress[worker_id] += loaded
            current_worker_steps = self.worker_progress[worker_id] // self.chunk_size_display
            steps_to_advance = current_worker_steps - self.last_worker_steps[worker_id]
            if steps_to_advance > 0:
                self.thread_bars[worker_id].update(steps_to_advance)
                self.last_worker_steps[worker_id] = current_worker_steps

        if self.all_bar:
            self.total_loaded += loaded
            current_total_steps = self.total_loaded // self.chunk_size_display
            steps_to_advance = current_total_steps - self.last_total_steps
            if steps_to_advance > 0:
                self.all_bar.update(steps_to_advance)
                self.last_total_steps = current_total_steps

    async def on_complete(self) -> None:
        if self.all_bar:
            self.all_bar.finish()

        for b in self.thread_bars:
            b.finish()

    async def on_merge_start(self, total_size: int) -> None:
        self.merge_accumulated = 0
        if total_size > 0:
            total_steps = max(1, math.ceil(total_size / self.chunk_size_display))
            self.merge_bar = ModernProgressBar(total=total_steps, process_name="Merge", spinner_mode=False)
            self.merge_bar.start()

    async def on_merge_update(self, loaded: int) -> None:
        if self.merge_bar:
            self.merge_accumulated += loaded
            steps_to_advance = self.merge_accumulated // self.chunk_size_display
            if steps_to_advance > 0:
                self.merge_bar.update(steps_to_advance)
                self.merge_accumulated %= self.chunk_size_display

    async def on_merge_complete(self) -> None:
        if self.merge_bar:
            self.merge_bar.finish()

    async def on_error(self, msg: str) -> None:
        self.logger.log(msg, "ERROR")

async def async_main() -> None:
    parser = argparse.ArgumentParser(prog='fastget', description='Modern High-Performance Downloader')
    parser.add_argument('url', help="Target URL")
    parser.add_argument('-o', '--output', help="File destination")
    parser.add_argument('-X', '--method', default='GET', choices=["GET", "POST"], help="HTTP method (GET/POST)")
    parser.add_argument('-d', '--data', help="Data for POST method")
    parser.add_argument('-H', '--header', action='append', help="Custom Headers")
    parser.add_argument('-t', '--threads', type=int, default=fastget.DEFAULT_THREADS, help="Number of threads to use for downloading")
    parser.add_argument('-p', '--print', dest='print_to_stdout', action='store_true', help="Output data directly to stdout without saving to a file")
    parser.add_argument('-s', '--storage', '--low-memory', dest='low_memory', action='store_true', help="Utilize storage efficiently to reduce memory usage during internal processes such as downloading and merging.")
    parser.add_argument('-m', '--memory', '--low-storage', dest='low_storage', action='store_true', help="Utilize memory efficiently to reduce maximum concurrent storage usage during internal processes such as downloading and merging.")
    parser.add_argument('--no-verify', action='store_true', help="In the case of HTTPS, if a secure connection cannot be established, the system will continue to operate normally.")
    parser.add_argument('--no-info', action='store_true', help="Suppresses all displays such as progress bars. If --print is used, only data is output to stdout.")
    parser.add_argument('--no-http1', action='store_true', help="Do not use HTTP/1 or HTTP/1.1")
    parser.add_argument('--no-http2', action='store_true', help="Do not use HTTP/2")

    args = parser.parse_args()

    if args.no_info:
        class DummyLogger:
            def log(self, *args, **kwargs):
                pass
        logger = DummyLogger()
        callback = fastget.ProgressCallback()
    else:
        logger = ModernLogging("fastget")
        callback = CLIProgress(logger)

    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()

    method = args.method
    if args.data and method.upper() == 'GET':
        method = 'POST'

    if args.print_to_stdout:
        if args.output:
            logger.log("Warning: Both --output and --print were specified. --output will be ignored.", "WARNING")
        output = None
    else:
        output = args.output
        if not output:
            parsed = fastget.urlparse(args.url)
            output = fastget.unquote(os.path.basename(parsed.path)) or "downloaded_file"

    http1_enabled = not args.no_http1
    http2_enabled = not args.no_http2
    if not http1_enabled and not http2_enabled:
        logger.log("Error: Cannot disable both HTTP/1 and HTTP/2.", "CRITICAL")
        return

    session = fastget.FastGetSession(
        max_threads=args.threads,
        http1=http1_enabled,
        http2=http2_enabled,
        verify=not args.no_verify
    )

    start_time = asyncio.get_running_loop().time()

    try:
        result = await session.process(
            method=method,
            url=args.url,
            output=output,
            data=args.data,
            headers=headers,
            callback=callback
        )

        if isinstance(result, str):
            end_time = asyncio.get_running_loop().time()
            duration_ms = (end_time - start_time) * 1000

            logger.log(f"Completed in {duration_ms:.2f}ms")
            logger.log(f"Saved to: {result}")
        else:
            sys.stdout.buffer.write(result.content)

    except fastget.FastGetError as e:
        logger.log(str(e), "CRITICAL")
    except Exception as e:
        logger.log(f"Unexpected error: {e}", "CRITICAL")

def main() -> None:
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass

    asyncio.run(async_main())

if __name__ == "__main__":
    main()
