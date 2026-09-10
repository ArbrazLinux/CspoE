# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Near-real-time stake-pool block detection for Telegram.

This component is deliberately outside the canonical epoch pipeline. It reads
Blockfrost, keeps its own notification cursor and never writes epoch archives.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.blockfrost import BlockfrostClient
from .telegram import TelegramClient
from .templates import render_realtime_block


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _hash_of(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("hash") or "")
    return ""


def _height(block: dict[str, Any]) -> int:
    try:
        return int(block.get("height") or 0)
    except (TypeError, ValueError):
        return 0


class PoolBlockWatcher:
    def __init__(
        self,
        *,
        ticker: str,
        state_file: Path,
        blockfrost: BlockfrostClient | None = None,
        telegram: TelegramClient | None = None,
        max_pages: int = 10,
        page_size: int = 100,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.ticker = ticker
        self.state_file = state_file
        self.blockfrost = blockfrost or BlockfrostClient()
        self.telegram = telegram
        self.max_pages = max(1, int(max_pages))
        self.page_size = max(1, min(int(page_size), 100))
        self.now = now

    def _list_hashes(self, last_hash: str = "") -> tuple[list[str], bool]:
        """Return hashes newer than last_hash, newest first, and whether cursor was seen."""
        found = False
        out: list[str] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            rows = self.blockfrost.pool_blocks(page=page, count=self.page_size, order="desc")
            if not isinstance(rows, list):
                raise RuntimeError("Réponse Blockfrost pool blocks invalide")
            if not rows:
                break
            for row in rows:
                h = _hash_of(row)
                if not h or h in seen:
                    continue
                seen.add(h)
                if last_hash and h == last_hash:
                    found = True
                    return out, found
                out.append(h)
            if len(rows) < self.page_size:
                break
        return out, found

    def run(self, *, dry_run: bool = False, bootstrap_notify: bool = False) -> dict[str, Any]:
        state = _load_json(self.state_file)
        last_hash = str(state.get("last_hash") or "")
        last_height = int(state.get("last_height") or 0)
        hashes, cursor_found = self._list_hashes(last_hash)

        # First run establishes a baseline and intentionally does not replay old blocks.
        if not last_hash:
            if not hashes:
                return {"ok": True, "bootstrap": True, "blocks_seen": 0, "pending": 0, "messages": []}
            latest = self.blockfrost.block(hashes[0])
            baseline = {
                "last_hash": str(latest.get("hash") or hashes[0]),
                "last_height": _height(latest),
                "last_slot": latest.get("slot"),
                "last_epoch": latest.get("epoch"),
                "last_time": latest.get("time"),
                "updated_at": int(self.now()),
            }
            messages: list[dict[str, Any]] = []
            if bootstrap_notify:
                text = render_realtime_block(latest, ticker=self.ticker)
                messages.append({"hash": baseline["last_hash"], "text": text})
                if not dry_run and self.telegram:
                    self.telegram.send_message(text)
            if not dry_run:
                _atomic_json(self.state_file, baseline)
            return {
                "ok": True,
                "bootstrap": True,
                "blocks_seen": len(hashes),
                "pending": 1 if bootstrap_notify else 0,
                "messages": messages,
                "state": baseline,
            }

        # If the cursor is older than the bounded listing window, details/heights keep
        # us from replaying historical blocks. A pool cannot normally mint 1000 blocks
        # between one-minute checks, but this also makes manual downtime recovery safe.
        candidates: list[dict[str, Any]] = []
        for h in hashes:
            block = self.blockfrost.block(h)
            if not isinstance(block, dict):
                continue
            if last_height and _height(block) <= last_height:
                continue
            candidates.append(block)

        # Blockfrost list is descending. Telegram should read chronologically.
        candidates.sort(key=lambda b: (_height(b), int(b.get("slot") or 0)))
        messages: list[dict[str, Any]] = []
        newest_state = dict(state)
        for block in candidates:
            h = str(block.get("hash") or "")
            if not h:
                continue
            text = render_realtime_block(block, ticker=self.ticker)
            messages.append({"hash": h, "height": _height(block), "text": text})
            if not dry_run and self.telegram:
                self.telegram.send_message(text)
            newest_state = {
                "last_hash": h,
                "last_height": _height(block),
                "last_slot": block.get("slot"),
                "last_epoch": block.get("epoch"),
                "last_time": block.get("time"),
                "updated_at": int(self.now()),
            }
            if not dry_run:
                _atomic_json(self.state_file, newest_state)

        return {
            "ok": True,
            "bootstrap": False,
            "cursor_found": cursor_found,
            "blocks_seen": len(hashes),
            "pending": len(candidates),
            "messages": messages,
            "state": newest_state,
        }
