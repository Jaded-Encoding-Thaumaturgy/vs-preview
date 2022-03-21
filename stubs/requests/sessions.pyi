from typing import IO, Any, AnyStr, Dict, List, Tuple

from .models import DEFAULT_REDIRECT_LIMIT as DEFAULT_REDIRECT_LIMIT
from .models import REDIRECT_STATI as REDIRECT_STATI
from .models import Response


class SessionRedirectMixin: ...

class Session(SessionRedirectMixin):
    __attrs__: Any
    headers: Any
    auth: Any
    proxies: Any
    hooks: Any
    params: Any
    stream: bool
    verify: bool
    cert: Any
    max_redirects: Any
    trust_env: bool
    cookies: Any
    adapters: Any
    def __init__(self) -> None: ...
    def __enter__(self) -> Session: ...
    def __exit__(self, *args: Any) -> None: ...
    def get(self, url: str, **kwargs: Any) -> Response: ...
    def post(self, url: str, data: Dict[Any, Any] | List[Tuple[Any, ...]] | bytes | IO[AnyStr] | None = ..., json: Any | None = ..., **kwargs: Any) -> Response: ...
    def close(self) -> None: ...
