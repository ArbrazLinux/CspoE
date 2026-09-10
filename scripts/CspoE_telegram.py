#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Send CspoE snapshot events to a Telegram channel."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import get_setting, settings
from notifications.telegram import TelegramClient
from notifications.watcher import TelegramWatcher
from notifications.subscribers import SubscriberStore
from notifications.personal import PersonalNotifier


def latest_pair(data_root: Path) -> tuple[Path, Path]:
    live = data_root / "pooldata" / "live.json"
    if not live.is_file():
        raise FileNotFoundError(f"live absent: {live}")
    current = json.loads(live.read_text(encoding="utf-8"))
    epoch = int(current.get("epoch", 0) or 0)
    previous = data_root / "live" / f"epoch_{epoch - 1}.json"
    if not previous.is_file():
        previous = data_root / "epochs" / f"epoch_{epoch - 1}.json"
    if not previous.is_file():
        raise FileNotFoundError(f"snapshot précédent absent: {previous}")
    return previous, live


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-message", action="store_true")
    parser.add_argument("--threshold-ada", type=float, default=float(get_setting("CSPOE_TELEGRAM_STAKE_THRESHOLD_ADA", "0") or 0))
    args = parser.parse_args()

    token = get_setting("TELEGRAM_BOT_TOKEN")
    chat_id = get_setting("TELEGRAM_CHAT_ID")
    enabled = get_setting("CSPOE_TELEGRAM_ENABLED", "0").lower() in {"1", "true", "yes", "on"}

    if args.test_message:
        if args.dry_run:
            print(json.dumps({"ok": True, "dry_run": True, "chat_id": chat_id, "text": f"✅ Test CspoE → Telegram {settings.pool_ticker}"}, ensure_ascii=False, indent=2))
            return 0
        TelegramClient(token, chat_id).send_message(
            f"✅ <b>Test CspoE → Telegram {settings.pool_ticker}</b>\n\n"
            "Le canal de notification est correctement configuré."
        )
        print(json.dumps({"ok": True, "sent": True, "chat_id": chat_id}, ensure_ascii=False, indent=2))
        return 0

    if not enabled and not args.dry_run:
        print(json.dumps({"ok": True, "skipped": True, "reason": "telegram_disabled"}, indent=2))
        return 0

    data_root = Path(args.data_root)
    previous, current = latest_pair(data_root)
    personal=None
    if get_setting("CSPOE_TELEGRAM_INTERACTIVE_ENABLED", "0").lower() in {"1","true","yes","on"} and not args.dry_run:
        db=Path(get_setting("CSPOE_TELEGRAM_SUBSCRIBERS_DB",str(data_root / "notifications" / "subscribers.sqlite3")))
        personal=PersonalNotifier(store=SubscriberStore(db),token=token,ticker=settings.pool_ticker)
    watcher = TelegramWatcher(
        ticker=settings.pool_ticker,
        token=token,
        chat_id=chat_id,
        state_file=data_root / "notifications" / "telegram_state.json",
        threshold_lovelace=max(0, int(args.threshold_ada * 1_000_000)),
        # Ownership is explicit: stake/delegator events belong to stake-watcher,
        # blocks belong to block-watcher. Snapshot Telegram handles epoch/rewards.
        include_delegator_events=False,
        include_pool_stake_events=False,
        include_block_events=False,
        personal_notifier=personal,
    )
    result = watcher.run(
        previous,
        current,
        dry_run=args.dry_run,
        epoch_manager_state_file=data_root / "epoch_manager_state.json",
        epochs_dir=data_root / "epochs",
    )
    result.update({"chat_id": chat_id, "previous": str(previous), "current": str(current)})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
