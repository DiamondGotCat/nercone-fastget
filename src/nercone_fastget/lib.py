import json
import httpx
import asyncio
from importlib.metadata import version

class Callback:
    async def on_start(self, size: int, threads: int, http_version: int, url: str) -> None:
        pass

    async def on_update(self, thread: int, downloaded: int) -> None:
        pass

    async def on_complete(self) -> None:
        pass

    async def on_merge_start(self, size: int) -> None:
        pass

    async def on_merge_update(self, downloaded: int) -> None:
        pass

    async def on_merge_complete(self) -> None:
        pass

    async def on_error(self, message: str) -> None:
        pass

class Response:
    def __init__(self, url: str, http_version: int, status_code: int, headers: dict[str, str], content: bytes):
        self.url = url
        self.http_version = http_version
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode()

    @property
    def json(self) -> dict | list:
        return json.loads(self.text)

class FastGet:
    @staticmethod
    async def get(url: str, threads: int = 8, headers: dict[str, str] = {}, callback: Callback = Callback()) -> Response:
        headers = {"User-Agent": f"FastGet/{version('nercone-fastget')} (+https://github.com/nercone-dev/fastget/)"} | headers
        try:
            limits = httpx.Limits(max_connections=threads + 2, max_keepalive_connections=threads + 2)
            async with httpx.AsyncClient(http2=True, limits=limits, follow_redirects=True) as client:
                head = await client.head(url, headers=headers)
                http_version = 2 if head.http_version == "HTTP/2" else 1
                content_length = int(head.headers.get("content-length", 0))
                supports_range = head.headers.get("accept-ranges", "none").lower() != "none" and content_length > 0

                if not supports_range or threads <= 1:
                    await callback.on_start(content_length, 1, http_version, url)
                    data = bytearray()
                    async with client.stream("GET", url, headers=headers) as stream:
                        async for piece in stream.aiter_bytes():
                            data += piece
                            await callback.on_update(0, len(data))
                    await callback.on_complete()
                    return Response(
                        url=str(stream.url),
                        http_version=http_version,
                        status_code=stream.status_code,
                        headers=dict(stream.headers),
                        content=bytes(data)
                    )

                await callback.on_start(content_length, threads, http_version, url)

                chunk_size = content_length // threads
                ranges = [(i, i * chunk_size, (i + 1) * chunk_size - 1 if i < threads - 1 else content_length - 1) for i in range(threads)]
                chunks: list[bytes | None] = [None] * threads

                async def download_chunk(index: int, start: int, end: int) -> None:
                    chunk_headers = {**headers, "Range": f"bytes={start}-{end}"}
                    async with client.stream("GET", url, headers=chunk_headers) as stream:
                        data = bytearray()
                        async for piece in stream.aiter_bytes():
                            data += piece
                            await callback.on_update(index, len(data))
                        chunks[index] = bytes(data)

                await asyncio.gather(*[download_chunk(index, start, end) for index, start, end in ranges])
                await callback.on_complete()

                total = sum(len(c) for c in chunks)  # type: ignore[arg-type]
                await callback.on_merge_start(total)

                merged = bytearray()
                for chunk in chunks:
                    merged += chunk  # type: ignore[operator]
                    await callback.on_merge_update(len(merged))

                await callback.on_merge_complete()

                return Response(
                    url=url,
                    http_version=http_version,
                    status_code=200,
                    headers=dict(head.headers),
                    content=bytes(merged)
                )

        except Exception as e:
            await callback.on_error(str(e))
            raise
