# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""CspoE epoch manager: one safe N-2 through N reconciliation path."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .CspoE_chain import CspoEChainSource
from .CspoE_finalizer import FinalizationError
from .CspoE_reward_reconciler import CspoERewardReconciler
from .config import settings
from .version import ENGINE_VERSION


class EpochManagerError(RuntimeError):
    pass


class CspoEEpochManager:
    VERSION = ENGINE_VERSION

    WINDOW_START_MINUTE = 21 * 60 + 35
    SECURITY_MINUTE = 21 * 60 + 40
    BOUNDARY_MINUTE = 21 * 60 + 45
    DEADLINE_MINUTE = 22 * 60 + 15

    def __init__(
        self,
        pool_id: Optional[str] = None,
        data_root: str | Path = Path(settings.data_dir) / "CspoE",
        live_dir: str | Path | None = None,
        archive_dir: str | Path | None = None,
        state_file: str | Path | None = None,
        awards_file: str | Path | None = None,
        finalization_reports_dir: str | Path | None = None,
        source: Optional[CspoEChainSource] = None,
    ) -> None:
        self.pool_id = pool_id or settings.bech32_pool_id
        self.pool_first_epoch = int(settings.pool_first_epoch)
        if self.pool_first_epoch <= 0:
            raise EpochManagerError(
                "POOL_FIRST_EPOCH doit contenir la première epoch active du pool"
            )
        if not self.pool_id:
            raise EpochManagerError("BECH32_POOL_ID n'est pas configuré")
        self.data_root = Path(data_root)
        self.live_dir = Path(live_dir) if live_dir else self.data_root / "live"
        self.archive_dir = Path(archive_dir) if archive_dir else self.data_root / "epochs"
        self.state_file = (
            Path(state_file) if state_file else self.data_root / "epoch_manager_state.json"
        )
        self.awards_file = (
            Path(awards_file) if awards_file else self.data_root.parent / "awards.json"
        )
        self.finalization_reports_dir = Path(
            finalization_reports_dir or self.data_root / "finalization_reports"
        )

        state_hint: dict[str, Any] = {}
        if self.state_file.is_file():
            try:
                loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
                state_hint = loaded if isinstance(loaded, dict) else {}
            except Exception:
                state_hint = {}
        protected_hint = state_hint.get("initialization_protected_end")
        if protected_hint is None:
            protected_hint = state_hint.get("last_rewards_settled_epoch")
        try:
            self.historical_protection_end = int(protected_hint)
        except (TypeError, ValueError):
            self.historical_protection_end = self.pool_first_epoch - 1

        self.live_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.finalization_reports_dir.mkdir(parents=True, exist_ok=True)

        self.source = source or CspoEChainSource(self.pool_id)
        self.reward_reconciler = CspoERewardReconciler(
            pool_id=self.pool_id,
            data_root=self.data_root,
            live_dir=self.live_dir,
            archive_dir=self.archive_dir,
            state_file=self.state_file,
            awards_file=self.awards_file,
            reports_dir=self.finalization_reports_dir,
            start_epoch=self.pool_first_epoch,
            historical_protection_end=self.historical_protection_end,
            source=self.source,
        )

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def transition_window(cls, now: Optional[datetime] = None) -> dict[str, Any]:
        now = now or cls.now_utc()
        minute = now.hour * 60 + now.minute
        if minute < cls.WINDOW_START_MINUTE:
            status = "before_window"
        elif minute < cls.SECURITY_MINUTE:
            status = "pre_transition"
        elif minute < cls.BOUNDARY_MINUTE:
            status = "security_snapshot"
        elif minute <= cls.DEADLINE_MINUTE:
            status = "confirmation_window"
        else:
            status = "after_deadline"
        return {
            "status": status,
            "now_utc": now.isoformat(),
            "start": "21:35 UTC",
            "security_check": "21:40 UTC",
            "theoretical_boundary": "21:45 UTC",
            "deadline": "22:15 UTC",
            "source_of_truth": "Blockfrost observed epoch",
            "confirmation_required": True,
            "finalization_policy": "rebuild every unsettled epoch through live N transactionally",
        }

    def _default_state(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "last_collected_epoch": None,
            "last_finalized_epoch": None,
            "last_chain_finalized_epoch": None,
            "last_rewards_settled_epoch": None,
            "pool_first_epoch": self.pool_first_epoch,
            "initialization_protected_end": self.pool_first_epoch - 1,
            "updated_at": None,
            "transition": {"status": "idle"},
            "reward_reconciliation": {"status": "idle"},
        }

    def _read_state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return self._default_state()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EpochManagerError(f"état CspoE illisible: {self.state_file}: {exc}") from exc
        if not isinstance(data, dict):
            raise EpochManagerError("état CspoE invalide: objet JSON attendu")
        data.setdefault("transition", {})
        data.setdefault("reward_reconciliation", {})
        data.setdefault("last_chain_finalized_epoch", data.get("last_finalized_epoch"))
        data.setdefault("last_rewards_settled_epoch", None)
        data.setdefault("pool_first_epoch", self.pool_first_epoch)
        protected = data.get("initialization_protected_end")
        if protected is None:
            protected = data.get("last_rewards_settled_epoch")
        if protected is None:
            protected = self.pool_first_epoch - 1
        try:
            data["pool_first_epoch"] = int(data["pool_first_epoch"])
            data["initialization_protected_end"] = int(protected)
        except (TypeError, ValueError) as exc:
            raise EpochManagerError("bornes d'initialisation invalides dans l'état") from exc
        if data["pool_first_epoch"] != self.pool_first_epoch:
            raise EpochManagerError(
                "POOL_FIRST_EPOCH diffère de la valeur enregistrée dans l'état CspoE"
            )
        for key in (
            "last_collected_epoch",
            "last_finalized_epoch",
            "last_chain_finalized_epoch",
            "last_rewards_settled_epoch",
        ):
            value = data.get(key)
            if value is None:
                continue
            try:
                data[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise EpochManagerError(f"état CspoE invalide: {key}={value!r}") from exc
        settled = data.get("last_rewards_settled_epoch")
        finalized = data.get("last_chain_finalized_epoch")
        collected = data.get("last_collected_epoch")
        if settled is not None and finalized is not None and settled > finalized:
            raise EpochManagerError("état CspoE incohérent: settled > finalized")
        if finalized is not None and collected is not None and finalized >= collected:
            raise EpochManagerError("état CspoE incohérent: finalized >= collected")
        data["version"] = self.VERSION
        return data

    @staticmethod
    def _epoch_inventory(directory: Path) -> tuple[list[int], list[str]]:
        epochs: list[int] = []
        extras: list[str] = []
        for path in sorted(directory.iterdir()) if directory.is_dir() else []:
            if not path.is_file():
                continue
            match = re.fullmatch(r"epoch_(\d+)\.json", path.name)
            if match:
                epochs.append(int(match.group(1)))
            else:
                extras.append(path.name)
        return sorted(epochs), extras

    def observe_epoch(self) -> int:
        return int(self.source.observed_epoch())

    def reconcile_reward_window(
        self,
        observed_epoch: int,
        *,
        write: bool = False,
        report_file: str | Path | None = None,
    ) -> dict[str, Any]:
        try:
            return self.reward_reconciler.reconcile(
                int(observed_epoch),
                write=write,
                report_file=Path(report_file) if report_file else None,
            )
        except FinalizationError as exc:
            return {
                "ok": False,
                "version": self.VERSION,
                "mode": "reward_window_reconciliation",
                "observed_epoch": int(observed_epoch),
                "written": False,
                "error": str(exc),
            }

    def status(self) -> dict[str, Any]:
        state = self._read_state()
        live_epochs, live_extras = self._epoch_inventory(self.live_dir)
        archived_epochs, archive_extras = self._epoch_inventory(self.archive_dir)
        return {
            "ok": True,
            "version": self.VERSION,
            "state": state,
            "transition_window": self.transition_window(),
            "live": {
                "count": len(live_epochs),
                "first": live_epochs[0] if live_epochs else None,
                "last": live_epochs[-1] if live_epochs else None,
                "unexpected_files": live_extras,
            },
            "archive": {
                "count": len(archived_epochs),
                "first": archived_epochs[0] if archived_epochs else None,
                "last": archived_epochs[-1] if archived_epochs else None,
                "unexpected_files": archive_extras,
            },
            "historical_protection": {
                "first_epoch": self.pool_first_epoch,
                "last_epoch": state.get(
                    "initialization_protected_end",
                    self.historical_protection_end,
                ),
                "immutable": True,
            },
            "initialization": {
                "mode": "full sequential Blockfrost reconstruction from POOL_FIRST_EPOCH",
                "pool_first_epoch": self.pool_first_epoch,
                "archive_rule": "observed_epoch - 2",
                "live_rule": "observed_epoch - 1 and observed_epoch",
                "existing_epochs_overwritten": False,
            },
            "projections": {
                "pooldata": {
                    "auto_export": settings.pooldata_auto_export,
                    "directory": str(self.data_root / "pooldata"),
                },
                "mysql": {
                    "auto_sync": settings.mysql_auto_sync,
                    "configured": bool(settings.mysql_database and settings.mysql_user),
                    "credentials_exposed": False,
                },
            },
            "finalization": {
                "mode": "transactional catch-up + reward settlement + exact legacy replay",
                "primary_source": "blockfrost",
                "secondary_source": "koios_optional",
                "reports_dir": str(self.finalization_reports_dir),
                "rewards_settled_through": state.get("last_rewards_settled_epoch"),
                "chain_finalized_through": state.get("last_chain_finalized_epoch"),
                "archive_on_validation_failure": False,
            },
        }
