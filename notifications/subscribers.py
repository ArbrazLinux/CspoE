# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""SQLite registry for interactive Telegram subscribers.

This database is notification-only and never participates in canonical CspoE data.
V1.2 adds one-time CIP-8 ownership challenges and verified bindings.
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS telegram_users (
  telegram_user_id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  username TEXT,
  first_name TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS stake_bindings (
  telegram_user_id INTEGER NOT NULL,
  stake_address TEXT NOT NULL,
  ownership_verified INTEGER NOT NULL DEFAULT 0,
  pool_verified INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  verified_at INTEGER,
  verification_method TEXT,
  PRIMARY KEY (telegram_user_id, stake_address),
  FOREIGN KEY (telegram_user_id) REFERENCES telegram_users(telegram_user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS preferences (
  telegram_user_id INTEGER PRIMARY KEY,
  reward_alert INTEGER NOT NULL DEFAULT 1,
  stake_alert INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY (telegram_user_id) REFERENCES telegram_users(telegram_user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS deliveries (
  telegram_user_id INTEGER NOT NULL,
  stake_address TEXT NOT NULL DEFAULT '',
  event_key TEXT NOT NULL,
  delivered_at INTEGER NOT NULL,
  PRIMARY KEY (telegram_user_id, stake_address, event_key)
);
CREATE TABLE IF NOT EXISTS verification_challenges (
  telegram_user_id INTEGER NOT NULL,
  stake_address TEXT NOT NULL,
  nonce TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER,
  PRIMARY KEY (telegram_user_id, stake_address),
  FOREIGN KEY (telegram_user_id) REFERENCES telegram_users(telegram_user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS bot_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

class SubscriberStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            self._migrate(db)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _migrate(self, db: sqlite3.Connection) -> None:
        cols={str(r[1]) for r in db.execute("PRAGMA table_info(stake_bindings)")}
        for name,typ in (("verified_at","INTEGER"),("verification_method","TEXT")):
            if name not in cols:
                db.execute(f"ALTER TABLE stake_bindings ADD COLUMN {name} {typ}")

    def connect(self) -> sqlite3.Connection:
        db=sqlite3.connect(self.path, timeout=15)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def upsert_user(self, user_id:int, chat_id:int, username:str="", first_name:str="") -> None:
        now=int(time.time())
        with self.connect() as db:
            db.execute("""INSERT INTO telegram_users(telegram_user_id,chat_id,username,first_name,enabled,created_at,updated_at)
                        VALUES(?,?,?,?,1,?,?) ON CONFLICT(telegram_user_id) DO UPDATE SET
                        chat_id=excluded.chat_id, username=excluded.username, first_name=excluded.first_name,
                        enabled=1, updated_at=excluded.updated_at""", (user_id,chat_id,username,first_name,now,now))
            db.execute("INSERT OR IGNORE INTO preferences(telegram_user_id) VALUES(?)",(user_id,))

    def add_binding(self,user_id:int,address:str,pool_verified:bool=True) -> None:
        now=int(time.time())
        with self.connect() as db:
            # Preserve verified ownership on re-add; do not silently downgrade a verified binding.
            existing=db.execute("SELECT ownership_verified,verified_at,verification_method FROM stake_bindings WHERE telegram_user_id=? AND stake_address=?",(user_id,address)).fetchone()
            ov=int(existing[0]) if existing else 0
            va=existing[1] if existing else None
            vm=existing[2] if existing else None
            db.execute("""INSERT OR REPLACE INTO stake_bindings(
                telegram_user_id,stake_address,ownership_verified,pool_verified,created_at,verified_at,verification_method
                ) VALUES(?,?,?,?,?,?,?)""",(user_id,address,ov,1 if pool_verified else 0,now,va,vm))

    def mark_ownership_verified(self,user_id:int,address:str,method:str="CIP-8") -> bool:
        now=int(time.time())
        with self.connect() as db:
            cur=db.execute("""UPDATE stake_bindings SET ownership_verified=1,verified_at=?,verification_method=?
                              WHERE telegram_user_id=? AND stake_address=? AND pool_verified=1""",
                           (now,method,user_id,address))
            return cur.rowcount>0

    def create_challenge(self,user_id:int,address:str,ttl_seconds:int=600,ticker:str="POOL") -> dict[str,Any]:
        now=int(time.time()); expires=now+max(60,int(ttl_seconds)); nonce=secrets.token_hex(16)
        payload=f"CspoE:{ticker}:stake-verify:v1:{user_id}:{address}:{nonce}:{expires}"
        with self.connect() as db:
            db.execute("""INSERT INTO verification_challenges(telegram_user_id,stake_address,nonce,payload,created_at,expires_at,used_at)
                          VALUES(?,?,?,?,?,?,NULL)
                          ON CONFLICT(telegram_user_id,stake_address) DO UPDATE SET
                          nonce=excluded.nonce,payload=excluded.payload,created_at=excluded.created_at,
                          expires_at=excluded.expires_at,used_at=NULL""",
                       (user_id,address,nonce,payload,now,expires))
        return {"telegram_user_id":user_id,"stake_address":address,"nonce":nonce,"payload":payload,"created_at":now,"expires_at":expires}

    def active_challenge(self,user_id:int,address:str,now:int|None=None) -> dict[str,Any]|None:
        now=int(time.time()) if now is None else int(now)
        with self.connect() as db:
            r=db.execute("SELECT * FROM verification_challenges WHERE telegram_user_id=? AND stake_address=?",(user_id,address)).fetchone()
        if not r:return None
        d=dict(r)
        if d.get("used_at") is not None or int(d.get("expires_at") or 0)<now:return None
        return d

    def consume_challenge(self,user_id:int,address:str) -> bool:
        now=int(time.time())
        with self.connect() as db:
            cur=db.execute("""UPDATE verification_challenges SET used_at=?
                              WHERE telegram_user_id=? AND stake_address=? AND used_at IS NULL AND expires_at>=?""",
                           (now,user_id,address,now))
            return cur.rowcount>0

    def remove_binding(self,user_id:int,address:str) -> bool:
        with self.connect() as db:
            db.execute("DELETE FROM verification_challenges WHERE telegram_user_id=? AND stake_address=?",(user_id,address))
            cur=db.execute("DELETE FROM stake_bindings WHERE telegram_user_id=? AND stake_address=?",(user_id,address))
            return cur.rowcount>0

    def bindings(self,user_id:int) -> list[dict[str,Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM stake_bindings WHERE telegram_user_id=? ORDER BY created_at",(user_id,))]

    def prefs(self,user_id:int) -> dict[str,bool]:
        with self.connect() as db:
            r=db.execute("SELECT reward_alert,stake_alert FROM preferences WHERE telegram_user_id=?",(user_id,)).fetchone()
        return {"reward_alert":bool(r[0]) if r else True,"stake_alert":bool(r[1]) if r else True}

    def set_pref(self,user_id:int,key:str,value:bool) -> None:
        if key not in {"reward_alert","stake_alert"}: raise ValueError("préférence inconnue")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO preferences(telegram_user_id) VALUES(?)",(user_id,))
            db.execute(f"UPDATE preferences SET {key}=? WHERE telegram_user_id=?",(1 if value else 0,user_id))

    def recipients_for(self,address:str,pref_key:str,require_ownership_verified:bool=True) -> list[dict[str,Any]]:
        if pref_key not in {"reward_alert","stake_alert"}: raise ValueError("préférence inconnue")
        verified="AND b.ownership_verified=1" if require_ownership_verified else ""
        with self.connect() as db:
            rows=db.execute(f"""SELECT u.telegram_user_id,u.chat_id,u.username,u.first_name,b.stake_address,b.ownership_verified
                FROM stake_bindings b JOIN telegram_users u USING(telegram_user_id)
                JOIN preferences p USING(telegram_user_id)
                WHERE b.stake_address=? AND b.pool_verified=1 {verified} AND u.enabled=1 AND p.{pref_key}=1""",(address,)).fetchall()
        return [dict(r) for r in rows]

    def was_delivered(self,user_id:int,address:str,event_key:str)->bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM deliveries WHERE telegram_user_id=? AND stake_address=? AND event_key=?",(user_id,address,event_key)).fetchone() is not None

    def mark_delivered(self,user_id:int,address:str,event_key:str)->None:
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO deliveries VALUES(?,?,?,?)",(user_id,address,event_key,int(time.time())))

    def get_meta(self,key:str,default:str="") -> str:
        with self.connect() as db:
            r=db.execute("SELECT value FROM bot_meta WHERE key=?",(key,)).fetchone()
        return str(r[0]) if r else default

    def set_meta(self,key:str,value:str)->None:
        with self.connect() as db:
            db.execute("INSERT INTO bot_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
