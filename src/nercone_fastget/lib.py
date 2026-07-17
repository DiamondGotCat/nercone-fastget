import json
from typing import Optional, Union, Literal, Dict
from importlib.metadata import version

class Callback:
    async def on_start(self, filesize: int, threads: int, url: str, http_version: Literal["HTTP/1.0", "HTTP/1.1", "HTTP/2.0", "HTTP/3.0"]):
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
    def __init__(self, url: str, http_version: Literal["HTTP/1.0", "HTTP/1.1", "HTTP/2.0", "HTTP/3.0"], status_code: int, headers: Dict[str, str], content: Optional[bytes]):
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
    async def get(url: str, threads: int = 4, headers: Dict[str, str] = {}, callback: Callback = Callback(), filepath: Optional[str] = None) -> Response:
        headers = {**{"User-Agent": f"FastGet/{version('nercone-fastget')} (+https://github.com/nercone-dev/fastget/)"}, **headers}
        ...
