from __future__ import annotations

import sys
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .backup_manager import BackupManager
from .codex_process import CodexProcessManager
from .config_manager import ConfigManager
from .connection_tester import ConnectionTester
from .credential_manager import CredentialManager
from .diagnostics import DiagnosticsService
from .paths import AppPaths
from .provider_store import ProviderStore
from .settings_store import SettingsStore
from .ui.main_window import MainWindow
from .ui.style import APP_STYLESHEET
from . import __version__


def build_window() -> MainWindow:
    paths = AppPaths.discover()
    paths.ensure_app_directories()
    provider_store = ProviderStore(paths.provider_file)
    backup_manager = BackupManager(paths.backup_dir)
    config_manager = ConfigManager(paths.config_file, backup_manager)
    credential_manager = CredentialManager()
    connection_tester = ConnectionTester()
    diagnostics = DiagnosticsService(paths, config_manager, credential_manager)
    settings_store = SettingsStore(paths.settings_file)
    codex_process_manager = CodexProcessManager()
    return MainWindow(
        paths,
        provider_store,
        backup_manager,
        config_manager,
        credential_manager,
        connection_tester,
        diagnostics,
        settings_store,
        codex_process_manager,
    )


def main() -> int:
    if "--version" in sys.argv:
        print(__version__)
        return 0
    smoke_test = "--smoke-test" in sys.argv
    app = cast(QApplication, QApplication.instance())
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("OpenCodex Switcher")
    app.setOrganizationName("OpenCodex")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(APP_STYLESHEET)
    window = build_window()
    window.show()
    if smoke_test:
        QTimer.singleShot(150, app.quit)
    return app.exec()
