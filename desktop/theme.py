# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Visual language shared by the CspoE desktop interface."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b1211;
    color: #e9f2ef;
    font-family: "Inter", "Noto Sans", "DejaVu Sans";
    font-size: 13px;
}
QMainWindow { background-color: #08100e; }
QWidget#topBar {
    background-color: #101b18;
    border-bottom: 1px solid #28423a;
}
QLabel#appTitle { font-size: 22px; font-weight: 700; color: #f4faf7; }
QLabel#appSubtitle { color: #86aa9d; }
QLabel#sectionTitle { font-size: 19px; font-weight: 700; color: #f4faf7; }
QLabel#muted { color: #8aa69c; }
QLabel#warning {
    color: #ffd997;
    background: #352a16;
    border: 1px solid #685228;
    border-radius: 8px;
    padding: 10px;
}
QFrame#metricCard, QFrame#panel {
    background-color: #121f1b;
    border: 1px solid #29443a;
    border-radius: 12px;
}
QLabel#metricLabel { color: #88a99d; font-size: 12px; }
QLabel#metricValue { color: #f5fbf8; font-size: 21px; font-weight: 700; }
QTabWidget::pane { border: 0; background: #0b1211; }
QTabBar::tab {
    background: #111b18;
    color: #8fa9a0;
    border: 1px solid #253b34;
    padding: 10px 16px;
    margin-right: 4px;
    min-width: 92px;
}
QTabBar::tab:selected {
    color: #071712;
    background: #63d7aa;
    border-color: #63d7aa;
    font-weight: 700;
}
QTabBar::tab:hover:!selected { background: #183029; color: #e9f2ef; }
QPushButton {
    min-height: 34px;
    border: 1px solid #39745e;
    border-radius: 8px;
    padding: 5px 13px;
    color: #e9f2ef;
    background: #173329;
}
QPushButton:hover { background: #21513f; border-color: #64d9ab; }
QPushButton:pressed { background: #102820; }
QPushButton#primaryButton {
    color: #062018;
    background: #63d7aa;
    border-color: #63d7aa;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background: #82e3bd; }
QPushButton#dangerButton { background: #54252b; border-color: #8f444d; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #091310;
    color: #edf5f2;
    border: 1px solid #2a493e;
    border-radius: 7px;
    padding: 7px;
    selection-background-color: #34765d;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #63d7aa;
}
QTableWidget {
    background: #0d1714;
    alternate-background-color: #101e1a;
    border: 1px solid #263d35;
    border-radius: 9px;
    gridline-color: #1e332c;
    selection-background-color: #245b47;
    selection-color: #ffffff;
}
QHeaderView::section {
    background: #16241f;
    color: #9db5ad;
    border: 0;
    border-right: 1px solid #2a423a;
    border-bottom: 1px solid #2a423a;
    padding: 8px;
    font-weight: 600;
}
QScrollBar:vertical { background: #0b1412; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #315247; border-radius: 6px; min-height: 28px; }
QScrollBar:horizontal { background: #0b1412; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #315247; border-radius: 6px; min-width: 28px; }
QGroupBox {
    border: 1px solid #29443a;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 700;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #77dcb5; }
QStatusBar { background: #101b18; color: #91aba2; border-top: 1px solid #29443a; }
QToolTip { color: #ecf7f3; background: #1b3029; border: 1px solid #4d8c73; }
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b1211"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e9f2ef"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#091310"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#101e1a"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e9f2ef"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#173329"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e9f2ef"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#34765d"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    application.setPalette(palette)
    application.setStyleSheet(STYLESHEET)
