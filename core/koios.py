# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Minimal Koios client used only as an independent block-count check."""
from __future__ import annotations

import json
import time
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import settings
from .version import USER_AGENT


class KoiosError(RuntimeError):
    pass


class KoiosClient:
    def __init__(
        self,
        pool_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 20,
        retries: int = 2,
    ) -> None:
        self.pool_id = pool_id or settings.bech32_pool_id
        self.base_url = (base_url or settings.koios_base).rstrip("/")
        self.timeout = int(timeout)
        self.retries = int(retries)

    def _get(self, path: str, params: dict[str, str]) -> Any:
        url = self.base_url + "/" + path.lstrip("/") + "?" + urlencode(params)
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                )
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if 400 <= exc.code < 500:
                    break
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(attempt + 1)
        raise KoiosError(f"Koios request failed: GET {path}: {last_error}")

    def pool_blocks(self, epoch: int) -> list[dict[str, Any]]:
        if not self.pool_id:
            raise KoiosError("BECH32_POOL_ID absent")
        rows: list[dict[str, Any]] = []
        offset = 0
        page_size = 1000
        for _ in range(settings.api_max_pages):
            page = self._get(
                "pool_blocks",
                {
                    "_pool_bech32": self.pool_id,
                    "_epoch_no": str(int(epoch)),
                    "limit": str(page_size),
                    "offset": str(offset),
                },
            )
            if not isinstance(page, list):
                raise KoiosError("Koios pool_blocks did not return a list")
            rows.extend(row for row in page if isinstance(row, dict))
            if len(page) < page_size:
                return rows
            offset += page_size
        raise KoiosError("Koios pool_blocks pagination limit exceeded")

