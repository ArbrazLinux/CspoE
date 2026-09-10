# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Read-only command-plan assistants for operator and DRep workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.transaction_drafts import (
    DraftStore,
    DraftValidationError,
    bonus_distribution_draft,
    drep_vote_draft,
    operational_certificate_draft,
)


def network_controls() -> tuple[QComboBox, QSpinBox, QWidget]:
    network = QComboBox()
    network.addItem("Mainnet", "mainnet")
    network.addItem("Testnet", "testnet")
    magic = QSpinBox()
    magic.setRange(0, 2_147_483_647)
    magic.setValue(1)
    magic.setEnabled(False)
    network.currentIndexChanged.connect(
        lambda: magic.setEnabled(network.currentData() == "testnet")
    )
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(network)
    layout.addWidget(QLabel("Magic"))
    layout.addWidget(magic)
    return network, magic, container


class DraftPanel(QWidget):
    def __init__(self, store: DraftStore, title: str, explanation: str) -> None:
        super().__init__()
        self.store = store
        self.current_draft: dict[str, Any] | None = None
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        subtitle = QLabel(explanation)
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        self.content_layout.addWidget(heading)
        self.content_layout.addWidget(subtitle)

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.content)
        root.addWidget(scroll)

    def add_policy_banner(self, text: str) -> None:
        banner = QLabel(text)
        banner.setObjectName("warning")
        banner.setWordWrap(True)
        self.content_layout.addWidget(banner)

    def add_preview(self) -> None:
        group = QGroupBox("Brouillon généré")
        layout = QVBoxLayout(group)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(180)
        self.preview.setPlaceholderText("Compléter le formulaire puis générer le brouillon.")
        layout.addWidget(self.preview)
        buttons = QHBoxLayout()
        copy = QPushButton("Copier les commandes")
        copy.clicked.connect(self.copy_commands)
        save = QPushButton("Enregistrer le brouillon JSON")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save_draft)
        buttons.addStretch(1)
        buttons.addWidget(copy)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.content_layout.addWidget(group)
        self.content_layout.addStretch(1)

    def generate(self, factory: Callable[[], dict[str, Any]]) -> None:
        try:
            draft = factory()
        except DraftValidationError as error:
            self.current_draft = None
            QMessageBox.warning(self, "Brouillon invalide", str(error))
            return
        except Exception as error:
            self.current_draft = None
            QMessageBox.critical(self, "CspoE", f"Impossible de préparer le brouillon : {error}")
            return
        self.current_draft = draft
        lines = [
            "POLITIQUE : préparation uniquement — aucune exécution, signature ou soumission.",
            "",
        ]
        for command in draft.get("commands", []):
            location = " — HORS LIGNE UNIQUEMENT" if command.get("offline_only") else ""
            lines.extend([f"[{command.get('role', 'commande')}{location}]", "$ " + command["preview"], ""])
        warnings = draft.get("warnings", [])
        if warnings:
            lines.append("CONTRÔLES OBLIGATOIRES")
            lines.extend(f"• {warning}" for warning in warnings)
        self.preview.setPlainText("\n".join(lines).rstrip())

    def copy_commands(self) -> None:
        if self.current_draft is None:
            QMessageBox.information(self, "CspoE", "Générer d’abord un brouillon valide.")
            return
        text = "\n\n".join(
            command["preview"] for command in self.current_draft.get("commands", [])
        )
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "CspoE", "Commandes copiées dans le presse-papiers.")

    def save_draft(self) -> None:
        if self.current_draft is None:
            QMessageBox.information(self, "CspoE", "Générer d’abord un brouillon valide.")
            return
        try:
            path = self.store.save(self.current_draft)
        except Exception as error:
            QMessageBox.critical(self, "CspoE", f"Enregistrement impossible : {error}")
            return
        QMessageBox.information(
            self,
            "Brouillon enregistré",
            f"Le plan a été enregistré avec des permissions restrictives :\n{path}",
        )


class BonusDistributionPanel(DraftPanel):
    def __init__(self, store: DraftStore) -> None:
        super().__init__(
            store,
            "Distribution de bonus en ADA",
            "Prépare une transaction non signée avec une sortie explicite par destinataire.",
        )
        self.add_policy_banner(
            "Saisir des adresses de paiement addr1/addr_test1. Une stake_address n’est pas une destination UTxO et ne sera jamais résolue automatiquement."
        )
        group = QGroupBox("Paramètres")
        form = QFormLayout(group)
        self.recipients = QPlainTextEdit()
        self.recipients.setPlaceholderText(
            "Une ligne par destinataire :\naddr1… ; 12,500000\naddr1… ; 3.25"
        )
        self.recipients.setMinimumHeight(130)
        self.tx_in = QLineEdit()
        self.tx_in.setPlaceholderText("64 caractères hexadécimaux#index")
        self.change_address = QLineEdit()
        self.change_address.setPlaceholderText("addr1…")
        self.network, self.magic, network_widget = network_controls()
        self.out_file = QLineEdit("bonus-tx.raw")
        form.addRow("Destinataires", self.recipients)
        form.addRow("UTxO d’entrée", self.tx_in)
        form.addRow("Adresse de change", self.change_address)
        form.addRow("Réseau", network_widget)
        form.addRow("Transaction non signée", self.out_file)
        self.content_layout.addWidget(group)
        generate = QPushButton("Générer le brouillon de transaction")
        generate.setObjectName("primaryButton")
        generate.clicked.connect(
            lambda: self.generate(
                lambda: bonus_distribution_draft(
                    recipients_text=self.recipients.toPlainText(),
                    tx_in=self.tx_in.text(),
                    change_address=self.change_address.text(),
                    network=str(self.network.currentData()),
                    testnet_magic=self.magic.value(),
                    out_file=self.out_file.text(),
                )
            )
        )
        self.content_layout.addWidget(generate)
        self.add_preview()


class OperationalCertificatePanel(DraftPanel):
    def __init__(self, store: DraftStore) -> None:
        super().__init__(
            store,
            "Certificat opérationnel / rotation KES",
            "Prépare la commande cardano-cli node issue-op-cert et son dossier de contrôle.",
        )
        self.add_policy_banner(
            "OPÉRATION HORS LIGNE : cold.skey ne doit jamais être copié sur le serveur CspoE connecté. Cette interface n’exécute pas la commande."
        )
        group = QGroupBox("Fichiers et période")
        form = QFormLayout(group)
        self.kes_vkey = QLineEdit("kes.vkey")
        self.cold_skey = QLineEdit("cold.skey")
        self.counter = QLineEdit("cold.counter")
        self.kes_period = QSpinBox()
        self.kes_period.setRange(0, 2_147_483_647)
        self.out_file = QLineEdit("opcert.cert")
        form.addRow("Clé KES publique", self.kes_vkey)
        form.addRow("Clé froide de signature", self.cold_skey)
        form.addRow("Compteur opérationnel", self.counter)
        form.addRow("Période KES", self.kes_period)
        form.addRow("Certificat de sortie", self.out_file)
        self.content_layout.addWidget(group)
        generate = QPushButton("Préparer la commande hors ligne")
        generate.setObjectName("primaryButton")
        generate.clicked.connect(
            lambda: self.generate(
                lambda: operational_certificate_draft(
                    kes_verification_key_file=self.kes_vkey.text(),
                    cold_signing_key_file=self.cold_skey.text(),
                    counter_file=self.counter.text(),
                    kes_period=self.kes_period.value(),
                    out_file=self.out_file.text(),
                )
            )
        )
        self.content_layout.addWidget(generate)
        self.add_preview()


class OperatorTransactions(QWidget):
    def __init__(self, drafts_directory: str | Path) -> None:
        super().__init__()
        store = DraftStore(drafts_directory)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(BonusDistributionPanel(store), "Bonus ADA")
        tabs.addTab(OperationalCertificatePanel(store), "Certificat opérationnel")
        layout.addWidget(tabs)


class DRepVotePanel(DraftPanel):
    def __init__(self, store: DraftStore) -> None:
        super().__init__(
            store,
            "Vote DRep",
            "Prépare le fichier de vote et la transaction non signée correspondante.",
        )
        self.add_policy_banner(
            "Vérifier l’action de gouvernance, son index et son ancre avant de voter. La signature DRep et la soumission ne sont pas réalisées par CspoE."
        )
        group = QGroupBox("Action et vote")
        form = QFormLayout(group)
        self.action_tx_id = QLineEdit()
        self.action_tx_id.setPlaceholderText("tx-id hexadécimal de 64 caractères")
        self.action_index = QSpinBox()
        self.action_index.setRange(0, 65535)
        self.decision = QComboBox()
        self.decision.addItem("Oui", "yes")
        self.decision.addItem("Non", "no")
        self.decision.addItem("Abstention", "abstain")
        self.drep_vkey = QLineEdit("drep.vkey")
        self.vote_file = QLineEdit("action.vote")
        self.tx_in = QLineEdit()
        self.tx_in.setPlaceholderText("64 caractères hexadécimaux#index")
        self.change_address = QLineEdit()
        self.change_address.setPlaceholderText("addr1…")
        self.network, self.magic, network_widget = network_controls()
        self.tx_out = QLineEdit("vote-tx.raw")
        form.addRow("Tx-id de l’action", self.action_tx_id)
        form.addRow("Index de l’action", self.action_index)
        form.addRow("Décision", self.decision)
        form.addRow("Clé DRep publique", self.drep_vkey)
        form.addRow("Fichier de vote", self.vote_file)
        form.addRow("UTxO d’entrée", self.tx_in)
        form.addRow("Adresse de change", self.change_address)
        form.addRow("Réseau", network_widget)
        form.addRow("Transaction non signée", self.tx_out)
        self.content_layout.addWidget(group)
        generate = QPushButton("Générer le brouillon de vote")
        generate.setObjectName("primaryButton")
        generate.clicked.connect(
            lambda: self.generate(
                lambda: drep_vote_draft(
                    governance_action_tx_id=self.action_tx_id.text(),
                    governance_action_index=self.action_index.value(),
                    decision=str(self.decision.currentData()),
                    drep_verification_key_file=self.drep_vkey.text(),
                    vote_file=self.vote_file.text(),
                    tx_in=self.tx_in.text(),
                    change_address=self.change_address.text(),
                    network=str(self.network.currentData()),
                    testnet_magic=self.magic.value(),
                    transaction_out_file=self.tx_out.text(),
                )
            )
        )
        self.content_layout.addWidget(generate)
        self.add_preview()


class DRepTools(QWidget):
    def __init__(self, drafts_directory: str | Path) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(DRepVotePanel(DraftStore(drafts_directory)), "Préparer un vote")
        layout.addWidget(tabs)
