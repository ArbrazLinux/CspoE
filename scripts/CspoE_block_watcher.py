#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Near-real-time Telegram notification for stake-pool blocks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.blockfrost import BlockfrostClient
from core.config import get_setting, settings
from notifications.block_watcher import PoolBlockWatcher
from notifications.telegram import TelegramClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--bootstrap-notify", action="store_true", help="notifier aussi le dernier bloc lors de la première initialisation")
    parser.add_argument("--state-file", default=str(Path(settings.data_dir) / "CspoE" / "notifications" / "block_watcher_state.json"))
    args = parser.parse_args()

    enabled = get_setting("CSPOE_TELEGRAM_BLOCKS_ENABLED", get_setting("CSPOE_TELEGRAM_ENABLED", "0")).lower() in {"1", "true", "yes", "on"}
    token = get_setting("TELEGRAM_BOT_TOKEN")
    chat_id = get_setting("TELEGRAM_CHAT_ID")

    if not enabled and not args.dry_run:
        print(json.dumps({"ok": True, "skipped": True, "reason": "telegram_blocks_disabled"}, ensure_ascii=False, indent=2))
        return 0

    client = BlockfrostClient()
    telegram = None if args.dry_run else TelegramClient(token, chat_id)
    watcher = PoolBlockWatcher(
        ticker=settings.pool_ticker,
        state_file=Path(args.state_file),
        blockfrost=client,
        telegram=telegram,
        max_pages=int(get_setting("CSPOE_TELEGRAM_BLOCK_MAX_PAGES", "10") or 10),
    )
    result = watcher.run(dry_run=args.dry_run, bootstrap_notify=args.bootstrap_notify)
    result.update({"chat_id": chat_id, "pool_id": settings.bech32_pool_id, "state_file": args.state_file})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
