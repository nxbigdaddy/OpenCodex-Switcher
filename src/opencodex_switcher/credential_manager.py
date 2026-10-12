from __future__ import annotations

import ctypes
import os
import re
import sys
from dataclasses import dataclass
from typing import Literal, Protocol


ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
EnvironmentScope = Literal["user", "system"]


@dataclass(frozen=True)
class EnvironmentVariable:
    name: str
    value: str
    scope: EnvironmentScope
    exists: bool


class RegistryBackend(Protocol):
    def get(self, scope: EnvironmentScope, name: str) -> str | None:
        ...

    def set(self, scope: EnvironmentScope, name: str, value: str) -> None:
        ...

    def delete(self, scope: EnvironmentScope, name: str) -> bool:
        ...


class WindowsRegistryBackend:
    USER_PATH = "Environment"
    SYSTEM_PATH = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

    @classmethod
    def _location(cls, scope: EnvironmentScope) -> tuple[int, str]:
        import winreg

        if scope == "user":
            return winreg.HKEY_CURRENT_USER, cls.USER_PATH
        return winreg.HKEY_LOCAL_MACHINE, cls.SYSTEM_PATH

    def get(self, scope: EnvironmentScope, name: str) -> str | None:
        import winreg

        root, path = self._location(scope)
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value)

    def set(self, scope: EnvironmentScope, name: str, value: str) -> None:
        import winreg

        root, path = self._location(scope)
        try:
            with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
                value_type = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ
                winreg.SetValueEx(key, name, 0, value_type, value)
        except PermissionError as exc:
            raise PermissionError(
                "保存系统范围环境变量需要管理员权限，请以管理员身份运行 run.bat。"
            ) from exc

    def delete(self, scope: EnvironmentScope, name: str) -> bool:
        import winreg

        root, path = self._location(scope)
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            return False
        except PermissionError as exc:
            raise PermissionError(
                "删除系统范围环境变量需要管理员权限，请以管理员身份运行 run.bat。"
            ) from exc
        return True


class CredentialManager:
    def __init__(
        self,
        registry_backend: RegistryBackend | None = None,
        *,
        broadcast_changes: bool = True,
    ):
        self._registry_backend = registry_backend
        self._broadcast_changes = broadcast_changes

    def has_key(self, env_name: str) -> bool:
        return bool(env_name and os.environ.get(env_name))

    def get_key(self, env_name: str) -> str:
        return os.environ.get(env_name, "") if env_name else ""

    def read_environment(
        self, scope: EnvironmentScope, env_name: str
    ) -> EnvironmentVariable:
        name = self._validate(scope, env_name)
        value = self._backend().get(scope, name)
        return EnvironmentVariable(name, value or "", scope, value is not None)

    def save_environment(
        self, scope: EnvironmentScope, env_name: str, value: str
    ) -> EnvironmentVariable:
        name = self._validate(scope, env_name)
        if not value:
            raise ValueError("环境变量值不能为空；如需清空请使用删除按钮。")
        if "\x00" in value:
            raise ValueError("环境变量值不能包含空字符。")
        backend = self._backend()
        backend.set(scope, name, value)
        self._refresh_current_process(name, backend)
        self._notify_environment_change()
        return EnvironmentVariable(name, value, scope, True)

    def delete_environment(self, scope: EnvironmentScope, env_name: str) -> bool:
        name = self._validate(scope, env_name)
        backend = self._backend()
        deleted = backend.delete(scope, name)
        if deleted:
            self._refresh_current_process(name, backend)
            self._notify_environment_change()
        return deleted

    def save_user_environment(self, env_name: str, api_key: str) -> None:
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("API Key 不能为空。")
        self.save_environment("user", env_name, api_key)

    def _backend(self) -> RegistryBackend:
        if self._registry_backend is not None:
            return self._registry_backend
        if sys.platform != "win32":
            raise RuntimeError("当前版本只支持在 Windows 管理环境变量。")
        self._registry_backend = WindowsRegistryBackend()
        return self._registry_backend

    @staticmethod
    def _validate(scope: EnvironmentScope, env_name: str) -> str:
        if scope not in ("user", "system"):
            raise ValueError("环境变量作用域无效。")
        name = env_name.strip()
        if not ENV_NAME_PATTERN.fullmatch(name):
            raise ValueError("环境变量名格式无效。")
        return name

    @staticmethod
    def _refresh_current_process(name: str, backend: RegistryBackend) -> None:
        user_value = backend.get("user", name)
        system_value = backend.get("system", name)
        effective_value = user_value if user_value is not None else system_value
        if effective_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = effective_value

    def _notify_environment_change(self) -> None:
        if self._broadcast_changes:
            self._broadcast_environment_change()

    @staticmethod
    def _broadcast_environment_change() -> None:
        if sys.platform != "win32":
            return
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            None,
        )
