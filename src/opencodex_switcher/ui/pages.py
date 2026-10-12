from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..backup_manager import BackupManager
from ..diagnostics import DiagnosticItem
from ..models import (
    ALLOWED_REASONING_EFFORTS,
    ConfigSnapshot,
    ConnectionReport,
    ModelProfile,
    ProviderProfile,
)
from ..provider_store import ProviderStore


def page_header(title: str, subtitle: str) -> tuple[QLabel, QLabel]:
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)
    return title_label, subtitle_label


def secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("secondary", True)
    return button


class StatusCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        caption = QLabel(title)
        caption.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.value = QLabel("—")
        self.value.setWordWrap(True)
        self.value.setStyleSheet("font-size: 16px; font-weight: 650; color: #f8fafc;")
        layout.addWidget(caption)
        layout.addWidget(self.value)


class DashboardPage(QWidget):
    refresh_requested = Signal()
    test_requested = Signal()
    edit_config_requested = Signal()
    restore_requested = Signal()
    browse_codex_requested = Signal()
    detect_codex_requested = Signal()
    save_codex_path_requested = Signal(str)
    start_codex_requested = Signal(str)
    close_codex_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        title, subtitle = page_header(
            "当前配置", "查看用户级 Codex 配置、密钥状态和最近一次切换结果。"
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.provider_card = StatusCard("服务商")
        self.model_card = StatusCard("模型")
        self.url_card = StatusCard("Base URL")
        self.key_card = StatusCard("API Key")
        cards.addWidget(self.provider_card, 0, 0)
        cards.addWidget(self.model_card, 0, 1)
        cards.addWidget(self.url_card, 1, 0)
        cards.addWidget(self.key_card, 1, 1)
        layout.addLayout(cards)

        config_box = QFrame()
        config_box.setObjectName("Card")
        config_layout = QVBoxLayout(config_box)
        config_layout.setContentsMargins(16, 14, 16, 14)
        self.config_path_label = QLabel()
        self.config_path_label.setWordWrap(True)
        self.config_state_label = QLabel()
        self.config_state_label.setStyleSheet("color: #94a3b8;")
        config_layout.addWidget(QLabel("配置文件"))
        config_layout.addWidget(self.config_path_label)
        config_layout.addWidget(self.config_state_label)
        layout.addWidget(config_box)

        codex_box = QFrame()
        codex_box.setObjectName("Card")
        codex_layout = QVBoxLayout(codex_box)
        codex_layout.setContentsMargins(16, 14, 16, 14)
        codex_header = QHBoxLayout()
        codex_header.addWidget(QLabel("Codex 程序控制"))
        codex_header.addStretch()
        self.codex_process_status = QLabel("未检测")
        self.codex_process_status.setStyleSheet("color: #94a3b8;")
        codex_header.addWidget(self.codex_process_status)
        codex_layout.addLayout(codex_header)

        path_row = QHBoxLayout()
        self.codex_path_input = QLineEdit()
        self.codex_path_input.setPlaceholderText("选择 Codex 桌面程序的 .exe 文件")
        browse = secondary_button("浏览")
        browse.clicked.connect(self.browse_codex_requested)
        detect = secondary_button("自动检测")
        detect.clicked.connect(self.detect_codex_requested)
        save_path = secondary_button("保存路径")
        save_path.clicked.connect(
            lambda: self.save_codex_path_requested.emit(
                self.codex_path_input.text().strip()
            )
        )
        path_row.addWidget(self.codex_path_input, 1)
        path_row.addWidget(browse)
        path_row.addWidget(detect)
        path_row.addWidget(save_path)
        codex_layout.addLayout(path_row)

        process_actions = QHBoxLayout()
        self.start_codex_button = QPushButton("启动 Codex")
        self.start_codex_button.clicked.connect(
            lambda: self.start_codex_requested.emit(
                self.codex_path_input.text().strip()
            )
        )
        self.close_codex_button = QPushButton("关闭 Codex")
        self.close_codex_button.setProperty("danger", True)
        self.close_codex_button.clicked.connect(
            lambda: self.close_codex_requested.emit(
                self.codex_path_input.text().strip()
            )
        )
        process_actions.addWidget(self.start_codex_button)
        process_actions.addWidget(self.close_codex_button)
        process_actions.addStretch()
        codex_layout.addLayout(process_actions)
        layout.addWidget(codex_box)

        actions = QHBoxLayout()
        refresh = secondary_button("刷新状态")
        refresh.clicked.connect(self.refresh_requested)
        test = QPushButton("测试当前配置")
        test.clicked.connect(self.test_requested)
        edit_config = secondary_button("内置配置编辑器")
        edit_config.clicked.connect(self.edit_config_requested)
        restore = secondary_button("恢复最近备份")
        restore.clicked.connect(self.restore_requested)
        actions.addWidget(refresh)
        actions.addWidget(test)
        actions.addWidget(edit_config)
        actions.addWidget(restore)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def set_snapshot(self, snapshot: ConfigSnapshot, key_configured: bool) -> None:
        self.provider_card.value.setText(
            snapshot.provider_name or snapshot.model_provider or "未设置"
        )
        self.model_card.value.setText(snapshot.model or "未设置")
        self.url_card.value.setText(snapshot.base_url or "内置服务商 / 未设置")
        if snapshot.env_key:
            self.key_card.value.setText(
                f"{snapshot.env_key} · {'已配置' if key_configured else '未找到'}"
            )
        else:
            self.key_card.value.setText("未声明环境变量")
        self.config_path_label.setText(str(snapshot.path))
        if snapshot.exists:
            time_text = (
                snapshot.modified_at.strftime("%Y-%m-%d %H:%M:%S")
                if snapshot.modified_at
                else ""
            )
            self.config_state_label.setText(f"用户级配置 · 最后修改 {time_text}")
        else:
            self.config_state_label.setText("文件尚不存在；首次应用配置时创建。")

    def set_codex_control(
        self, executable: str, running: bool, running_pids: tuple[int, ...]
    ) -> None:
        if executable and self.codex_path_input.text().strip() != executable:
            self.codex_path_input.setText(executable)
        if running:
            pid_text = ", ".join(str(pid) for pid in running_pids)
            self.codex_process_status.setText(f"运行中 · PID {pid_text}")
            self.codex_process_status.setStyleSheet("color: #22c55e;")
        elif executable:
            self.codex_process_status.setText("未运行")
            self.codex_process_status.setStyleSheet("color: #94a3b8;")
        else:
            self.codex_process_status.setText("尚未设置路径")
            self.codex_process_status.setStyleSheet("color: #f59e0b;")
        self.start_codex_button.setEnabled(bool(executable) and not running)
        self.close_codex_button.setEnabled(bool(executable) and running)


class EnvironmentVariablesPage(QWidget):
    load_requested = Signal(str, str)
    save_requested = Signal(str, str, str)
    delete_requested = Signal(str, str)

    PRESET_NAMES = (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "CODEX_HOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    )

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        title, subtitle = page_header(
            "Windows 环境变量",
            "读取、设置或删除 Codex 及模型服务使用的 Windows 环境变量。",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        editor = QFrame()
        editor.setObjectName("Card")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(18, 18, 18, 18)
        editor_layout.setSpacing(14)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("当前用户（推荐，无需管理员权限）", "user")
        self.scope_combo.addItem("整个系统（需要管理员权限）", "system")
        form.addRow("作用范围", self.scope_combo)

        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.name_combo.addItems(self.PRESET_NAMES)
        self.name_combo.setCurrentText("OPENAI_API_KEY")
        form.addRow("变量名称", self.name_combo)

        value_row = QHBoxLayout()
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("输入环境变量值")
        self.show_value = QCheckBox("显示值")
        self.show_value.toggled.connect(self._update_echo_mode)
        value_row.addWidget(self.value_input, 1)
        value_row.addWidget(self.show_value)
        form.addRow("变量值", value_row)
        editor_layout.addLayout(form)

        self.environment_status = QLabel("请选择变量后点击“读取当前值”。")
        self.environment_status.setWordWrap(True)
        self.environment_status.setStyleSheet("color: #94a3b8;")
        editor_layout.addWidget(self.environment_status)

        actions = QHBoxLayout()
        self.load_environment_button = secondary_button("读取当前值")
        self.load_environment_button.clicked.connect(self._request_load)
        self.save_environment_button = QPushButton("保存 / 更新")
        self.save_environment_button.clicked.connect(self._request_save)
        self.delete_environment_button = QPushButton("删除变量")
        self.delete_environment_button.setProperty("danger", True)
        self.delete_environment_button.clicked.connect(self._request_delete)
        actions.addWidget(self.load_environment_button)
        actions.addWidget(self.save_environment_button)
        actions.addWidget(self.delete_environment_button)
        actions.addStretch()
        editor_layout.addLayout(actions)
        layout.addWidget(editor)

        note = QLabel(
            "说明：保存后会通知 Windows 环境已变化，但已经运行的 Codex 不会自动刷新。"
            "请关闭并重新启动 Codex；系统范围写入需要以管理员身份启动本程序。"
        )
        note.setObjectName("PageSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

        self.scope_combo.currentIndexChanged.connect(self._selection_changed)
        self.name_combo.currentTextChanged.connect(self._selection_changed)
        self._update_echo_mode()

    def scope(self) -> str:
        return str(self.scope_combo.currentData())

    def variable_name(self) -> str:
        return self.name_combo.currentText().strip()

    def set_loaded(self, value: str, exists: bool) -> None:
        self.value_input.setText(value if exists else "")
        if exists:
            self.environment_status.setText(
                f"已读取 {self._scope_label()}变量 {self.variable_name()}。"
            )
            self.environment_status.setStyleSheet("color: #22c55e;")
        else:
            self.environment_status.setText(
                f"{self._scope_label()}尚未设置 {self.variable_name()}。"
            )
            self.environment_status.setStyleSheet("color: #f59e0b;")

    def set_saved(self) -> None:
        self.environment_status.setText(
            f"已保存 {self._scope_label()}变量 {self.variable_name()}。"
        )
        self.environment_status.setStyleSheet("color: #22c55e;")

    def set_deleted(self, deleted: bool) -> None:
        self.value_input.clear()
        if deleted:
            text = f"已删除 {self._scope_label()}变量 {self.variable_name()}。"
            color = "#22c55e"
        else:
            text = f"{self._scope_label()}未找到 {self.variable_name()}。"
            color = "#f59e0b"
        self.environment_status.setText(text)
        self.environment_status.setStyleSheet(f"color: {color};")

    def _selection_changed(self) -> None:
        self.value_input.clear()
        self.environment_status.setText("变量选择已改变，请点击“读取当前值”。")
        self.environment_status.setStyleSheet("color: #94a3b8;")
        self.show_value.setChecked(False)
        self._update_echo_mode()

    def _update_echo_mode(self) -> None:
        sensitive = any(
            marker in self.variable_name().upper()
            for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        )
        hidden = sensitive and not self.show_value.isChecked()
        mode = QLineEdit.EchoMode.Password if hidden else QLineEdit.EchoMode.Normal
        self.value_input.setEchoMode(mode)

    def _scope_label(self) -> str:
        return "当前用户" if self.scope() == "user" else "系统范围"

    def _request_load(self) -> None:
        self.load_requested.emit(self.scope(), self.variable_name())

    def _request_save(self) -> None:
        self.save_requested.emit(
            self.scope(), self.variable_name(), self.value_input.text()
        )

    def _request_delete(self) -> None:
        self.delete_requested.emit(self.scope(), self.variable_name())


class ProvidersPage(QWidget):
    providers_changed = Signal()
    test_requested = Signal(object, object, str)
    apply_requested = Signal(object, object)
    save_key_requested = Signal(str, str)

    def __init__(self, store: ProviderStore):
        super().__init__()
        self.store = store
        self.providers: list[ProviderProfile] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        title, subtitle = page_header(
            "服务商与模型",
            "模板只提供起点；请以服务商当前文档为准，并在应用前运行 Responses API 测试。",
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        content = QHBoxLayout()
        content.setSpacing(16)
        left = QVBoxLayout()
        self.provider_list = QListWidget()
        self.provider_list.setObjectName("ProviderList")
        self.provider_list.setMinimumWidth(210)
        self.provider_list.currentRowChanged.connect(self._load_selected)
        left.addWidget(self.provider_list)
        left_actions = QHBoxLayout()
        add_provider = secondary_button("新增")
        add_provider.clicked.connect(self._add_provider)
        delete_provider = QPushButton("删除")
        delete_provider.setProperty("danger", True)
        delete_provider.clicked.connect(self._delete_provider)
        left_actions.addWidget(add_provider)
        left_actions.addWidget(delete_provider)
        left.addLayout(left_actions)
        content.addLayout(left, 1)

        editor = QVBoxLayout()
        form_box = QGroupBox("服务商配置")
        form = QFormLayout(form_box)
        self.provider_id = QLineEdit()
        self.provider_name = QLineEdit()
        self.base_url = QLineEdit()
        self.env_key = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(70)
        form.addRow("Provider ID", self.provider_id)
        form.addRow("显示名称", self.provider_name)
        form.addRow("Base URL", self.base_url)
        form.addRow("API Key 环境变量", self.env_key)
        form.addRow("备注", self.notes)
        editor.addWidget(form_box)

        key_box = QGroupBox("API Key（不会写入配置文件）")
        key_layout = QHBoxLayout(key_box)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("留空则使用当前进程环境变量")
        save_key = secondary_button("保存到 Windows 用户环境变量")
        save_key.clicked.connect(
            lambda: self.save_key_requested.emit(
                self.env_key.text(), self.api_key.text()
            )
        )
        key_layout.addWidget(self.api_key, 1)
        key_layout.addWidget(save_key)
        editor.addWidget(key_box)

        models_box = QGroupBox("模型")
        models_layout = QVBoxLayout(models_box)
        self.models_table = QTableWidget(0, 3)
        self.models_table.setHorizontalHeaderLabels(
            ["显示名称", "Model ID", "推理强度"]
        )
        self.models_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.models_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.models_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.models_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.models_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        models_layout.addWidget(self.models_table)
        model_actions = QHBoxLayout()
        add_model = secondary_button("添加模型")
        add_model.clicked.connect(self._add_model_row)
        remove_model = secondary_button("删除模型")
        remove_model.clicked.connect(self._remove_model_row)
        model_actions.addWidget(add_model)
        model_actions.addWidget(remove_model)
        model_actions.addStretch()
        models_layout.addLayout(model_actions)
        editor.addWidget(models_box, 1)

        actions = QHBoxLayout()
        save = secondary_button("保存服务商")
        save.clicked.connect(self._save_current)
        test = secondary_button("测试所选模型")
        test.clicked.connect(self._request_test)
        apply = QPushButton("预览并应用")
        apply.clicked.connect(self._request_apply)
        actions.addWidget(save)
        actions.addWidget(test)
        actions.addStretch()
        actions.addWidget(apply)
        editor.addLayout(actions)
        content.addLayout(editor, 3)
        root.addLayout(content, 1)
        self.reload()

    def reload(self) -> None:
        try:
            self.providers = self.store.load()
        except Exception as exc:
            QMessageBox.critical(self, "无法读取服务商文件", str(exc))
            self.providers = []
        self.provider_list.clear()
        for provider in self.providers:
            self.provider_list.addItem(provider.name or provider.provider_id)
        if self.providers:
            self.provider_list.setCurrentRow(0)

    def _load_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.providers):
            return
        self._loading = True
        provider = self.providers[row]
        self.provider_id.setText(provider.provider_id)
        self.provider_name.setText(provider.name)
        self.base_url.setText(provider.base_url)
        self.env_key.setText(provider.env_key)
        self.notes.setPlainText(provider.notes)
        self.api_key.clear()
        self.models_table.setRowCount(0)
        for model in provider.models:
            self._add_model_row(model)
        self._loading = False

    def _add_provider(self) -> None:
        base = "custom_provider"
        existing = {item.provider_id for item in self.providers}
        candidate = base
        index = 2
        while candidate in existing:
            candidate = f"{base}_{index}"
            index += 1
        provider = ProviderProfile(candidate, "新服务商", "", "CUSTOM_API_KEY")
        self.providers.append(provider)
        self.provider_list.addItem(provider.name)
        self.provider_list.setCurrentRow(len(self.providers) - 1)

    def _delete_provider(self) -> None:
        row = self.provider_list.currentRow()
        if row < 0:
            return
        provider = self.providers[row]
        answer = QMessageBox.question(
            self,
            "删除服务商",
            f"确定从本程序中删除“{provider.name}”吗？这不会删除 Codex 配置中的旧记录。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self.providers.pop(row)
        try:
            self.store.save(self.providers)
        except Exception as exc:
            self.providers.insert(row, removed)
            QMessageBox.critical(self, "删除失败", str(exc))
            return
        self.provider_list.takeItem(row)
        self.providers_changed.emit()
        if self.providers:
            self.provider_list.setCurrentRow(min(row, len(self.providers) - 1))

    def _add_model_row(self, model: ModelProfile | None = None) -> None:
        model = model or ModelProfile("", "", "medium")
        row = self.models_table.rowCount()
        self.models_table.insertRow(row)
        self.models_table.setItem(row, 0, QTableWidgetItem(model.name))
        self.models_table.setItem(row, 1, QTableWidgetItem(model.model_id))
        combo = QComboBox()
        combo.addItems(ALLOWED_REASONING_EFFORTS)
        combo.setCurrentText(model.reasoning_effort)
        self.models_table.setCellWidget(row, 2, combo)
        if self.models_table.currentRow() < 0:
            self.models_table.selectRow(row)

    def _remove_model_row(self) -> None:
        row = self.models_table.currentRow()
        if row >= 0:
            self.models_table.removeRow(row)

    def _collect_provider(self) -> ProviderProfile:
        models: list[ModelProfile] = []
        for row in range(self.models_table.rowCount()):
            name_item = self.models_table.item(row, 0)
            id_item = self.models_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            model_id = id_item.text().strip() if id_item else ""
            combo = self.models_table.cellWidget(row, 2)
            effort = combo.currentText() if isinstance(combo, QComboBox) else "medium"
            if name or model_id:
                models.append(ModelProfile(name or model_id, model_id, effort))
        return ProviderProfile(
            provider_id=self.provider_id.text().strip(),
            name=self.provider_name.text().strip(),
            base_url=self.base_url.text().strip(),
            env_key=self.env_key.text().strip(),
            models=models,
            notes=self.notes.toPlainText().strip(),
            builtin=(
                0 <= self.provider_list.currentRow() < len(self.providers)
                and self.providers[self.provider_list.currentRow()].builtin
            ),
        )

    def _save_current(self) -> bool:
        row = self.provider_list.currentRow()
        if row < 0:
            return False
        provider = self._collect_provider()
        if not provider.provider_id or not provider.name:
            QMessageBox.warning(self, "字段不完整", "Provider ID 和显示名称不能为空。")
            return False
        for index, existing in enumerate(self.providers):
            if index != row and existing.provider_id == provider.provider_id:
                QMessageBox.warning(
                    self, "Provider ID 重复", "请使用唯一的 Provider ID。"
                )
                return False
        previous = self.providers[row]
        self.providers[row] = provider
        try:
            self.store.save(self.providers)
        except Exception as exc:
            self.providers[row] = previous
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self.provider_list.item(row).setText(provider.name)
        self.providers_changed.emit()
        return True

    def _selected_model(self) -> ModelProfile | None:
        selected_row = self.models_table.currentRow()
        if selected_row < 0 and self.models_table.rowCount() > 0:
            selected_row = 0
        if selected_row < 0:
            return None
        name_item = self.models_table.item(selected_row, 0)
        id_item = self.models_table.item(selected_row, 1)
        combo = self.models_table.cellWidget(selected_row, 2)
        name = name_item.text().strip() if name_item else ""
        model_id = id_item.text().strip() if id_item else ""
        effort = combo.currentText() if isinstance(combo, QComboBox) else "medium"
        return ModelProfile(name or model_id, model_id, effort)

    def _request_test(self) -> None:
        if not self._save_current():
            return
        provider = self.providers[self.provider_list.currentRow()]
        model = self._selected_model()
        if model is None:
            QMessageBox.warning(self, "没有选择模型", "请先添加并选择一个模型。")
            return
        self.test_requested.emit(provider, model, self.api_key.text().strip())

    def _request_apply(self) -> None:
        if not self._save_current():
            return
        provider = self.providers[self.provider_list.currentRow()]
        model = self._selected_model()
        if model is None:
            QMessageBox.warning(self, "没有选择模型", "请先添加并选择一个模型。")
            return
        self.apply_requested.emit(provider, model)


class ConnectionTestPage(QWidget):
    test_requested = Signal(object, object, str)

    def __init__(self) -> None:
        super().__init__()
        self.providers: list[ProviderProfile] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        title, subtitle = page_header(
            "连接测试",
            "发送一个最小 `/responses` 请求，不记录完整 API Key 或响应正文。",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        selector = QFrame()
        selector.setObjectName("Card")
        selector_layout = QGridLayout(selector)
        selector_layout.setContentsMargins(16, 16, 16, 16)
        self.provider_combo = QComboBox()
        self.model_combo = QComboBox()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("可选；留空使用环境变量")
        self.provider_combo.currentIndexChanged.connect(self._refresh_models)
        selector_layout.addWidget(QLabel("服务商"), 0, 0)
        selector_layout.addWidget(self.provider_combo, 0, 1)
        selector_layout.addWidget(QLabel("模型"), 1, 0)
        selector_layout.addWidget(self.model_combo, 1, 1)
        selector_layout.addWidget(QLabel("临时 API Key"), 2, 0)
        selector_layout.addWidget(self.key_input, 2, 1)
        self.test_button = QPushButton("运行基础兼容性测试")
        self.test_button.clicked.connect(self._request_test)
        selector_layout.addWidget(
            self.test_button, 3, 1, alignment=Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(selector)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("测试结果将在这里显示。")
        layout.addWidget(self.result, 1)

    def set_providers(self, providers: list[ProviderProfile]) -> None:
        current_id = self.provider_combo.currentData()
        self.providers = providers
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for provider in providers:
            self.provider_combo.addItem(provider.name, provider.provider_id)
        self.provider_combo.blockSignals(False)
        if current_id:
            index = self.provider_combo.findData(current_id)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
        self._refresh_models()

    def select(self, provider_id: str, model_id: str) -> None:
        index = self.provider_combo.findData(provider_id)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)
        model_index = self.model_combo.findData(model_id)
        if model_index >= 0:
            self.model_combo.setCurrentIndex(model_index)

    def _refresh_models(self) -> None:
        self.model_combo.clear()
        index = self.provider_combo.currentIndex()
        if 0 <= index < len(self.providers):
            for model in self.providers[index].models:
                self.model_combo.addItem(model.name or model.model_id, model.model_id)

    def _request_test(self) -> None:
        provider_index = self.provider_combo.currentIndex()
        model_index = self.model_combo.currentIndex()
        if provider_index < 0 or model_index < 0:
            QMessageBox.warning(
                self, "没有测试目标", "请先在服务商页面添加并保存模型。"
            )
            return
        provider = self.providers[provider_index]
        model = provider.models[model_index]
        self.test_requested.emit(provider, model, self.key_input.text().strip())

    def set_running(self, running: bool) -> None:
        self.test_button.setEnabled(not running)
        if running:
            self.result.setPlainText("正在连接服务商并测试 Responses API…")

    def show_report(self, report: ConnectionReport) -> None:
        lines = [
            f"服务商：{report.provider_id}",
            f"模型：{report.model_id}",
            f"结论：{'通过' if report.ok else '未通过'}",
            "",
        ]
        for check in report.checks:
            mark = "✓" if check.ok else "✗"
            elapsed = (
                f" ({check.elapsed_ms} ms)" if check.elapsed_ms is not None else ""
            )
            lines.append(f"{mark} {check.name}{elapsed}")
            lines.append(f"  {check.message}")
        self.result.setPlainText("\n".join(lines))
        self.test_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.result.setPlainText(f"测试程序发生错误：\n{message}")
        self.test_button.setEnabled(True)


class HistoryPage(QWidget):
    restore_requested = Signal(Path)

    def __init__(self, backup_manager: BackupManager):
        super().__init__()
        self.backup_manager = backup_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        title, subtitle = page_header(
            "配置历史",
            "每次应用和恢复前都会保留一份原配置。恢复操作也会先备份当前文件。",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["时间", "文件", "大小"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        refresh = secondary_button("刷新")
        refresh.clicked.connect(self.refresh)
        restore = QPushButton("恢复所选备份")
        restore.clicked.connect(self._restore_selected)
        actions.addWidget(refresh)
        actions.addStretch()
        actions.addWidget(restore)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        backups = self.backup_manager.list()
        self.table.setRowCount(0)
        for backup in backups:
            row = self.table.rowCount()
            self.table.insertRow(row)
            time_item = QTableWidgetItem(
                backup.created_at.strftime("%Y-%m-%d %H:%M:%S")
            )
            time_item.setData(Qt.ItemDataRole.UserRole, str(backup.path))
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, QTableWidgetItem(backup.path.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{backup.size / 1024:.1f} KB"))
        if backups:
            self.table.selectRow(0)

    def _restore_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "没有备份",
                "请先选择一条备份记录。",
                QMessageBox.StandardButton.Ok,
            )
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.restore_requested.emit(path)


class DiagnosticsPage(QWidget):
    run_requested = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        title, subtitle = page_header(
            "诊断中心",
            "检查 Codex CLI、用户配置、Profile、项目覆盖和当前进程环境变量。",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)
        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("项目目录"))
        self.project_dir = QLineEdit(str(Path.cwd()))
        run = QPushButton("运行诊断")
        run.clicked.connect(
            lambda: self.run_requested.emit(Path(self.project_dir.text()))
        )
        project_row.addWidget(self.project_dir, 1)
        project_row.addWidget(run)
        layout.addLayout(project_row)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

    def show_items(self, items: Sequence[DiagnosticItem]) -> None:
        marks = {"ok": "✓", "info": "•", "warning": "!", "error": "✗"}
        lines: list[str] = []
        for item in items:
            lines.append(f"{marks.get(item.level, '•')} {item.name}")
            lines.append(f"  {item.message}")
            lines.append("")
        self.output.setPlainText("\n".join(lines).rstrip())
