# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF_CANDIDATES = (
    ROOT / "CspoE.conf",
    ROOT / "config" / "CspoE.conf",
)


def _load_conf() -> tuple[dict[str, str], Path | None]:
    values: dict[str, str] = {}
    used: Path | None = None
    # Root config keeps compatibility with the deployed engine. config/CspoE.conf
    # is also accepted. The first existing file has priority; the second only
    # fills keys that are absent/empty.
    for path in CONF_CANDIDATES:
        if not path.is_file():
            continue
        if used is None:
            used = path
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and (key not in values or not values[key]):
                values[key] = value
    return values, used


_CONF, CONF_PATH = _load_conf()


def get_setting(name: str, default: str = "") -> str:
    """Non-empty config wins; an empty config entry never masks an env secret."""
    value = _CONF.get(name)
    if value not in (None, ""):
        return str(value)
    env = os.getenv(name)
    return env if env not in (None, "") else default


def _int_setting(name: str, default: int) -> int:
    try:
        return int(get_setting(name, str(default)) or default)
    except (TypeError, ValueError):
        return int(default)


def _bool_setting(name: str, default: bool = False) -> bool:
    raw = get_setting(name, "1" if default else "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    blockfrost_project_id: str = get_setting("BLOCKFROST_PROJECT_ID")
    bech32_pool_id: str = get_setting("BECH32_POOL_ID")
    pool_ticker: str = get_setting("POOL_TICKER", "POOL")
    pool_first_epoch: int = _int_setting("POOL_FIRST_EPOCH", 0)
    network: str = (get_setting("CARDANO_NETWORK", "mainnet") or "mainnet").lower()
    blockfrost_page_size: int = _int_setting("BLOCKFROST_PAGE_SIZE", 100)
    # Local initialization guard. This is deliberately below the commonly
    # used Starter allowance and remains configurable because plan limits and
    # other consumers sharing the same Blockfrost account are external state.
    blockfrost_daily_budget: int = _int_setting("BLOCKFROST_DAILY_BUDGET", 45000)
    blockfrost_quota_reserve: int = _int_setting("BLOCKFROST_QUOTA_RESERVE", 2000)
    blockfrost_auto_pause: bool = _bool_setting("BLOCKFROST_AUTO_PAUSE", True)
    api_max_pages: int = _int_setting("API_MAX_PAGES", 10000)
    prune_nb: int = _int_setting("PRUNE_NB", 10)
    awards_file: str = get_setting("AWARDS_FILE", str(ROOT / "data" / "awards.json"))
    legacy_source: str = get_setting(
        "CSPOE_LEGACY_SOURCE",
        str(ROOT / "data" / "CspoE" / "legacy_reference" / "history"),
    )
    koios_base: str = get_setting("CSPOE_KOIOS_BASE", "https://api.koios.rest/api/v1")
    data_dir: str = str(ROOT / "data")
    strict_secondary_check: bool = _bool_setting("CSPOE_STRICT_SECONDARY_CHECK")

    # Optional projections.  They never participate in the canonical epoch
    # transaction; a failed projection can therefore be retried safely.
    pooldata_auto_export: bool = _bool_setting("CSPOE_POOLDATA_AUTO_EXPORT", True)
    mysql_auto_sync: bool = _bool_setting("CSPOE_MYSQL_AUTO_SYNC", False)
    mysql_legacy_compat: bool = _bool_setting("CSPOE_MYSQL_LEGACY_COMPAT", False)
    mysql_host: str = get_setting("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = _int_setting("MYSQL_PORT", 3306)
    mysql_database: str = get_setting("MYSQL_DATABASE")
    mysql_user: str = get_setting("MYSQL_USER")
    mysql_password: str = get_setting("MYSQL_PASSWORD")

    @property
    def project_id(self) -> str:
        return self.blockfrost_project_id

    @property
    def pool_id(self) -> str:
        return self.bech32_pool_id

    @property
    def ticker(self) -> str:
        return self.pool_ticker


settings = Settings()
