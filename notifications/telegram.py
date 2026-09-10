# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Minimal Telegram Bot API client for CspoE notifications."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class TelegramError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramClient:
    token: str
    chat_id: str
    timeout: int = 15

    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text: str, *, disable_web_page_preview: bool = True, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN absent")
        if not self.chat_id:
            raise TelegramError("TELEGRAM_CHAT_ID absent")
        body = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        response = requests.post(
            f"{self.api_base}/sendMessage",
            json=body,
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramError(f"réponse Telegram non JSON: HTTP {response.status_code}") from exc
        if not response.ok or not payload.get("ok"):
            description = payload.get("description") or f"HTTP {response.status_code}"
            raise TelegramError(f"Telegram: {description}")
        return payload
