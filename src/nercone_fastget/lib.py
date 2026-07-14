import os
import json
import httpx
import asyncio
import tempfile
from typing import Optional, Union, Dict
from pathlib import Path
from importlib.metadata import version

class Callback:
    async def on_start(self, size: int, threads: int, http_version: int, url: str):
        pass

    async def on_update(self, thread: int, downloaded: int):
        pass

    async def on_complete(self):
        pass

    async def on_error(self, message: str):
        pass

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
    async def get(url: str, threads: int = 8, headers: Dict[str, str] = {}, callback: Callback = Callback(), temp_path: Optional[Union[str, Path]] = None) -> Response:
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

        try:
            limits = httpx.Limits(max_connections=threads + 2, max_keepalive_connections=threads + 2)
            async with httpx.AsyncClient(http2=True, limits=limits, follow_redirects=True) as client:
                head = await client.head(url, headers=headers)
                http_version = 2 if head.http_version == "HTTP/2" else 1
                content_length = int(head.headers.get("content-length", 0))
                supports_range = head.headers.get("accept-ranges", "none").lower() != "none" and content_length > 0

                if not supports_range or threads <= 1:
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
                ranges = [(i, i * chunk_size, (i + 1) * chunk_size - 1 if i < threads - 1 else content_length - 1) for i in range(threads)]

                with open(temp_path, "wb") as file:
                    file.truncate(content_length)

                async def download_chunk(index: int, start: int, end: int):
                    chunk_headers = {**headers, "Range": f"bytes={start}-{end}"}
                    async with client.stream("GET", url, headers=chunk_headers) as stream:
                        downloaded = 0
                        with open(temp_path, "r+b") as file:
                            file.seek(start)
                            async for piece in stream.aiter_bytes():
                                file.write(piece)
                                downloaded += len(piece)
                                await callback.on_update(index, downloaded)

                await asyncio.gather(*[download_chunk(index, start, end) for index, start, end in ranges])
                await callback.on_complete()

                return Response(
                    url=url,
                    http_version=http_version,
                    status_code=200,
                    headers=dict(head.headers),
                    content=temp_path.read_bytes() if owns_temp_file else None
                )

        except Exception as e:
            await callback.on_error(repr(e))
            raise
        finally:
            if owns_temp_file:
                temp_path.unlink(missing_ok=True)
