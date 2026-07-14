import os
import json
import httpx
import asyncio
import tempfile
import time
from typing import Optional, Union, Dict
from pathlib import Path
from importlib.metadata import version

class Callback:
    async def on_start(self, size: int, threads: int, http_version: int, url: str):
        pass

    async def on_update(self, thread: int, downloaded: int):
        pass

    async def on_retry(self, thread: int, attempt: int, max_attempts: int, message: str):
        pass

    async def on_complete(self):
        pass

    async def on_error(self, message: str):
        pass

class ChunkRange:
    def __init__(self, index: int, start: int, end: int):
        self.index = index
        self.start = start
        self.end = end

    @property
    def size(self) -> int:
        return self.end - self.start + 1

class ProgressState:
    save_interval = 1.0 # seconds

    def __init__(self, path: Path, url: str, content_length: int, threads: int):
        self.path = path
        self.url = url
        self.content_length = content_length
        self.threads = threads
        self.chunks: Dict[int, int] = {}
        self.last_saved_time = 0.0

    def load_resumable(self) -> bool:
        if not self.path.exists():
            return False
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return False

        matches = (
            data.get("url") == self.url and
            data.get("content_length") == self.content_length and
            data.get("threads") == self.threads
        )
        if not matches:
            return False

        self.chunks = {int(index): downloaded for index, downloaded in data.get("chunks", {}).items()}
        return True

    def resume_offset(self, index: int) -> int:
        return self.chunks.get(index, 0)

    def mark(self, index: int, downloaded: int):
        self.chunks[index] = downloaded
        now = time.monotonic()
        if now - self.last_saved_time >= self.save_interval:
            self.last_saved_time = now
            self.save()

    def save(self):
        self.path.write_text(json.dumps({
            "url": self.url,
            "content_length": self.content_length,
            "threads": self.threads,
            "chunks": self.chunks
        }))

    def cleanup(self):
        self.path.unlink(missing_ok=True)

class Response:
    def __init__(self, url: str, http_version: int, status_code: int, headers: Dict[str, str], content: Optional[bytes]):
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

class FastGet:
    @staticmethod
    async def get(url: str, threads: int = 8, headers: Dict[str, str] = {}, callback: Callback = Callback(), temp_path: Optional[Union[str, Path]] = None, max_retries: int = 5, retry_backoff: float = 1.0) -> Response:
        headers_arg = headers
        headers = {"User-Agent": f"FastGet/{version('nercone-fastget')} (+https://github.com/nercone-dev/fastget/)"}
        headers.update(headers_arg)

        owns_temp_file = temp_path is None
        if owns_temp_file:
            fd, path = tempfile.mkstemp(prefix="fastget-")
            os.close(fd)
            temp_path = Path(path)
        else:
            temp_path = Path(temp_path)

        progress: Optional[ProgressState] = None

        try:
            limits = httpx.Limits(max_connections=threads + 2, max_keepalive_connections=threads + 2)
            async with httpx.AsyncClient(http2=True, limits=limits, follow_redirects=True) as client:
                head = await client.head(url, headers=headers)
                http_version = 2 if head.http_version == "HTTP/2" else 1
                content_length = int(head.headers.get("content-length", 0))
                supports_range = head.headers.get("accept-ranges", "none").lower() != "none" and content_length > 0

                if not supports_range:
                    await callback.on_start(content_length, 1, http_version, url)
                    downloaded = 0
                    with open(temp_path, "wb") as file:
                        async with client.stream("GET", url, headers=headers) as stream:
                            async for piece in stream.aiter_bytes():
                                file.write(piece)
                                downloaded += len(piece)
                                await callback.on_update(0, downloaded)
                    await callback.on_complete()
                    return Response(
                        url=str(stream.url),
                        http_version=http_version,
                        status_code=stream.status_code,
                        headers=dict(stream.headers),
                        content=temp_path.read_bytes() if owns_temp_file else None
                    )

                await callback.on_start(content_length, threads, http_version, url)

                chunk_size = content_length // threads
                ranges = [
                    ChunkRange(i, i * chunk_size, (i + 1) * chunk_size - 1 if i < threads - 1 else content_length - 1)
                    for i in range(threads)
                ]

                progress_path = Path(f"{temp_path}.progress")
                progress = ProgressState(progress_path, url, content_length, threads)
                resumable = (progress.load_resumable() and temp_path.exists() and temp_path.stat().st_size == content_length)
                if not resumable:
                    progress.chunks = {}
                    with open(temp_path, "wb") as file:
                        file.truncate(content_length)

                async def download_chunk(chunk: ChunkRange):
                    downloaded = progress.resume_offset(chunk.index)
                    if downloaded >= chunk.size:
                        await callback.on_update(chunk.index, downloaded)
                        return

                    attempt = 0
                    while True:
                        try:
                            range_start = chunk.start + downloaded
                            chunk_headers = {**headers, "Range": f"bytes={range_start}-{chunk.end}"}
                            async with client.stream("GET", url, headers=chunk_headers) as stream:
                                with open(temp_path, "r+b") as file:
                                    file.seek(range_start)
                                    async for piece in stream.aiter_bytes():
                                        file.write(piece)
                                        downloaded += len(piece)
                                        await callback.on_update(chunk.index, downloaded)
                                        progress.mark(chunk.index, downloaded)
                            return
                        except httpx.TransportError as error:
                            attempt += 1
                            if attempt > max_retries:
                                raise
                            await callback.on_retry(chunk.index, attempt, max_retries, repr(error))
                            await asyncio.sleep(min(retry_backoff * (2 ** (attempt - 1)), 30))

                await asyncio.gather(*[download_chunk(chunk) for chunk in ranges])
                await callback.on_complete()
                progress.cleanup()

                return Response(
                    url=url,
                    http_version=http_version,
                    status_code=200,
                    headers=dict(head.headers),
                    content=temp_path.read_bytes() if owns_temp_file else None
                )

        except Exception as e:
            if progress is not None:
                progress.save()
            await callback.on_error(repr(e))
            raise
        finally:
            if owns_temp_file:
                temp_path.unlink(missing_ok=True)
                if progress is not None:
                    progress.cleanup()
