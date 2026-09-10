# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Local canonical-data browser used by the CspoE desktop GUI."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.model import AdminModel, ada


def compact(value: str, head: int = 16, tail: int = 10) -> str:
    text = str(value)
    return text if len(text) <= head + tail + 1 else f"{text[:head]}…{text[-tail:]}"


class SortableItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        # Do not call QTableWidgetItem.__lt__ through super() here. With the
        # PySide6/Shiboken binding used by CspoE, that virtual call is routed
        # back to this Python override and recurses until the process crashes.
        # Comparing the displayed values directly keeps Qt sorting stable and
        # preserves numeric sorting through UserRole above.
        if left is not None and right is not None:
            return str(left).casefold() < str(right).casefold()
        return self.text().casefold() < other.text().casefold()


def table_item(text: Any, *, sort_value: Any = None, tooltip: str = "") -> QTableWidgetItem:
    item = SortableItem(str(text))
    if sort_value is not None:
        item.setData(Qt.ItemDataRole.UserRole, sort_value)
    if tooltip:
        item.setToolTip(tooltip)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def setup_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class DelegatorDialog(QDialog):
    def __init__(self, model: AdminModel, stake_address: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historique délégataire")
        self.resize(1080, 620)
        layout = QVBoxLayout(self)
        title = QLabel(stake_address)
        title.setObjectName("sectionTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setWordWrap(True)
        layout.addWidget(title)

        history = model.delegator_history(stake_address)
        subtitle = QLabel(f"{len(history)} epochs présents dans la chronologie canonique")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        table = setup_table(
            ["Epoch", "Stake", "Variation", "Reward", "Rewards cumulées", "Bonus", "Loyauté", "ROA"]
        )
        table.setSortingEnabled(False)
        table.setRowCount(len(history))
        for row_index, row in enumerate(history):
            values = (
                (row["epoch"], row["epoch"]),
                (ada(row["stake"]), row["stake"]),
                (ada(row["stake_diff"]), row["stake_diff"]),
                (ada(row["rewards"]), row["rewards"]),
                (ada(row["rewards_sum"]), row["rewards_sum"]),
                (ada(row["bonus"]), row["bonus"]),
                (f"{row['loyalty']:.2f} %", row["loyalty"]),
                (f"{row['roa']:.2f} %", row["roa"]),
            )
            for column, (text, sort_value) in enumerate(values):
                table.setItem(row_index, column, table_item(text, sort_value=sort_value))
        table.setSortingEnabled(True)
        layout.addWidget(table, 1)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)


class DataBrowser(QWidget):
    def __init__(self, model: AdminModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self._browser_data: dict[str, list[dict[str, Any]]] = {
            "epochs": [], "blocks": [], "bonuses": []
        }
        layout = QVBoxLayout(self)
        title = QLabel("Consultation des données")
        title.setObjectName("sectionTitle")
        subtitle = QLabel(
            "Vue en lecture seule des snapshots JSON canoniques — même contrat métier que les pages PHP."
        )
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._build_pool_tab()
        self._build_accounts_tab()
        self._build_delegators_tab()
        self._build_blocks_tab()
        self._build_bonus_tab()

    def _build_pool_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.pool_count = QLabel()
        self.pool_count.setObjectName("muted")
        layout.addWidget(self.pool_count)
        self.pool_table = setup_table(
            ["Epoch", "État", "Stake", "Variation", "Rewards", "Délégataires", "Blocs", "Cumul blocs", "ROA"]
        )
        layout.addWidget(self.pool_table, 1)
        self.tabs.addTab(page, "Pool")

    def _build_accounts_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        explanation = QLabel(
            "Vue historique conservée : propriétaires et délégataires du snapshot live."
        )
        explanation.setObjectName("muted")
        layout.addWidget(explanation)
        self.accounts_table = setup_table(
            ["Rôle", "Stake address", "Stake", "Reward epoch", "Rewards cumulées", "Loyauté", "Epochs"]
        )
        layout.addWidget(self.accounts_table, 1)
        self.tabs.addTab(page, "Comptes")

    def _build_delegators_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.delegator_search = QLineEdit()
        self.delegator_search.setPlaceholderText("Rechercher une stake_address…")
        self.delegator_search.setClearButtonEnabled(True)
        self.delegator_search.textChanged.connect(self._fill_delegators)
        self.delegator_count = QLabel()
        self.delegator_count.setObjectName("muted")
        controls.addWidget(self.delegator_search, 1)
        controls.addWidget(self.delegator_count)
        layout.addLayout(controls)
        self.delegator_table = setup_table(
            ["Stake address", "Stake", "Variation", "Reward epoch", "Rewards cumulées", "Bonus", "Loyauté", "Epochs"]
        )
        self.delegator_table.itemDoubleClicked.connect(self._open_delegator)
        layout.addWidget(self.delegator_table, 1)
        hint = QLabel("Double-cliquer sur une ligne pour afficher l’historique complet.")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.tabs.addTab(page, "Délégataires")

    def _build_blocks_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.blocks_count = QLabel()
        self.blocks_count.setObjectName("muted")
        layout.addWidget(self.blocks_count)
        self.blocks_table = setup_table(
            ["Epoch", "Hash", "Hauteur", "Slot", "Date Unix", "Transactions", "Frais", "Valeur"]
        )
        layout.addWidget(self.blocks_table, 1)
        self.tabs.addTab(page, "Blocs")

    def _build_bonus_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.bonus_count = QLabel()
        self.bonus_count.setObjectName("muted")
        layout.addWidget(self.bonus_count)
        self.bonus_table = setup_table(
            ["Epoch", "Stake address", "Montant", "Cumul", "Actifs"]
        )
        layout.addWidget(self.bonus_table, 1)
        self.tabs.addTab(page, "Bonus")

    def refresh(self) -> None:
        self._browser_data = self.model.browser_data()
        self._fill_pool()
        self._fill_accounts()
        self._fill_delegators()
        self._fill_blocks()
        self._fill_bonus()

    def _fill_pool(self) -> None:
        rows = self._browser_data["epochs"]
        self.pool_count.setText(f"{len(rows)} epochs disponibles")
        table = self.pool_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = (
                (row["epoch"], row["epoch"]),
                ("Live" if row["state"] == "live" else "Archivé", row["state"]),
                (ada(row["stake"]), row["stake"]),
                (ada(row["stake_diff"]), row["stake_diff"]),
                (ada(row["rewards"]), row["rewards"]),
                (row["delegators"], row["delegators"]),
                (row["blocks"], row["blocks"]),
                (row["blocks_sum"], row["blocks_sum"]),
                (f"{row['roa']:.2f} %", row["roa"]),
            )
            for column, (text, sort_value) in enumerate(values):
                table.setItem(index, column, table_item(text, sort_value=sort_value))
        table.setSortingEnabled(True)

    def _fill_accounts(self) -> None:
        rows = self.model.account_table()
        table = self.accounts_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                tooltip = value if column == 1 else ""
                visible = compact(value) if column == 1 else value
                table.setItem(row_index, column, table_item(visible, tooltip=tooltip))
        table.setSortingEnabled(True)

    def _fill_delegators(self) -> None:
        rows = self.model.delegator_rows(self.delegator_search.text())
        self.delegator_count.setText(f"{len(rows)} délégataires")
        table = self.delegator_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            address = row["stake_address"]
            values = (
                (compact(address), address, address),
                (ada(row["stake"]), row["stake"], ""),
                (ada(row["stake_diff"]), row["stake_diff"], ""),
                (ada(row["rewards"]), row["rewards"], ""),
                (ada(row["rewards_sum"]), row["rewards_sum"], ""),
                (ada(row["bonus"]), row["bonus"], ""),
                (f"{row['loyalty']:.2f} %", row["loyalty"], ""),
                (row["epoch_count"], row["epoch_count"], ""),
            )
            for column, (text, sort_value, tooltip) in enumerate(values):
                table.setItem(index, column, table_item(text, sort_value=sort_value, tooltip=tooltip))
        table.setSortingEnabled(True)

    def _open_delegator(self, item: QTableWidgetItem) -> None:
        address_item = self.delegator_table.item(item.row(), 0)
        if address_item is None:
            return
        address = str(address_item.data(Qt.ItemDataRole.UserRole) or "")
        if address:
            DelegatorDialog(self.model, address, self).exec()

    def _fill_blocks(self) -> None:
        rows = self._browser_data["blocks"]
        self.blocks_count.setText(f"{len(rows)} blocs produits")
        table = self.blocks_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            block_hash = str(row.get("hash") or "")
            values = (
                (row.get("epoch", 0), int(row.get("epoch", 0) or 0), ""),
                (compact(block_hash, 12, 8), block_hash, block_hash),
                (row.get("height", 0), int(row.get("height", 0) or 0), ""),
                (row.get("slot", 0), int(row.get("slot", 0) or 0), ""),
                (row.get("time", 0), int(row.get("time", 0) or 0), ""),
                (row.get("tx_count", 0), int(row.get("tx_count", 0) or 0), ""),
                (ada(int(row.get("fees", 0) or 0)), int(row.get("fees", 0) or 0), ""),
                (ada(int(row.get("output", 0) or 0)), int(row.get("output", 0) or 0), ""),
            )
            for column, (text, sort_value, tooltip) in enumerate(values):
                table.setItem(index, column, table_item(text, sort_value=sort_value, tooltip=tooltip))
        table.setSortingEnabled(True)

    def _fill_bonus(self) -> None:
        rows = self._browser_data["bonuses"]
        self.bonus_count.setText(f"{len(rows)} attributions de bonus")
        table = self.bonus_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            address = row["stake_address"]
            values = (
                (row["epoch"], row["epoch"], ""),
                (compact(address), address, address),
                (ada(row["amount"]), row["amount"], ""),
                (ada(row["sum"]), row["sum"], ""),
                (len(row["assets"]), len(row["assets"]), ""),
            )
            for column, (text, sort_value, tooltip) in enumerate(values):
                table.setItem(index, column, table_item(text, sort_value=sort_value, tooltip=tooltip))
        table.setSortingEnabled(True)
