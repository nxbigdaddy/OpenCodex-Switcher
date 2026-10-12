from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..backup_manager import BackupManager
from ..codex_process import CodexProcessManager
from ..config_manager import ConfigManager
from ..connection_tester import ConnectionTester
from ..credential_manager import CredentialManager, EnvironmentScope
from ..diagnostics import DiagnosticsService
from ..models import ConnectionReport, ModelProfile, ProviderProfile
from ..paths import AppPaths
from ..provider_store import ProviderStore
from ..settings_store import SettingsStore
from .dialogs import ConfigEditorDialog, DiffDialog
from .pages import (
    ConnectionTestPage,
    DashboardPage,
    DiagnosticsPage,
    EnvironmentVariablesPage,
    HistoryPage,
    ProvidersPage,
)
from .title_bar import CustomTitleBar


class ConnectionTestThread(QThread):
    report_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        tester: ConnectionTester,
        provider: ProviderProfile,
        model: ModelProfile,
        api_key: str,
    ):
        super().__init__()
        self.tester = tester
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def run(self) -> None:
        try:
            report = self.tester.test(self.provider, self.model, api_key=self.api_key)
            self.report_ready.emit(report)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    def __init__(
        self,
        paths: AppPaths,
        provider_store: ProviderStore,
        backup_manager: BackupManager,
        config_manager: ConfigManager,
        credential_manager: CredentialManager,
        connection_tester: ConnectionTester,
        diagnostics: DiagnosticsService,
        settings_store: SettingsStore,
        codex_process_manager: CodexProcessManager,
    ):
        super().__init__()
        self.paths = paths
        self.provider_store = provider_store
        self.backup_manager = backup_manager
        self.config_manager = config_manager
        self.credential_manager = credential_manager
        self.connection_tester = connection_tester
        self.diagnostics = diagnostics
        self.settings_store = settings_store
        self.codex_process_manager = codex_process_manager
        self._test_thread: ConnectionTestThread | None = None
        self._codex_path = self._initial_codex_path()

        self.setWindowTitle("OpenCodex Switcher")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.resize(1180, 760)
        self.setMinimumSize(980, 650)
        root = QWidget()
        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(self, "OpenCodex Switcher")
        outer_layout.addWidget(self.title_bar)

        content = QWidget()
        root_layout = QHBoxLayout(content)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(215)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 22, 10, 14)
        brand = QLabel("OpenCodex")
        brand.setObjectName("AppTitle")
        subtitle = QLabel("Model Switcher")
        subtitle.setStyleSheet("color: #64748b;")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(20)
        self.navigation = QListWidget()
        self.navigation.setObjectName("Navigation")
        self.navigation.addItems(
            [
                "当前配置",
                "服务商与模型",
                "Windows 环境变量",
                "连接测试",
                "配置历史",
                "诊断中心",
            ]
        )
        sidebar_layout.addWidget(self.navigation, 1)
        version = QLabel("v0.1.0 · Keys are never stored in TOML")
        version.setWordWrap(True)
        version.setStyleSheet("color: #64748b; font-size: 11px; padding: 8px;")
        sidebar_layout.addWidget(version)
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.providers_page = ProvidersPage(provider_store)
        self.environment_page = EnvironmentVariablesPage()
        self.test_page = ConnectionTestPage()
        self.history_page = HistoryPage(backup_manager)
        self.diagnostics_page = DiagnosticsPage()
        for page in (
            self.dashboard_page,
            self.providers_page,
            self.environment_page,
            self.test_page,
            self.history_page,
            self.diagnostics_page,
        ):
            self.stack.addWidget(page)
        root_layout.addWidget(self.stack, 1)
        outer_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self.statusBar().addPermanentWidget(QSizeGrip(self))
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)

        self.dashboard_page.refresh_requested.connect(self.refresh_all)
        self.dashboard_page.test_requested.connect(self._test_current)
        self.dashboard_page.edit_config_requested.connect(self._edit_config)
        self.dashboard_page.restore_requested.connect(self._restore_latest)
        self.dashboard_page.browse_codex_requested.connect(self._browse_codex_path)
        self.dashboard_page.detect_codex_requested.connect(self._detect_codex_path)
        self.dashboard_page.save_codex_path_requested.connect(self._save_codex_path)
        self.dashboard_page.start_codex_requested.connect(self._start_codex)
        self.dashboard_page.close_codex_requested.connect(self._close_codex)
        self.providers_page.providers_changed.connect(self.refresh_all)
        self.providers_page.test_requested.connect(self._start_test)
        self.providers_page.apply_requested.connect(self._apply_selection)
        self.providers_page.save_key_requested.connect(self._save_api_key)
        self.environment_page.load_requested.connect(self._load_environment)
        self.environment_page.save_requested.connect(self._save_environment)
        self.environment_page.delete_requested.connect(self._delete_environment)
        self.test_page.test_requested.connect(self._start_test)
        self.history_page.restore_requested.connect(self._restore_backup)
        self.diagnostics_page.run_requested.connect(self._run_diagnostics)
        self.codex_status_timer = QTimer(self)
        self.codex_status_timer.setInterval(3000)
        self.codex_status_timer.timeout.connect(self._refresh_codex_status)
        self.codex_status_timer.start()
        self.refresh_all()

    def refresh_all(self) -> None:
        try:
            snapshot = self.config_manager.read()
            key_status = self.credential_manager.has_key(snapshot.env_key)
            self.dashboard_page.set_snapshot(snapshot, key_status)
        except Exception as exc:
            QMessageBox.critical(self, "Codex 配置读取失败", str(exc))
        try:
            providers = self.provider_store.load()
            self.test_page.set_providers(providers)
        except Exception as exc:
            self.statusBar().showMessage(f"服务商文件读取失败：{exc}", 8000)
        self.history_page.refresh()
        self._refresh_codex_status()

    def _initial_codex_path(self) -> Path | None:
        try:
            saved = self.settings_store.load().codex_executable.strip()
        except Exception:
            saved = ""
        if saved:
            return Path(saved)
        return self.codex_process_manager.detect_executable()

    def _refresh_codex_status(self) -> None:
        status = self.codex_process_manager.status(self._codex_path)
        executable = str(self._codex_path) if self._codex_path else ""
        self.dashboard_page.set_codex_control(
            executable, status.running, status.running_pids
        )

    def _browse_codex_path(self) -> None:
        initial = (
            str(self._codex_path.parent)
            if self._codex_path and self._codex_path.parent.exists()
            else str(Path.home())
        )
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Codex 程序",
            initial,
            "Codex 程序 (*.exe);;所有文件 (*)",
        )
        if not selected:
            return
        self._codex_path = Path(selected)
        self._refresh_codex_status()

    def _detect_codex_path(self) -> None:
        detected = self.codex_process_manager.detect_executable()
        if detected is None:
            QMessageBox.information(
                self,
                "没有检测到 Codex",
                "没有从运行进程、PATH 或常见安装位置检测到 Codex，请手动浏览选择。",
                QMessageBox.StandardButton.Ok,
            )
            return
        self._codex_path = detected
        self._refresh_codex_status()
        self.statusBar().showMessage(
            f"已检测到 {detected}；确认后请点击“保存路径”。", 8000
        )

    def _save_codex_path(self, path_text: str) -> None:
        try:
            executable = self.codex_process_manager.validate_executable(Path(path_text))
            self.settings_store.save_codex_executable(executable)
        except Exception as exc:
            QMessageBox.warning(self, "Codex 路径无效", str(exc))
            return
        self._codex_path = executable
        self._refresh_codex_status()
        self.statusBar().showMessage("Codex 程序路径已保存。", 5000)

    def _start_codex(self, path_text: str) -> None:
        try:
            executable = self.codex_process_manager.validate_executable(Path(path_text))
            if self.codex_process_manager.status(executable).running:
                QMessageBox.information(
                    self,
                    "Codex 已在运行",
                    "配置路径对应的 Codex 进程已经在运行。",
                    QMessageBox.StandardButton.Ok,
                )
                return
            self.settings_store.save_codex_executable(executable)
            self.codex_process_manager.start(executable)
        except Exception as exc:
            QMessageBox.critical(self, "启动 Codex 失败", str(exc))
            return
        self._codex_path = executable
        self.statusBar().showMessage("已发送 Codex 启动请求。", 5000)
        QTimer.singleShot(1200, self._refresh_codex_status)

    def _close_codex(self, path_text: str) -> None:
        try:
            executable = self.codex_process_manager.validate_executable(Path(path_text))
            status = self.codex_process_manager.status(executable)
        except Exception as exc:
            QMessageBox.warning(self, "Codex 路径无效", str(exc))
            return
        if not status.running:
            self._refresh_codex_status()
            QMessageBox.information(
                self,
                "Codex 未运行",
                "没有找到与当前配置路径完全匹配的运行进程。",
                QMessageBox.StandardButton.Ok,
            )
            return
        answer = QMessageBox.question(
            self,
            "关闭 Codex",
            "关闭 Codex 可能中断正在执行的任务。确定向匹配进程发送正常关闭请求吗？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.codex_process_manager.request_close(executable)
        except Exception as exc:
            QMessageBox.critical(self, "关闭 Codex 失败", str(exc))
            return
        self._codex_path = executable
        self.statusBar().showMessage(
            f"已向 {len(result.matched_pids)} 个匹配进程发送关闭请求。", 6000
        )
        QTimer.singleShot(1800, lambda: self._check_codex_closed(executable))

    def _check_codex_closed(self, executable: Path) -> None:
        status = self.codex_process_manager.status(executable)
        self._refresh_codex_status()
        if not status.running:
            self.statusBar().showMessage("Codex 已关闭。", 5000)
            return
        answer = QMessageBox.question(
            self,
            "Codex 仍在运行",
            "正常关闭请求后进程仍然存在。是否强制结束与配置路径完全匹配的进程？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            terminated = self.codex_process_manager.force_close(executable)
        except Exception as exc:
            QMessageBox.critical(self, "强制关闭失败", str(exc))
            return
        self.statusBar().showMessage(f"已强制结束 {len(terminated)} 个匹配进程。", 6000)
        QTimer.singleShot(500, self._refresh_codex_status)

    def _save_api_key(self, env_name: str, api_key: str) -> None:
        if not env_name.strip() or not api_key.strip():
            QMessageBox.warning(self, "字段不完整", "请填写环境变量名和 API Key。")
            return
        answer = QMessageBox.question(
            self,
            "保存 API Key",
            f"将把密钥保存到 Windows 当前用户环境变量 {env_name.strip()}。\n\n"
            "环境变量会存储在当前用户注册表中，新启动的 Codex 才会读取新值。是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.credential_manager.save_user_environment(env_name, api_key)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.providers_page.api_key.clear()
        self.refresh_all()
        QMessageBox.information(
            self,
            "保存成功",
            f"{env_name.strip()} 已设置；请重启正在运行的 Codex。",
            QMessageBox.StandardButton.Ok,
        )

    def _load_environment(self, scope_text: str, env_name: str) -> None:
        try:
            scope = self._environment_scope(scope_text)
            variable = self.credential_manager.read_environment(scope, env_name)
        except Exception as exc:
            QMessageBox.warning(self, "读取环境变量失败", str(exc))
            return
        self.environment_page.set_loaded(variable.value, variable.exists)

    def _save_environment(self, scope_text: str, env_name: str, value: str) -> None:
        try:
            scope = self._environment_scope(scope_text)
        except ValueError as exc:
            QMessageBox.warning(self, "环境变量设置无效", str(exc))
            return
        scope_label = "当前用户" if scope == "user" else "整个系统"
        answer = QMessageBox.question(
            self,
            "保存 Windows 环境变量",
            f"将保存 {scope_label}范围的环境变量 {env_name.strip()}。\n\n"
            "系统范围写入需要管理员权限。保存后必须重启 Codex 才能生效。是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.credential_manager.save_environment(scope, env_name, value)
        except Exception as exc:
            QMessageBox.critical(self, "保存环境变量失败", str(exc))
            return
        self.environment_page.set_saved()
        if self._is_sensitive_environment(env_name):
            self.environment_page.value_input.clear()
        self.refresh_all()
        QMessageBox.information(
            self,
            "保存成功",
            f"{env_name.strip()} 已保存到 {scope_label}范围。\n"
            "当前程序启动的新进程会使用最新值；已运行的 Codex 请关闭后重新启动。",
            QMessageBox.StandardButton.Ok,
        )

    def _delete_environment(self, scope_text: str, env_name: str) -> None:
        try:
            scope = self._environment_scope(scope_text)
        except ValueError as exc:
            QMessageBox.warning(self, "环境变量设置无效", str(exc))
            return
        scope_label = "当前用户" if scope == "user" else "系统"
        answer = QMessageBox.question(
            self,
            "删除 Windows 环境变量",
            f"确定删除{scope_label}范围的环境变量 {env_name.strip()} 吗？\n\n"
            "该操作不会删除另一个作用范围中的同名变量。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.credential_manager.delete_environment(scope, env_name)
        except Exception as exc:
            QMessageBox.critical(self, "删除环境变量失败", str(exc))
            return
        self.environment_page.set_deleted(deleted)
        self.refresh_all()
        if deleted:
            self.statusBar().showMessage(
                f"已删除 {scope_label}范围环境变量 {env_name.strip()}；请重启 Codex。",
                8000,
            )

    @staticmethod
    def _environment_scope(scope_text: str) -> EnvironmentScope:
        if scope_text == "user":
            return "user"
        if scope_text == "system":
            return "system"
        raise ValueError("环境变量作用域无效。")

    @staticmethod
    def _is_sensitive_environment(env_name: str) -> bool:
        upper_name = env_name.upper()
        return any(
            marker in upper_name for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        )

    def _apply_selection(self, provider: ProviderProfile, model: ModelProfile) -> None:
        try:
            snapshot = self.config_manager.read()
            _, diff = self.config_manager.render_selection(provider, model)
        except Exception as exc:
            QMessageBox.warning(self, "配置校验失败", str(exc))
            return
        dialog = DiffDialog(diff, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            written = self.config_manager.apply_selection(
                provider, model, expected_digest=snapshot.digest
            )
        except Exception as exc:
            QMessageBox.critical(self, "应用配置失败", str(exc))
            return
        self.refresh_all()
        self.navigation.setCurrentRow(0)
        QMessageBox.information(
            self,
            "配置已应用",
            f"当前默认配置已切换为：\n{written.model_provider} / {written.model}\n\n"
            "正在运行的 Codex 不会自动刷新，请新建进程或重启 Codex。",
            QMessageBox.StandardButton.Ok,
        )

    def _start_test(
        self, provider: ProviderProfile, model: ModelProfile, api_key: str
    ) -> None:
        if self._test_thread and self._test_thread.isRunning():
            QMessageBox.information(
                self,
                "测试进行中",
                "请等待当前测试完成。",
                QMessageBox.StandardButton.Ok,
            )
            return
        key = api_key or self.credential_manager.get_key(provider.env_key)
        try:
            providers = self.provider_store.load()
        except Exception as exc:
            QMessageBox.critical(self, "服务商文件读取失败", str(exc))
            return
        display_provider = next(
            (item for item in providers if item.provider_id == provider.provider_id),
            None,
        )
        if display_provider is None:
            providers.append(provider)
        elif not any(
            item.model_id == model.model_id for item in display_provider.models
        ):
            display_provider.models.append(model)
        self.test_page.set_providers(providers)
        self.test_page.select(provider.provider_id, model.model_id)
        self.navigation.setCurrentRow(2)
        self.test_page.set_running(True)
        self._test_thread = ConnectionTestThread(
            self.connection_tester, provider, model, key
        )
        self._test_thread.report_ready.connect(self._test_complete)
        self._test_thread.failed.connect(self._test_failed)
        self._test_thread.finished.connect(self._test_thread.deleteLater)
        self._test_thread.start()

    def _test_complete(self, report: ConnectionReport) -> None:
        self.test_page.show_report(report)
        self.statusBar().showMessage(
            "连接测试通过。" if report.ok else "连接测试未通过。", 6000
        )
        self._test_thread = None

    def _test_failed(self, message: str) -> None:
        self.test_page.show_error(message)
        self._test_thread = None

    def _test_current(self) -> None:
        try:
            snapshot = self.config_manager.read()
            providers = self.provider_store.load()
        except Exception as exc:
            QMessageBox.critical(self, "无法读取配置", str(exc))
            return
        provider = next(
            (item for item in providers if item.provider_id == snapshot.model_provider),
            None,
        )
        if provider is None:
            provider = ProviderProfile(
                snapshot.model_provider,
                snapshot.provider_name or snapshot.model_provider,
                snapshot.base_url,
                snapshot.env_key,
                builtin=snapshot.model_provider == "openai",
            )
        model = next(
            (item for item in provider.models if item.model_id == snapshot.model),
            ModelProfile(snapshot.model, snapshot.model, snapshot.reasoning_effort),
        )
        self._start_test(provider, model, "")

    def _edit_config(self) -> None:
        try:
            dialog = ConfigEditorDialog(self.config_manager, self)
        except Exception as exc:
            QMessageBox.critical(self, "配置编辑器打开失败", str(exc))
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_all()
            QMessageBox.information(
                self,
                "配置已提交",
                "Codex 配置已备份并更新。请重启正在运行的 Codex。",
                QMessageBox.StandardButton.Ok,
            )

    def _restore_latest(self) -> None:
        backups = self.backup_manager.list()
        if not backups:
            QMessageBox.information(
                self,
                "没有备份",
                "当前没有可以恢复的配置备份。",
                QMessageBox.StandardButton.Ok,
            )
            return
        self._restore_backup(backups[0].path)

    def _restore_backup(self, path: Path) -> None:
        answer = QMessageBox.question(
            self,
            "恢复配置",
            f"即将恢复：\n{path.name}\n\n当前配置会先被再次备份，是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.backup_manager.restore(path, self.paths.config_file)
        except Exception as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))
            return
        self.refresh_all()
        self.navigation.setCurrentRow(0)
        QMessageBox.information(
            self,
            "恢复成功",
            "配置已恢复；请重启正在运行的 Codex。",
            QMessageBox.StandardButton.Ok,
        )

    def _run_diagnostics(self, project_dir: Path) -> None:
        try:
            items = self.diagnostics.run(project_dir)
        except Exception as exc:
            QMessageBox.critical(self, "诊断失败", str(exc))
            return
        self.diagnostics_page.show_items(items)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "title_bar"):
            self.title_bar.sync_window_state()
