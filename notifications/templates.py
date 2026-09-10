# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Centralised French Telegram message templates for CspoE/pool.

All Telegram presentation belongs here. Watchers should only detect events and
pass structured data to these renderers.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from urllib.parse import quote

from .events import Event

CARDANOSCAN_BASE = "https://cardanoscan.io"


def ada(lovelace: int | str | None, *, signed: bool = False) -> str:
    """Format lovelace as human-readable ADA without losing useful precision."""
    try:
        raw = int(lovelace or 0)
    except (TypeError, ValueError):
        raw = 0
    value = raw / 1_000_000
    sign = "+" if signed and raw > 0 else ""
    av = abs(value)
    if av >= 1_000_000:
        text = f"{value / 1_000_000:,.3f} M₳"
    elif av >= 1_000:
        text = f"{value:,.2f} ₳"
    elif av >= 10:
        text = f"{value:,.2f} ₳"
    elif av >= 1:
        text = f"{value:,.3f} ₳"
    else:
        text = f"{value:,.6f} ₳"
    return sign + text.replace(",", " ")


def pct_change(before: int | str | None, after: int | str | None) -> str | None:
    try:
        b, a = int(before or 0), int(after or 0)
    except (TypeError, ValueError):
        return None
    if b == 0:
        return None
    pct = (a - b) * 100.0 / b
    return f"{pct:+.2f} %"


def short_id(value: str | None, *, left: int = 14, right: int = 8) -> str:
    value = str(value or "")
    return value if len(value) <= left + right + 1 else f"{value[:left]}…{value[-right:]}"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _link(label: str, url: str) -> str:
    return f'<a href="{_esc(url)}">{_esc(label)}</a>'


def stake_link(address: str) -> str:
    addr = str(address)
    return _link(short_id(addr, left=16, right=10), f"{CARDANOSCAN_BASE}/stakekey/{quote(addr, safe='')}")


def block_link(*, block_hash: str | None = None, height: int | str | None = None) -> str:
    target = str(height if height not in (None, "") else block_hash or "")
    label = f"bloc {target}" if height not in (None, "") else short_id(target)
    return _link(label, f"{CARDANOSCAN_BASE}/block/{quote(target, safe='')}") if target else ""


def gov_action_link(proposal_id: str) -> str:
    pid = str(proposal_id)
    return _link(short_id(pid, left=18, right=10), f"{CARDANOSCAN_BASE}/govAction/{quote(pid, safe='')}")


def _chain_time(timestamp: object) -> str | None:
    try:
        dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        return dt.strftime("%d/%m/%Y %H:%M:%S UTC")
    except (TypeError, ValueError, OSError):
        return None


def _header(icon: str, title: str) -> list[str]:
    return [f"{icon} <b>{_esc(title)}</b>", ""]


def render(event: Event, *, ticker: str = "POOL") -> str:
    """Render events produced from canonical CspoE snapshots."""
    d = event.data
    pool = _esc(ticker)
    if event.kind == "new_epoch":
        summary = d.get("summary") if isinstance(d.get("summary"), dict) else {}
        return render_epoch_summary(current_epoch=event.epoch, summary=summary, ticker=ticker)
    if event.kind == "rewards_settled":
        return render_rewards_settled(d, ticker=ticker)
    if event.kind == "delegator_join":
        return render_live_delegator_event(kind="join", address=str(d["address"]), before=0, after=int(d["stake"]), ticker=ticker)
    if event.kind == "delegator_leave":
        return render_live_delegator_event(kind="leave", address=str(d["address"]), before=int(d["stake"]), after=0, ticker=ticker)
    if event.kind == "delegator_stake_change":
        return render_live_delegator_event(kind="change", address=str(d["address"]), before=int(d["before"]), after=int(d["after"]), ticker=ticker)
    if event.kind == "pool_stake_change":
        return render_live_pool_stake_change(before=int(d["before"]), after=int(d["after"]), ticker=ticker)
    if event.kind == "block":
        return render_realtime_block(d.get("block") or {}, ticker=ticker)
    return f"🔔 <b>{pool}</b> · {_esc(event.kind)} · epoch {_esc(event.epoch)}"


def render_realtime_block(block: dict, *, ticker: str = "POOL") -> str:
    block_hash = str(block.get("hash") or "")
    epoch = block.get("epoch")
    slot = block.get("slot")
    height = block.get("height")
    tx_count = block.get("tx_count")
    lines = _header("🧱", f"Bloc produit par {ticker} !")
    if epoch not in (None, ""):
        lines.append(f"Epoch : <b>{_esc(epoch)}</b>")
    if height not in (None, ""):
        lines.append(f"Hauteur : <code>{_esc(height)}</code>")
    if slot not in (None, ""):
        lines.append(f"Slot : <code>{_esc(slot)}</code>")
    if tx_count not in (None, ""):
        lines.append(f"Transactions : <b>{_esc(tx_count)}</b>")
    when = _chain_time(block.get("time"))
    if when:
        lines.append(f"Heure chaîne : <code>{_esc(when)}</code>")
    if block_hash:
        lines.append(f"Hash : <code>{_esc(short_id(block_hash))}</code>")
        explorer = block_link(block_hash=block_hash, height=height)
        if explorer:
            lines += ["", f"🔎 Voir {explorer} sur Cardanoscan"]
    return "\n".join(lines)


def render_drep_vote(vote: dict, *, ticker: str = "POOL", proposal: dict | None = None, tx: dict | None = None) -> str:
    proposal, tx = proposal or {}, tx or {}
    choice = str(vote.get("vote") or "").lower()
    labels = {"yes": "OUI ✅", "no": "NON ❌", "abstain": "ABSTENTION ⚪"}
    type_labels = {
        "parameter_change": "Changement de paramètres",
        "hard_fork_initiation": "Initiation de hard fork",
        "treasury_withdrawals": "Retrait du Trésor",
        "no_confidence": "Motion de défiance",
        "new_committee": "Nouveau comité constitutionnel",
        "new_constitution": "Nouvelle constitution",
        "info_action": "Action informative",
    }
    ptype = str(proposal.get("governance_type") or "")
    proposal_id = str(vote.get("proposal_id") or proposal.get("id") or "")
    tx_hash = str(vote.get("tx_hash") or "")
    lines = _header("🗳️", f"Nouveau vote du DRep {ticker}")
    lines.append(f"Vote : <b>{_esc(labels.get(choice, choice.upper() or 'INCONNU'))}</b>")
    if ptype:
        lines.append(f"Action : <b>{_esc(type_labels.get(ptype, ptype))}</b>")
    if tx.get("block_height") not in (None, ""):
        lines.append(f"Bloc : <code>{_esc(tx.get('block_height'))}</code>")
    when = _chain_time(tx.get("block_time"))
    if when:
        lines.append(f"Heure chaîne : <code>{_esc(when)}</code>")
    if proposal_id:
        lines.append(f"Action ID : <code>{_esc(short_id(proposal_id, left=18, right=10))}</code>")
    if tx_hash:
        lines.append(f"Tx vote : <code>{_esc(short_id(tx_hash))}</code>")
    if proposal_id.startswith("gov_action1"):
        lines += ["", f"🔎 Voir l’action sur Cardanoscan : {gov_action_link(proposal_id)}"]
    return "\n".join(lines)


def render_live_delegator_event(*, kind: str, address: str, before: int, after: int, ticker: str = "POOL",
                                diff_override: int | None = None, reward_component: int = 0) -> str:
    before, after = int(before), int(after)
    raw_diff = after - before
    diff = raw_diff if diff_override is None else int(diff_override)
    reward_component = int(reward_component or 0)
    if kind == "join":
        lines = _header("🟢", "Nouveau délégateur")
        lines += [f"Pool <b>{_esc(ticker)}</b>", f"Stake : <b>{ada(after)}</b>"]
    elif kind == "leave":
        lines = _header("🔴", "Départ d’un délégateur")
        lines += [f"Pool <b>{_esc(ticker)}</b>", f"Dernier stake : <b>{ada(before)}</b>"]
    else:
        icon = "📈" if diff > 0 else "📉"
        lines = _header(icon, "Variation de délégation")
        label = "Variation hors rewards" if reward_component else "Variation"
        lines += [f"Pool <b>{_esc(ticker)}</b>", f"{label} : <b>{ada(diff, signed=True)}</b>"]
        pct = pct_change(before, after)
        if pct:
            lines[-1] += f" · <b>{_esc(pct)}</b>"
        lines.append(f"Stake : {ada(before)} → <b>{ada(after)}</b>")
        if reward_component:
            lines.append(f"Rewards intégrées neutralisées : {ada(reward_component, signed=True)}")
    lines += [f"Délégateur : {stake_link(address)}"]
    return "\n".join(lines)



def render_grouped_stake_event(*, before: int, after: int, events: list[dict], ticker: str = "POOL",
                               delegator_count: int | None = None, max_items: int = 8, residual: int = 0,
                               diff_override: int | None = None, reward_component: int = 0) -> str:
    """Render a pool stake move together with the delegator changes that explain it."""
    before, after = int(before), int(after)
    raw_diff = after - before
    diff = raw_diff if diff_override is None else int(diff_override)
    reward_component = int(reward_component or 0)
    icon = "📈" if diff > 0 else "📉"
    lines = _header(icon, "Mouvement de délégation")
    label = "Stake pool hors rewards" if reward_component else "Stake pool"
    lines += [f"Pool <b>{_esc(ticker)}</b>", f"{label} : <b>{ada(diff, signed=True)}</b>"]
    pct = pct_change(before, after)
    if pct:
        lines[-1] += f" · <b>{_esc(pct)}</b>"
    lines.append(f"Total : {ada(before)} → <b>{ada(after)}</b>")
    if reward_component:
        lines.append(f"Rewards intégrées neutralisées : {ada(reward_component, signed=True)}")
    if delegator_count is not None:
        lines.append(f"Délégateurs : <b>{int(delegator_count)}</b>")
    lines.append("")
    lines.append("<b>Changements associés</b>")
    labels={"join":"🟢 Arrivée","leave":"🔴 Départ","change":"↕️ Variation"}
    ordered=sorted(events, key=lambda e: abs(int(e.get("diff",0))), reverse=True)
    for e in ordered[:max(1,int(max_items))]:
        kind=str(e.get("kind") or "change")
        addr=str(e.get("address") or "")
        d=int(e.get("diff",0) or 0)
        lines.append(f"{labels.get(kind,'↕️ Variation')} · <b>{ada(d, signed=True)}</b> · {stake_link(addr)}")
    extra=max(0,len(ordered)-max(1,int(max_items)))
    if extra:
        lines.append(f"… et <b>{extra}</b> autre(s) changement(s)")
    if residual:
        lines.append(f"Écart d’attribution : {ada(int(residual), signed=True)}")
    return "\n".join(lines)

def render_live_pool_stake_change(*, before: int, after: int, ticker: str = "POOL", delegator_count: int | None = None,
                                  diff_override: int | None = None, reward_component: int = 0) -> str:
    before, after = int(before), int(after)
    raw_diff = after - before
    diff = raw_diff if diff_override is None else int(diff_override)
    reward_component = int(reward_component or 0)
    icon = "📈" if diff > 0 else "📉"
    lines = _header(icon, "Variation du stake live du pool")
    label = "Variation hors rewards" if reward_component else "Variation"
    lines += [f"Pool <b>{_esc(ticker)}</b>", f"{label} : <b>{ada(diff, signed=True)}</b>"]
    pct = pct_change(before, after)
    if pct:
        lines[-1] += f" · <b>{_esc(pct)}</b>"
    lines.append(f"Stake : {ada(before)} → <b>{ada(after)}</b>")
    if reward_component:
        lines.append(f"Rewards intégrées neutralisées : {ada(reward_component, signed=True)}")
    if delegator_count is not None:
        lines.append(f"Délégateurs : <b>{int(delegator_count)}</b>")
    return "\n".join(lines)


def render_epoch_summary(*, current_epoch: int, summary: dict, ticker: str = "POOL") -> str:
    """Render the transition summary without rewards (settled later)."""
    closed_epoch = int(summary.get("closed_epoch", int(current_epoch) - 1) or (int(current_epoch) - 1))
    blocks = int(summary.get("blocks", 0) or 0)
    stake = int(summary.get("stake", 0) or 0)
    previous_stake = int(summary.get("previous_stake", stake) or 0)
    stake_diff = int(summary.get("stake_diff", stake - previous_stake) or 0)
    delegators = int(summary.get("delegators", 0) or 0)
    previous_delegators = int(summary.get("previous_delegators", delegators) or 0)
    delegators_diff = int(summary.get("delegators_diff", delegators - previous_delegators) or 0)

    lines = _header("📅", f"Nouvelle epoch Cardano · {current_epoch}")
    lines.append(f"Bilan de l’epoch <b>{closed_epoch}</b> pour le pool <b>{_esc(ticker)}</b>")
    lines.append("")
    lines.append(f"🧱 Blocs produits : <b>{blocks}</b>")
    if stake:
        stake_line = f"💎 Stake : <b>{ada(stake)}</b>"
        if stake_diff:
            stake_line += f" · {ada(stake_diff, signed=True)}"
            pct = pct_change(previous_stake, stake)
            if pct:
                stake_line += f" ({_esc(pct)})"
        lines.append(stake_line)
    deleg_line = f"👥 Délégateurs : <b>{delegators}</b>"
    if delegators_diff:
        deleg_line += f" · {delegators_diff:+d}"
    lines.append(deleg_line)
    lines += ["", "ℹ️ Les rewards seront annoncées séparément après leur règlement effectif."]
    return "\n".join(lines)


def render_rewards_settled(data: dict, *, ticker: str = "POOL") -> str:
    epoch = int(data.get("settled_epoch", 0) or 0)
    total = int(data.get("pool_rewards", 0) or 0)
    owners = int(data.get("owners_rewards", 0) or 0)
    delegators = int(data.get("delegators_rewards", 0) or 0)
    rewarded_accounts = int(data.get("rewarded_accounts", 0) or 0)
    blocks = int(data.get("blocks", 0) or 0)
    lines = _header("💰", "Rewards distribuées")
    lines.append(f"Les rewards de l’epoch <b>{epoch}</b> ont été versées pour <b>{_esc(ticker)}</b>.")
    lines.append("")
    lines.append(f"Total : <b>{ada(total)}</b>")
    lines.append(f"Opérateurs / owners : <b>{ada(owners)}</b>")
    lines.append(f"Délégateurs : <b>{ada(delegators)}</b>")
    if rewarded_accounts:
        lines.append(f"Comptes récompensés : <b>{rewarded_accounts}</b>")
    if blocks:
        lines.append(f"Blocs produits dans l’epoch : <b>{blocks}</b>")
    return "\n".join(lines)


def _duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def format_health_incident(label: str, detail: str, failures: int, severity: str = "warning") -> str:
    icon = "🚨" if severity == "critical" else "⚠️"
    return (
        f"{icon} <b>CspoE — Incident technique</b>\n\n"
        f"<b>{html.escape(str(label))}</b>\n"
        f"Échecs consécutifs : <b>{int(failures)}</b>\n"
        f"Détail : <code>{html.escape(str(detail))}</code>\n\n"
        "Cette alerte est privée et ne sera pas publiée sur le canal public."
    )


def format_health_recovery(label: str, detail: str, duration_seconds: int) -> str:
    return (
        "✅ <b>CspoE — Service rétabli</b>\n\n"
        f"<b>{html.escape(str(label))}</b> est de nouveau opérationnel.\n"
        f"Durée approximative de l’incident : <b>{_duration(duration_seconds)}</b>\n"
        f"État : <code>{html.escape(str(detail))}</code>"
    )


def format_transition_success(*, from_epoch: int, to_epoch: int, finalized_epoch: int, rewards_settled_through: int | None, checks_ok: int, checks_total: int, detail: str = "") -> str:
    """Private positive acknowledgement after a confirmed epoch transition."""
    lines = [
        "✅ <b>CspoE — Transition réussie</b>",
        "",
        f"Epoch <b>{int(from_epoch)}</b> → <b>{int(to_epoch)}</b> confirmée.",
        f"Epoch finalisée : <b>{int(finalized_epoch)}</b>",
    ]
    if rewards_settled_through is not None and int(rewards_settled_through) >= 0:
        lines.append(f"Rewards réglées jusqu’à l’epoch : <b>{int(rewards_settled_through)}</b>")
    lines.append(f"Santé CspoE : <b>{int(checks_ok)}/{int(checks_total)} contrôles OK</b>")
    if detail:
        lines += ["", f"État : <code>{html.escape(str(detail))}</code>"]
    lines += ["", "Synthèse privée d’exploitation — non publiée sur le canal public."]
    return "\n".join(lines)


def render_stake_address_transfer(*, from_address: str, to_address: str, before: int, after: int,
                                  ticker: str = "POOL", age_seconds: int | None = None) -> str:
    """Render a likely stake-address migration as one public event."""
    before, after = int(before), int(after)
    diff = after - before
    lines = _header("🔄", "Transfert de stake / changement de stake address")
    lines += [f"Pool <b>{_esc(ticker)}</b>", f"Stake transféré : <b>{ada(after)}</b>"]
    if diff:
        lines.append(f"Écart entre les deux adresses : <b>{ada(diff, signed=True)}</b>")
    if age_seconds is not None:
        minutes = max(0, int(age_seconds) // 60)
        if minutes < 60:
            delay = f"{minutes} min"
        else:
            h, m = divmod(minutes, 60)
            delay = f"{h} h {m:02d}"
        lines.append(f"Délai de corrélation : <b>{_esc(delay)}</b>")
    lines += ["", f"Ancienne adresse : {stake_link(from_address)}", f"Nouvelle adresse : {stake_link(to_address)}"]
    lines += ["", "ℹ️ Détecté comme un transfert probable : ni départ ni nouvelle arrivée ne sont comptabilisés séparément."]
    return "\n".join(lines)
