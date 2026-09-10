# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Independent operational health watcher for CspoE.

This module is deliberately outside the canonical epoch transaction.  It only
reads system/API/database state and sends private administrator alerts.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.blockfrost import BlockfrostClient
from core.config import ROOT, get_setting, settings
from core.mysql import MySQLRepository
from notifications.telegram import TelegramClient
from notifications.templates import format_health_incident, format_health_recovery

DEFAULT_STATE = ROOT / "data" / "CspoE" / "notifications" / "health_watcher_state.json"
EPOCH_STATE = ROOT / "data" / "CspoE" / "epoch_manager_state.json"

DEFAULT_TIMERS = (
    "cspoe-transition.timer",
    "cspoe-telegram.timer",
    "cspoe-block-watcher.timer",
    "cspoe-drep-watcher.timer",
    "cspoe-stake-watcher.timer",
)


def _now() -> int:
    return int(time.time())


def _bool(name: str, default: bool = False) -> bool:
    raw = get_setting(name, "1" if default else "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(get_setting(name, str(default)) or default)
    except (TypeError, ValueError):
        return int(default)


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _systemctl_show(unit: str) -> dict[str, str]:
    proc = subprocess.run(
        ["systemctl", "show", unit, "-p", "LoadState", "-p", "ActiveState", "-p", "SubState", "-p", "UnitFileState"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"systemctl rc={proc.returncode}").strip())
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


@dataclass
class CheckResult:
    key: str
    label: str
    ok: bool
    detail: str = ""
    severity: str = "warning"
    threshold: int = 3


def check_blockfrost() -> CheckResult:
    result = BlockfrostClient().health()
    if result.get("ok"):
        return CheckResult("blockfrost", "Blockfrost", True, f"epoch {result.get('epoch')}", threshold=_int("CSPOE_HEALTH_EXTERNAL_FAILURES", 3))
    return CheckResult("blockfrost", "Blockfrost", False, str(result.get("error") or "indisponible"), "critical", _int("CSPOE_HEALTH_EXTERNAL_FAILURES", 3))


def check_mysql() -> CheckResult:
    threshold = _int("CSPOE_HEALTH_EXTERNAL_FAILURES", 3)
    if not settings.mysql_database or not settings.mysql_user:
        return CheckResult("mysql", "MySQL", True, "non configuré — contrôle ignoré", threshold=threshold)
    repo = MySQLRepository()
    try:
        conn = repo.connect()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            row = cur.fetchone()
            if not row or int(row[0]) != 1:
                raise RuntimeError("SELECT 1 inattendu")
        finally:
            cur.close()
            conn.close()
        return CheckResult("mysql", "MySQL", True, "connexion OK", threshold=threshold)
    except Exception as exc:
        return CheckResult("mysql", "MySQL", False, str(exc), "critical", threshold)


def check_timer(unit: str) -> CheckResult:
    threshold = _int("CSPOE_HEALTH_SYSTEMD_FAILURES", 1)
    try:
        st = _systemctl_show(unit)
        # For timer units, SubState is informational and may legitimately
        # be "running" while the associated service is being triggered.
        # Health is determined by the stable unit properties instead.
        ok = (
            st.get("LoadState") == "loaded"
            and st.get("ActiveState") == "active"
            and st.get("UnitFileState") in {"enabled", "static"}
        )
        detail = ", ".join(f"{k}={st.get(k, '')}" for k in ("LoadState", "ActiveState", "SubState", "UnitFileState"))
        return CheckResult(f"timer:{unit}", unit, ok, detail, "critical", threshold)
    except Exception as exc:
        return CheckResult(f"timer:{unit}", unit, False, str(exc), "critical", threshold)


def check_epoch_state(chain_epoch: int | None) -> list[CheckResult]:
    results: list[CheckResult] = []
    state = _load(EPOCH_STATE)
    if not state:
        return [CheckResult("epoch_state", "État du moteur d’epoch", False, f"illisible ou absent: {EPOCH_STATE}", "critical", 1)]

    def iv(name: str, default: int = -1) -> int:
        try:
            return int(state.get(name, default))
        except (TypeError, ValueError):
            return default

    collected = iv("last_collected_epoch")
    finalized = iv("last_finalized_epoch")
    settled = iv("last_rewards_settled_epoch")
    transition = state.get("transition") if isinstance(state.get("transition"), dict) else {}
    status = str(transition.get("status") or "")

    structural_ok = collected >= 0 and finalized >= 0 and finalized <= collected and (collected - finalized) <= _int("CSPOE_HEALTH_FINALIZATION_LAG_MAX", 1)
    results.append(CheckResult(
        "epoch_consistency", "Cohérence epochs CspoE", structural_ok,
        f"collected={collected}, finalized={finalized}, transition={status or 'n/a'}", "critical", 1,
    ))

    if chain_epoch is not None and collected >= 0:
        lag = chain_epoch - collected
        max_lag = _int("CSPOE_HEALTH_CHAIN_EPOCH_LAG_MAX", 1)
        results.append(CheckResult(
            "chain_epoch_lag", "Retard CspoE sur la chaîne", lag <= max_lag,
            f"chain={chain_epoch}, collected={collected}, lag={lag}", "critical", 1,
        ))
    if chain_epoch is not None and settled >= 0:
        reward_lag = chain_epoch - settled
        max_reward_lag = _int("CSPOE_HEALTH_REWARD_LAG_MAX", 2)
        results.append(CheckResult(
            "reward_lag", "Retard de règlement rewards", reward_lag <= max_reward_lag,
            f"chain={chain_epoch}, settled={settled}, lag={reward_lag}", "warning", _int("CSPOE_HEALTH_REWARD_FAILURES", 2),
        ))
    return results


def _transition_state(old: dict[str, Any], result: CheckResult, now: int) -> tuple[dict[str, Any], str | None]:
    rec = dict(old or {})
    was_open = bool(rec.get("incident_open"))
    if result.ok:
        rec.update({
            "status": "ok", "consecutive_failures": 0, "last_ok_at": now,
            "last_detail": result.detail, "label": result.label,
        })
        if was_open:
            opened = int(rec.get("incident_opened_at") or now)
            rec["incident_open"] = False
            rec["recovered_at"] = now
            return rec, format_health_recovery(result.label, result.detail, max(0, now - opened))
        rec["incident_open"] = False
        return rec, None

    failures = int(rec.get("consecutive_failures") or 0) + 1
    rec.update({
        "status": "failed", "consecutive_failures": failures,
        "last_failure_at": now, "last_detail": result.detail,
        "label": result.label, "severity": result.severity,
    })
    if not rec.get("first_failure_at") or not was_open:
        rec["first_failure_at"] = now
    if not was_open and failures >= max(1, result.threshold):
        rec["incident_open"] = True
        rec["incident_opened_at"] = now
        rec["notified_at"] = now
        return rec, format_health_incident(result.label, result.detail, failures, result.severity)
    return rec, None


def run_health(*, dry_run: bool = False, checks_override: Callable[[], list[CheckResult]] | None = None) -> dict[str, Any]:
    state_path = Path(get_setting("CSPOE_HEALTH_STATE_FILE", str(DEFAULT_STATE)))
    old_state = _load(state_path)
    old_checks = old_state.get("checks") if isinstance(old_state.get("checks"), dict) else {}
    now = _now()

    if checks_override is not None:
        results = checks_override()
    else:
        bf = check_blockfrost()
        results = [bf, check_mysql()]
        for unit in DEFAULT_TIMERS:
            results.append(check_timer(unit))
        chain_epoch = None
        if bf.ok:
            try:
                chain_epoch = int(bf.detail.split()[-1])
            except (ValueError, IndexError):
                chain_epoch = None
        results.extend(check_epoch_state(chain_epoch))

    new_checks: dict[str, Any] = {}
    messages: list[dict[str, str]] = []
    for result in results:
        rec, message = _transition_state(old_checks.get(result.key, {}), result, now)
        new_checks[result.key] = rec
        if message:
            messages.append({"key": result.key, "text": message})

    enabled = _bool("CSPOE_TELEGRAM_ADMIN_ENABLED", False)
    token = get_setting("TELEGRAM_BOT_TOKEN")
    admin_chat = get_setting("TELEGRAM_ADMIN_CHAT_ID")
    sent: list[str] = []
    if not dry_run and enabled and messages:
        if not admin_chat:
            raise RuntimeError("TELEGRAM_ADMIN_CHAT_ID absent alors que CSPOE_TELEGRAM_ADMIN_ENABLED=1")
        client = TelegramClient(token=token, chat_id=admin_chat)
        for item in messages:
            client.send_message(item["text"])
            sent.append(item["key"])

    new_state = {"version": 1, "updated_at": now, "checks": new_checks}
    if not dry_run:
        _save(state_path, new_state)

    return {
        "ok": all(r.ok for r in results),
        "dry_run": dry_run,
        "admin_enabled": enabled,
        "admin_chat_id": admin_chat,
        "checks_total": len(results),
        "checks_failed": sum(1 for r in results if not r.ok),
        "notifications_pending": len(messages),
        "notifications_sent": sent,
        "messages": messages,
        "checks": [
            {"key": r.key, "label": r.label, "ok": r.ok, "detail": r.detail, "threshold": r.threshold}
            for r in results
        ],
        "state_file": str(state_path),
    }
