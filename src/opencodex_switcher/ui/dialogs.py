from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
import tomlkit
from tomlkit.items import Table

from ..config_manager import ConfigManager
from ..models import ALLOWED_REASONING_EFFORTS
from .title_bar import CustomTitleBar


BUILTIN_PROVIDER_IDS = {"openai", "ollama", "lmstudio"}


def _secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("secondary", True)
    return button


class DiffDialog(QDialog):
    def __init__(self, diff: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(820, 620)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(CustomTitleBar(self, "确认 Codex 配置修改"))

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 18)
        label = QLabel(
            "确认后将先备份原配置，再应用下面的修改。API Key 不会写入配置文件。"
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        editor = QPlainTextEdit(diff)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("备份并应用")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        outer.addWidget(body, 1)


class ConfigEditorDialog(QDialog):
    def __init__(self, manager: ConfigManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.manager = manager
        self.snapshot = manager.read()
        self._loading = False
        self._known_provider_ids: set[str] = set()
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(900, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(CustomTitleBar(self, "内置 Codex 配置编辑器"))

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 16, 20, 18)
        description = QLabel(
            "可以通过关键字段表单修改常用设置，也可以直接编辑完整 TOML。"
            "保存前会校验语法、显示差异并自动备份。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #94a3b8;")
        layout.addWidget(description)

        self.tabs = QTabWidget()
        self.basic_tab = QWidget()
        form = QFormLayout(self.basic_tab)
        form.setContentsMargins(14, 16, 14, 14)
        form.setSpacing(12)
        self.model_input = QLineEdit()
        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(True)
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItems(ALLOWED_REASONING_EFFORTS)
        self.context_window = QSpinBox()
        self.context_window.setRange(0, 10_000_000)
        self.context_window.setSpecialValueText("不设置")
        self.provider_name = QLineEdit()
        self.base_url = QLineEdit()
        self.env_key = QLineEdit()
        form.addRow("Model ID", self.model_input)
        form.addRow("Provider ID", self.provider_combo)
        form.addRow("推理强度", self.reasoning_combo)
        form.addRow("上下文窗口", self.context_window)
        form.addRow("服务商显示名称", self.provider_name)
        form.addRow("Base URL", self.base_url)
        form.addRow("API Key 环境变量名", self.env_key)
        hint = QLabel(
            "这里只保存环境变量名称，不保存 API Key。自定义服务商固定使用 Responses API。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b;")
        form.addRow("", hint)

        self.raw_editor = QPlainTextEdit()
        self.raw_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_editor.setTabStopDistance(28)
        self.tabs.addTab(self.basic_tab, "关键配置")
        self.tabs.addTab(self.raw_editor, "原始 TOML")
        layout.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        validate_button = _secondary_button("校验当前内容")
        validate_button.clicked.connect(self._validate)
        reload_button = _secondary_button("重新从磁盘加载")
        reload_button.clicked.connect(self._reload_requested)
        cancel_button = _secondary_button("取消")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("预览并提交")
        save_button.clicked.connect(self._save)
        actions.addWidget(validate_button)
        actions.addWidget(reload_button)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        outer.addWidget(body, 1)

        self.provider_combo.currentTextChanged.connect(self._provider_changed)
        self._load_snapshot(self.snapshot.raw_text)

    def _load_snapshot(self, raw_text: str) -> None:
        self._loading = True
        document = tomlkit.parse(raw_text) if raw_text.strip() else tomlkit.document()
        self.raw_editor.setPlainText(raw_text)
        self.raw_editor.document().setModified(False)
        self.model_input.setText(str(document.get("model", "")))
        provider_id = str(document.get("model_provider", "openai"))
        providers = document.get("model_providers")
        provider_ids = set(BUILTIN_PROVIDER_IDS)
        if isinstance(providers, Table):
            provider_ids.update(str(key) for key in providers.keys())
        provider_ids.add(provider_id)
        self._known_provider_ids = provider_ids
        self.provider_combo.clear()
        self.provider_combo.addItems(sorted(provider_ids))
        self.provider_combo.setCurrentText(provider_id)
        self.reasoning_combo.setCurrentText(
            str(document.get("model_reasoning_effort", ""))
        )
        context = document.get("model_context_window", 0)
        self.context_window.setValue(int(context) if context else 0)
        self._populate_provider_details(provider_id, document)
        self._loading = False

    def _populate_provider_details(self, provider_id: str, document: object) -> None:
        providers = (
            document.get("model_providers") if hasattr(document, "get") else None
        )
        provider_table = (
            providers.get(provider_id) if isinstance(providers, Table) else None
        )
        is_builtin = provider_id in BUILTIN_PROVIDER_IDS
        if isinstance(provider_table, Table):
            self.provider_name.setText(str(provider_table.get("name", provider_id)))
            self.base_url.setText(str(provider_table.get("base_url", "")))
            self.env_key.setText(str(provider_table.get("env_key", "")))
        else:
            self.provider_name.setText(
                "OpenAI" if provider_id == "openai" else provider_id
            )
            self.base_url.clear()
            self.env_key.setText("OPENAI_API_KEY" if provider_id == "openai" else "")
        for widget in (self.provider_name, self.base_url, self.env_key):
            widget.setEnabled(not is_builtin)

    def _provider_changed(self, provider_id: str) -> None:
        if self._loading:
            return
        if provider_id in self._known_provider_ids:
            try:
                document = (
                    tomlkit.parse(self.raw_editor.toPlainText())
                    if self.raw_editor.toPlainText().strip()
                    else tomlkit.document()
                )
            except Exception:
                return
            self._populate_provider_details(provider_id, document)
            return
        is_builtin = provider_id in BUILTIN_PROVIDER_IDS
        for widget in (self.provider_name, self.base_url, self.env_key):
            widget.setEnabled(not is_builtin)

    def _candidate_text(self) -> str:
        raw_text = self.raw_editor.toPlainText()
        if self.tabs.currentWidget() is self.raw_editor:
            tomlkit.parse(raw_text)
            return raw_text
        rendered = self.manager.render_basic_edit(
            raw_text,
            model=self.model_input.text(),
            provider_id=self.provider_combo.currentText(),
            reasoning_effort=self.reasoning_combo.currentText(),
            context_window=self.context_window.value() or None,
            provider_name=self.provider_name.text(),
            base_url=self.base_url.text(),
            env_key=self.env_key.text(),
        )
        self.raw_editor.setPlainText(rendered)
        return rendered

    def _validate(self) -> None:
        try:
            self._candidate_text()
        except Exception as exc:
            QMessageBox.warning(self, "配置校验失败", str(exc))
            return
        QMessageBox.information(
            self,
            "配置有效",
            "当前内容可以被解析，关键字段格式有效。",
            QMessageBox.StandardButton.Ok,
        )

    def _reload_requested(self) -> None:
        answer = QMessageBox.question(
            self,
            "重新加载",
            "重新加载会丢弃编辑器中尚未提交的修改，是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.snapshot = self.manager.read()
        self._load_snapshot(self.snapshot.raw_text)

    def _save(self) -> None:
        try:
            candidate = self._candidate_text()
            current, diff = self.manager.render_raw_diff(candidate)
        except Exception as exc:
            QMessageBox.warning(self, "配置校验失败", str(exc))
            return
        if current.digest != self.snapshot.digest:
            QMessageBox.warning(
                self,
                "配置已变化",
                "磁盘上的 Codex 配置已被其他程序修改。请重新加载后合并修改。",
            )
            return
        if diff == "配置没有变化。":
            QMessageBox.information(
                self,
                "没有变化",
                "当前内容与磁盘配置一致，无需提交。",
                QMessageBox.StandardButton.Ok,
            )
            return
        if DiffDialog(diff, self).exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.manager.apply_raw_text(candidate, expected_digest=self.snapshot.digest)
        except Exception as exc:
            QMessageBox.critical(self, "配置提交失败", str(exc))
            return
        self.accept()
