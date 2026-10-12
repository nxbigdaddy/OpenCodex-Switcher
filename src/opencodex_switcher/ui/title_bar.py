from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class CustomTitleBar(QFrame):
    def __init__(
        self,
        window: QWidget,
        title: str,
        *,
        allow_maximize: bool = True,
    ) -> None:
        super().__init__(window)
        self.target_window = window
        self.allow_maximize = allow_maximize
        self.setObjectName("TitleBar")
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(0)
        mark = QLabel("OC")
        mark.setObjectName("TitleBarMark")
        mark.setFixedSize(25, 25)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TitleBarTitle")
        layout.addWidget(mark)
        layout.addSpacing(10)
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.minimize_button = self._window_button("—", "最小化")
        self.minimize_button.clicked.connect(self.target_window.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = self._window_button("□", "最大化")
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.maximize_button.setVisible(allow_maximize)
        layout.addWidget(self.maximize_button)

        self.close_button = self._window_button("×", "关闭", close=True)
        self.close_button.clicked.connect(self.target_window.close)
        layout.addWidget(self.close_button)

    @staticmethod
    def _window_button(text: str, tooltip: str, *, close: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("CloseWindowButton" if close else "WindowButton")
        button.setToolTip(tooltip)
        button.setFixedSize(46, 42)
        return button

    def toggle_maximized(self) -> None:
        if not self.allow_maximize:
            return
        if self.target_window.isMaximized():
            self.target_window.showNormal()
        else:
            self.target_window.showMaximized()
        self.sync_window_state()

    def sync_window_state(self) -> None:
        if self.allow_maximize:
            maximized = self.target_window.isMaximized()
            self.maximize_button.setText("❐" if maximized else "□")
            self.maximize_button.setToolTip("还原" if maximized else "最大化")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.target_window.windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.allow_maximize:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
