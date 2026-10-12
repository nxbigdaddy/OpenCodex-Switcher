APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #0f172a;
    color: #e2e8f0;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
}
QFrame#TitleBar {
    background: #0b1220;
    border-bottom: 1px solid #243044;
}
QLabel#TitleBarMark {
    background: #2563eb;
    color: white;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 800;
}
QLabel#TitleBarTitle {
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 650;
}
QPushButton#WindowButton, QPushButton#CloseWindowButton {
    background: transparent;
    color: #cbd5e1;
    border: none;
    border-radius: 0;
    padding: 0;
    font-size: 16px;
    font-weight: 400;
}
QPushButton#WindowButton:hover {
    background: #273449;
}
QPushButton#CloseWindowButton:hover {
    background: #dc2626;
    color: white;
}
QFrame#Sidebar {
    background: #111827;
    border-right: 1px solid #243044;
}
QLabel#AppTitle {
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#PageTitle {
    font-size: 24px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#PageSubtitle {
    color: #94a3b8;
}
QListWidget#Navigation {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#Navigation::item {
    padding: 11px 14px;
    margin: 3px 8px;
    border-radius: 7px;
    color: #cbd5e1;
}
QListWidget#Navigation::item:selected {
    background: #2563eb;
    color: white;
}
QListWidget#Navigation::item:hover:!selected {
    background: #1f2937;
}
QFrame#Card {
    background: #162033;
    border: 1px solid #273449;
    border-radius: 10px;
}
QPushButton {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #3b82f6; }
QPushButton:disabled { background: #334155; color: #64748b; }
QPushButton[secondary="true"] {
    background: #243044;
    color: #e2e8f0;
    border: 1px solid #334155;
}
QPushButton[secondary="true"]:hover { background: #334155; }
QPushButton[danger="true"] { background: #b91c1c; }
QPushButton[danger="true"]:hover { background: #dc2626; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: #0b1220;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: #3b82f6;
}
QTableWidget, QListWidget#ProviderList {
    background: #0b1220;
    alternate-background-color: #111b2e;
    border: 1px solid #334155;
    border-radius: 7px;
    gridline-color: #263449;
}
QHeaderView::section {
    background: #1e293b;
    color: #cbd5e1;
    border: none;
    border-right: 1px solid #334155;
    padding: 7px;
}
QTableWidget::item:selected, QListWidget#ProviderList::item:selected {
    background: #1d4ed8;
}
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QScrollBar:vertical {
    background: #111827;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 24px;
    border-radius: 5px;
}
QStatusBar { background: #111827; color: #94a3b8; }
"""
