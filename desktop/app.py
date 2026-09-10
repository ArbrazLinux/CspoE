# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""PySide6 administration interface for the canonical CspoE engine."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import settings
from core.version import ENGINE_VERSION
from desktop.data_tab import DataBrowser
from desktop.model import AdminModel, ada
from desktop.theme import apply_theme
from desktop.transaction_tabs import DRepTools, OperatorTransactions


class MetricCard(QFrame):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        caption = QLabel(label)
        caption.setObjectName("metricLabel")
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(caption)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Vue d’ensemble")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("État du dernier snapshot canonique et de la chaîne de finalisation.")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        labels = (
            ("epoch", "Epoch live"),
            ("finalized", "Chaîne finalisée"),
            ("settled", "Rewards stabilisées"),
            ("stake", "Stake du pool"),
            ("rewards", "Rewards de l’epoch"),
            ("rewards_sum", "Rewards cumulées"),
            ("blocks", "Blocs epoch / cumul"),
            ("delegators", "Délégataires"),
            ("owners", "Propriétaires"),
            ("roa", "ROA du pool"),
        )
        self.cards: dict[str, MetricCard] = {}
        for index, (key, label) in enumerate(labels):
            card = MetricCard(label)
            self.cards[key] = card
            grid.addWidget(card, index // 3, index % 3)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_title = QLabel("Principe de sécurité")
        panel_title.setObjectName("sectionTitle")
        policy = QLabel(
            "Les snapshots JSON restent la source de vérité. MySQL et PHP sont des projections. "
            "Les assistants Cardano ne signent et ne soumettent aucune transaction."
        )
        policy.setObjectName("muted")
        policy.setWordWrap(True)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(policy)
        layout.addWidget(panel)
        layout.addStretch(1)

    def refresh(self, summary: dict) -> None:
        state = summary.get("state") if isinstance(summary.get("state"), dict) else {}
        self.cards["epoch"].set_value(str(summary.get("epoch", "—")))
        self.cards["finalized"].set_value(str(state.get("last_chain_finalized_epoch", "—")))
        self.cards["settled"].set_value(str(state.get("last_rewards_settled_epoch", "—")))
        self.cards["stake"].set_value(ada(summary.get("stake", 0)))
        self.cards["rewards"].set_value(ada(summary.get("rewards", 0)))
        self.cards["rewards_sum"].set_value(ada(summary.get("rewards_sum", 0)))
        self.cards["blocks"].set_value(
            f"{summary.get('blocks', 0)} / {summary.get('blocks_sum', 0)}"
        )
        self.cards["delegators"].set_value(str(summary.get("delegators", 0)))
        self.cards["owners"].set_value(str(summary.get("owners", 0)))
        self.cards["roa"].set_value(f"{float(summary.get('roa', 0) or 0):.2f} %")


class AdminWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{settings.pool_ticker} — CspoE {ENGINE_VERSION}")
        self.resize(1460, 920)
        self.setMinimumSize(1050, 700)
        self.model = AdminModel(Path(settings.data_dir) / "CspoE")
        self.process: QProcess | None = None

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._top_bar())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.dashboard = DashboardPage()
        self.data_browser = DataBrowser(self.model)
        drafts_directory = self.model.store.data_root / "transaction_drafts"
        self.tabs.addTab(self.dashboard, "Vue d’ensemble")
        self.tabs.addTab(self.data_browser, "Données")
        self.tabs.addTab(OperatorTransactions(drafts_directory), "Transactions")
        self.tabs.addTab(DRepTools(drafts_directory), "DRep")
        self.tabs.addTab(self._administration_page(), "Administration")
        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Prêt")
        self.refresh()

    def _top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 12, 20, 12)
        titles = QVBoxLayout()
        title = QLabel("CspoE · Console opérateur")
        title.setObjectName("appTitle")
        subtitle = QLabel(f"Moteur {ENGINE_VERSION} · snapshots canoniques et outils contrôlés")
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        layout.addLayout(titles)
        layout.addStretch(1)
        refresh = QPushButton("Actualiser les données")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        return bar

    def _administration_page(self) -> QWidget:
        operations = QWidget()
        layout = QVBoxLayout(operations)
        title = QLabel("Administration du moteur")
        title.setObjectName("sectionTitle")
        subtitle = QLabel(
            "Les boutons appellent les scripts canoniques existants et conservent leurs validations."
        )
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        parameters = QGroupBox("Paramètres")
        form = QFormLayout(parameters)
        self.observed_epoch = QLineEdit()
        self.observed_epoch.setPlaceholderText("ex. 655")
        form.addRow("Epoch observé", self.observed_epoch)
        first_epoch = QLineEdit(str(settings.pool_first_epoch or "non configurée"))
        first_epoch.setReadOnly(True)
        form.addRow("Première epoch active", first_epoch)
        layout.addWidget(parameters)

        actions = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions)
        button_rows = (
            (
                ("Observer Blockfrost", self.observe, False),
                ("Réconciliation dry-run", lambda: self.reconcile(False), False),
                ("Réconciliation écriture", lambda: self.reconcile(True), True),
            ),
            (
                ("Valider les données", self.validate_data, False),
                ("Initialisation dry-run", lambda: self.initialize("dry-run"), False),
                ("Construire / reprendre le staging", lambda: self.initialize("write"), True),
                ("Activer le staging", lambda: self.initialize("activate"), True),
            ),
            (
                ("Pooldata dry-run", lambda: self.pooldata(False), False),
                ("Exporter pooldata", lambda: self.pooldata(True), True),
                ("MySQL statut", self.mysql_status, False),
                ("MySQL dry-run", lambda: self.mysql_sync(False), False),
                ("MySQL synchroniser", lambda: self.mysql_sync(True), True),
            ),
            (
                ("MySQL legacy dry-run", lambda: self.mysql_legacy_sync(False), False),
                ("MySQL legacy synchroniser", lambda: self.mysql_legacy_sync(True), True),
            ),
        )
        for definitions in button_rows:
            row = QHBoxLayout()
            for label, callback, dangerous in definitions:
                button = QPushButton(label)
                if dangerous:
                    button.setObjectName("dangerButton")
                button.clicked.connect(callback)
                row.addWidget(button)
            row.addStretch(1)
            actions_layout.addLayout(row)
        layout.addWidget(actions)

        log_group = QGroupBox("Journal d’exécution")
        log_layout = QVBoxLayout(log_group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.setMinimumHeight(230)
        log_layout.addWidget(self.log)
        layout.addWidget(log_group, 1)
        return operations

    def refresh(self) -> None:
        try:
            self.dashboard.refresh(self.model.dashboard())
            self.data_browser.refresh()
            self.statusBar().showMessage("Données locales actualisées", 5000)
        except Exception as exc:
            self.statusBar().showMessage("Données locales indisponibles", 8000)
            QMessageBox.warning(self, "CspoE", f"Données indisponibles : {exc}")

    def run_script(self, script: str, arguments: list[str]) -> None:
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.warning(self, "CspoE", "Une opération est déjà en cours.")
            return
        self.log.append(f"\n$ {Path(sys.executable).name} {script} {' '.join(arguments)}")
        process = QProcess(self)
        process.setWorkingDirectory(str(ROOT))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(
            lambda: self.log.append(
                bytes(process.readAllStandardOutput())
                .decode("utf-8", errors="replace")
                .rstrip()
            )
        )
        process.finished.connect(lambda code, _status: self.operation_finished(code))
        self.process = process
        self.statusBar().showMessage("Opération en cours…")
        process.start(sys.executable, [str(ROOT / "scripts" / script), *arguments])

    def operation_finished(self, code: int) -> None:
        self.log.append(f"[fin — code {code}]")
        self.statusBar().showMessage(f"Opération terminée — code {code}", 8000)
        process = self.process
        self.process = None
        if process is not None:
            process.deleteLater()
        self.refresh()

    def confirmed(self, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Confirmation CspoE",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def observe(self) -> None:
        self.run_script("CspoE_epoch_manager.py", ["observe"])

    def reconcile(self, write: bool) -> None:
        epoch = self.observed_epoch.text().strip()
        if not epoch.isdigit():
            QMessageBox.warning(self, "CspoE", "Renseigner un epoch observé entier.")
            return
        if write and not self.confirmed(
            f"Écrire transactionnellement la fenêtre de rewards pour l'epoch observé {epoch} ?"
        ):
            return
        arguments = ["--observed-epoch", epoch]
        if write:
            arguments.append("--write")
        self.run_script("CspoE_reward_window.py", arguments)

    def validate_data(self) -> None:
        self.run_script("CspoE_validate_data.py", [])

    def initialize(self, mode: str) -> None:
        checkpoint = self.model.store.data_root / "init" / "reconstructed" / "initialization_checkpoint.json"
        if mode == "dry-run":
            if not self.confirmed(
                "Le dry-run utilise un répertoire temporaire, consomme des requêtes Blockfrost "
                "et ne peut pas être repris. Continuer ?"
            ):
                return
            arguments: list[str] = []
        elif mode == "write":
            if not self.confirmed(
                "Construire ou reprendre toutes les epochs depuis POOL_FIRST_EPOCH dans le staging ? "
                "L'archive canonique ne sera pas écrasée."
            ):
                return
            arguments = ["--write"]
            if checkpoint.is_file():
                arguments.append("--resume")
        elif mode == "activate":
            if not checkpoint.is_file():
                QMessageBox.warning(self, "CspoE", "Aucun checkpoint de staging à activer.")
                return
            if not self.confirmed(
                "Valider/reprendre le staging puis l'activer ? L'activation reste refusée "
                "si des données canoniques existent déjà."
            ):
                return
            arguments = ["--write", "--resume", "--activate"]
        else:
            QMessageBox.warning(self, "CspoE", f"Mode d'initialisation inconnu : {mode}")
            return
        self.run_script("CspoE_initialize.py", arguments)

    def pooldata(self, write: bool) -> None:
        if write and not self.confirmed("Mettre à jour la projection pooldata du site ?"):
            return
        self.run_script("CspoE_pooldata_export.py", ["--write"] if write else [])

    def mysql_status(self) -> None:
        self.run_script("CspoE_mysql_sync.py", ["status"])

    def mysql_sync(self, write: bool) -> None:
        if write and not self.confirmed(
            "Synchroniser tous les snapshots canoniques vers MySQL ?"
        ):
            return
        arguments = ["sync", "--include-live"]
        if write:
            arguments.append("--write")
        self.run_script("CspoE_mysql_sync.py", arguments)

    def mysql_legacy_sync(self, write: bool) -> None:
        if write and not self.confirmed(
            "Reconstruire transactionnellement les 11 tables MySQL historiques "
            "depuis tous les snapshots canoniques ? Une sauvegarde SQL préalable est recommandée."
        ):
            return
        arguments = ["legacy-sync", "--include-live"]
        if write:
            arguments.append("--write")
        self.run_script("CspoE_mysql_sync.py", arguments)


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("CspoE")
    application.setOrganizationName("CspoE")
    apply_theme(application)
    window = AdminWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
