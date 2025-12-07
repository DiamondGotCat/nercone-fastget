import os
import math
import argparse
import asyncio
import sys
from . import fastget
from urllib.parse import urlparse, unquote
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
        if total_size > 0:
            total_steps = max(1, math.ceil(total_size / self.chunk_size_display))
            self.all_bar = ModernProgressBar(total=total_steps, process_name="Total", spinner_mode=False)
            self.all_bar.start()
            if threads > 1:
                part_size = total_size // threads
                for i in range(threads):
                    p_steps = max(1, math.ceil(part_size / self.chunk_size_display))
                    bar = ModernProgressBar(total=p_steps, process_name=f"DL #{i+1}", spinner_mode=False)
                    bar.start()
                    self.thread_bars.append(bar)

    async def on_update(self, worker_id: int, loaded: int) -> None:
        if self.thread_bars and worker_id < len(self.thread_bars):
            self.thread_bars[worker_id].update()

        if self.all_bar:
            self.all_bar.update()

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
            while self.merge_accumulated >= self.chunk_size_display:
                self.merge_bar.update()
                self.merge_accumulated -= self.chunk_size_display

    async def on_merge_complete(self) -> None:
        if self.merge_bar:
            self.merge_bar.finish()

    async def on_error(self, msg: str) -> None:
        if self.logger:
            self.logger.log(msg, "ERROR")

async def async_main() -> None:
    parser = argparse.ArgumentParser(prog='fastget', description='Modern High-Performance Downloader')
    parser.add_argument('url', help="Target URL")

    parser.add_argument('-o', '--output', help="File destination")
    parser.add_argument('-X', '--method', default='GET', help="HTTP method (GET/POST)")
    parser.add_argument('-d', '--data', help="Data for POST method")
    parser.add_argument('-H', '--header', action='append', help="Custom Headers")
    parser.add_argument('-t', '--threads', type=int, default=fastget.DEFAULT_THREADS, help="Number of threads to use for downloading")
    parser.add_argument('-p', '--print', action='store_true', help="Output data directly to stdout without saving to a file")

    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument('-s', '--storage', '--low-memory', action='store_const', const='storage', dest='strategy', help="Avoid using memory as much as possible, and perform tasks such as saving destinations and merging on received data only on the storage device as much as possible. (default)")
    strategy_group.add_argument('-m', '--memory', '--low-storage', action='store_const', const='memory', dest='strategy', help="Utilize memory efficiently to reduce maximum concurrent storage usage.")
    parser.set_defaults(strategy='storage')

    parser.add_argument('--no-verify', action='store_true', help="In the case of HTTPS, if a secure connection cannot be established, the system will continue to operate normally.")
    parser.add_argument('--no-info', action='store_true', help="Suppresses all displays such as progress bars. If --print is used, only data is output to stdout.")

    parser.add_argument('--no-http1', action='store_true', help="Do not use HTTP/1 or HTTP/1.1")
    parser.add_argument('--no-http2', action='store_true', help="Do not use HTTP/2")
    parser.add_argument('--no-http3', action='store_true', help="Do not use HTTP/3")

    args = parser.parse_args()

    if args.print and args.output:
        parser.error("If -p/--print is specified, -o/--output cannot be specified.")

    if args.no_info:
        logger = None
        callback = fastget.ProgressCallback()
    else:
        logger = ModernLogging("FastGet")
        callback = CLIProgress(logger)

    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()

    method = args.method.upper()
    if args.data:
        method = 'POST'

    session = fastget.FastGetSession(
        max_threads=args.threads,
        http1=not args.no_http1,
        http2=not args.no_http2,
        http3=not args.no_http3,
        verify=not args.no_verify
    )

    start_time = 0
    if logger:
        start_time = asyncio.get_running_loop().time()

    try:
        if args.print:
            result = await session.process(
                method=method, 
                url=args.url, 
                data=args.data, 
                headers=headers, 
                callback=callback
            )
            sys.stdout.buffer.write(result.content)
        else:
            output = args.output
            if not output:
                parsed = urlparse(args.url)
                output = unquote(os.path.basename(parsed.path)) or "downloaded_file"

            path = await session.process(
                method=method, 
                url=args.url, 
                output=output, 
                data=args.data, 
                headers=headers, 
                callback=callback,
                strategy=args.strategy
            )
            if logger:
                end_time = asyncio.get_running_loop().time()
                duration_ms = (end_time - start_time) * 1000
                logger.log(f"Completed in {duration_ms:.2f}ms")
                logger.log(f"Saved to: {path}")

    except fastget.FastGetError as e:
        if logger:
            logger.log(str(e), "CRITICAL")
        else:
            print(f"Error: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        if logger:
            logger.log(f"Unexpected error: {e}", "CRITICAL")
        else:
            print(f"Unexpected error: {e}", file=sys.stderr, flush=True)

def main() -> None:
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
