import os
import json
import asyncio
import threading
import http.client
import urllib.error
import urllib.request
from typing import Optional, Union, Literal, Dict, List, Tuple
from dataclasses import dataclass
from importlib.metadata import version

HTTPVersion = Literal["HTTP/1.0", "HTTP/1.1", "HTTP/2.0", "HTTP/3.0"]

class Callback:
    async def on_start(self, filesize: int, threads: int, url: str, http_version: HTTPVersion):
        pass

    async def on_update(self, thread: int, downloaded: int):
        pass

    async def on_retry(self, thread: int, attempt: int, max_attempts: int):
        pass

    async def on_complete(self):
        pass

    async def on_error(self, reason: str):
        pass

class Response:
    def __init__(self, url: str, http_version: HTTPVersion, status_code: int, headers: Dict[str, str], content: Optional[bytes]):
        self.url = url
        self.http_version = http_version
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode()

    @property
    def json(self) -> Union[dict, list]:
        return json.loads(self.text)

@dataclass
class Probe:
    status: int
    http_version: HTTPVersion
    headers: Dict[str, str]
    filesize: int
    resumable: bool

class Destination:
    def write(self, offset: int, data: bytes):
        raise NotImplementedError

    def content(self) -> Optional[bytes]:
        return None

    def close(self):
        pass

class FileDestination(Destination):
    def __init__(self, filepath: str, filesize: int):
        self.file = open(filepath, "wb")
        if filesize:
            self.file.truncate(filesize)
        self.lock = threading.Lock()

    def write(self, offset: int, data: bytes):
        with self.lock:
            self.file.seek(offset)
            self.file.write(data)

    def close(self):
        self.file.close()

class MemoryDestination(Destination):
    def __init__(self, filesize: int):
        self.buffer = bytearray(filesize)
        self.lock = threading.Lock()

    def write(self, offset: int, data: bytes):
        with self.lock:
            end = offset + len(data)
            if end > len(self.buffer):
                self.buffer.extend(bytes(end - len(self.buffer)))
            self.buffer[offset:end] = data

    def content(self) -> Optional[bytes]:
        return bytes(self.buffer)

class FastGet:
    @staticmethod
    def format_version(code: int) -> HTTPVersion:
        if code == 10:
            return "HTTP/1.0"
        elif code == 11:
            return "HTTP/1.1"

    @staticmethod
    def fetch(url: str, headers: Dict[str, str], byte_range: Optional[Tuple[int, Optional[int]]] = None, timeout: float = 30) -> http.client.HTTPResponse:
        request_headers = dict(headers)
        if byte_range is not None:
            start, end = byte_range
            request_headers["Range"] = f"bytes={start}-{end}" if end is not None else f"bytes={start}-"
        request = urllib.request.Request(url, headers=request_headers, method="GET")
        return urllib.request.urlopen(request, timeout=timeout)

    @staticmethod
    def probe(url: str, headers: Dict[str, str]) -> Probe:
        with FastGet.fetch(url, headers, byte_range=(0, 0)) as response:
            status = response.status
            http_version = FastGet.format_version(response.version)
            response_headers = dict(response.headers)

        if status == 206:
            total = response_headers.get("Content-Range", "").rsplit("/", 1)[-1]
            filesize = int(total) if total.isdigit() else 0
            resumable = filesize > 0
        else:
            content_length = response_headers.get("Content-Length")
            filesize = int(content_length) if content_length and content_length.isdigit() else 0
            resumable = False

        return Probe(status, http_version, response_headers, filesize, resumable)

    @staticmethod
    def split(filesize: int, threads: int) -> List[Tuple[int, int]]:
        base, remainder = divmod(filesize, threads)
        ranges = []
        start = 0
        for index in range(threads):
            size = base + (1 if index < remainder else 0)
            ranges.append((start, start + size - 1))
            start += size
        return ranges

    @staticmethod
    async def download(url: str, *, loop: asyncio.AbstractEventLoop, headers: Dict[str, str], thread: int, byte_range: Tuple[int, Optional[int]], resumable: bool, destination: Destination, callback: Callback, timeout: float = 30, chunk_size: int = 256 * 1024, max_retries: int = 3, retry_delay: float = 1):
        start, end = byte_range
        attempt = 0

        while True:
            offset = start
            downloaded = 0

            try:
                response = await loop.run_in_executor(None, FastGet.fetch, url, headers, byte_range if resumable else None, timeout)
                try:
                    while True:
                        data = await loop.run_in_executor(None, response.read, chunk_size)
                        if not data:
                            break
                        await loop.run_in_executor(None, destination.write, offset, data)
                        offset += len(data)
                        downloaded += len(data)
                        await callback.on_update(thread, downloaded)
                finally:
                    response.close()
                return
            except urllib.error.HTTPError as error:
                await callback.on_error(f"Thread {thread}: {error}")
                raise
            except (OSError, http.client.HTTPException) as error:
                attempt += 1
                if attempt > max_retries:
                    await callback.on_error(f"Thread {thread}: {error}")
                    raise
                await callback.on_retry(thread, attempt, max_retries)
                await asyncio.sleep(retry_delay * attempt)

    @staticmethod
    async def get(url: str, threads: int = 4, headers: Dict[str, str] = {}, callback: Callback = Callback(), filepath: Optional[str] = None, timeout: float = 30, chunk_size: int = 256 * 1024, max_retries: int = 3, retry_delay: float = 1) -> Response:
        headers = {**{"User-Agent": f"FastGet/{version('nercone-fastget')} (+https://github.com/nercone-dev/fastget/)"}, **headers}

        loop = asyncio.get_running_loop()

        attempt = 0
        while True:
            try:
                probe = await loop.run_in_executor(None, FastGet.probe, url, headers)
                break
            except urllib.error.HTTPError as error:
                await callback.on_error(str(error))
                raise
            except (OSError, http.client.HTTPException) as error:
                attempt += 1
                if attempt > max_retries:
                    await callback.on_error(str(error))
                    raise
                await callback.on_retry(0, attempt, max_retries)
                await asyncio.sleep(retry_delay * attempt)

        threads = max(1, threads)
        if probe.resumable:
            threads = min(threads, probe.filesize)
        else:
            threads = 1

        await callback.on_start(probe.filesize, threads, url, probe.http_version)

        destination = FileDestination(filepath, probe.filesize) if filepath is not None else MemoryDestination(probe.filesize)

        ranges = FastGet.split(probe.filesize, threads) if threads > 1 else [(0, probe.filesize - 1 if probe.filesize else None)]

        tasks = [asyncio.create_task(FastGet.download(url, loop=loop, headers=headers, thread=thread, byte_range=byte_range, resumable=probe.resumable, destination=destination, callback=callback)) for thread, byte_range in enumerate(ranges, start=1)]

        try:
            await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            destination.close()
            raise

        await callback.on_complete()

        content = destination.content() if filepath is None else None
        destination.close()

        filesize = probe.filesize or (len(content) if content is not None else os.path.getsize(filepath))

        response_headers = dict(probe.headers)
        response_headers.pop("Content-Range", None)
        response_headers["Content-Length"] = str(filesize)

        return Response(url, probe.http_version, 200, response_headers, content)
