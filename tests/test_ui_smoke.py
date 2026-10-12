from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from opencodex_switcher.application import build_window
from opencodex_switcher.ui.dialogs import ConfigEditorDialog


def test_window_builds_with_isolated_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    app = QApplication.instance() or QApplication([])

    window = build_window()

    assert window.stack.count() == 6
    assert len(window.provider_store.load()) >= 8
    assert window.dashboard_page.config_path_label.text().endswith("config.toml")
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.title_bar.close_button.text() == "×"
    assert window.dashboard_page.codex_path_input is not None
    assert window.dashboard_page.start_codex_button.text() == "启动 Codex"
    assert window.dashboard_page.close_codex_button.text() == "关闭 Codex"
    assert window.environment_page.scope_combo.count() == 2
    assert window.environment_page.variable_name() == "OPENAI_API_KEY"
    assert window.environment_page.value_input.echoMode() == QLineEdit.EchoMode.Password

    editor = ConfigEditorDialog(window.config_manager, window)
    assert editor.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert editor.tabs.count() == 2
    assert editor.provider_combo.currentText() == "openai"
    editor.close()
    window.close()
    app.processEvents()
