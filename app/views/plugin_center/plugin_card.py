"""🧩 插件卡片组件 — 图标 + 名称 + 版本 + 启用开关"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent

try:
    from qfluentwidgets import ToggleSwitch
    _HAS_TOGGLE = True
except ImportError:
    _HAS_TOGGLE = False
    from PySide6.QtWidgets import QCheckBox


class PluginCard(QFrame):
    """插件网格卡片 — 圆角 8px，间距 15px，悬停/按下反馈"""

    clicked = Signal(str)          # plugin_id
    toggled = Signal(str, bool)    # plugin_id, enabled

    def __init__(self, plugin_id: str, icon: str, name: str, version: str,
                 enabled: bool = True, parent=None):
        super().__init__(parent)
        self._plugin_id = plugin_id
        self._enabled = enabled

        self.setObjectName("pluginGridCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 170)
        self.setMaximumWidth(280)

        # ── 基础样式 — 交由 plugin_center.py 的全局样式表覆盖 ──
        self.setStyleSheet("""
            QFrame#pluginGridCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QFrame#pluginGridCard:hover {
                border-color: #8b5cf6;
                background: #faf8ff;
            }
            QFrame#pluginGridCard:pressed {
                border-color: #7c3aed;
                background: #f5f0ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 18, 16, 14)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 40px; border: none;")
        layout.addWidget(icon_label)

        # 名称
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        name_label.setWordWrap(True)
        name_label.setStyleSheet("border: none; color: #1e293b;")
        layout.addWidget(name_label)

        # 版本
        ver_label = QLabel(f"v{version}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
        layout.addWidget(ver_label)

        # 底部行：开关
        bottom = QHBoxLayout()
        bottom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _HAS_TOGGLE:
            self._toggle = ToggleSwitch()
            self._toggle.setChecked(enabled)
        else:
            self._toggle = QCheckBox("启用")
            self._toggle.setChecked(enabled)
            self._toggle.setStyleSheet("font-size: 12px;")
        self._toggle.toggled.connect(self._on_toggled)
        bottom.addWidget(self._toggle)
        layout.addLayout(bottom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 如果点击的不是开关区域，触发卡片点击
            if self._enabled:
                self.clicked.emit(self._plugin_id)
        super().mousePressEvent(event)

    def _on_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self.toggled.emit(self._plugin_id, checked)
        self.setEnabled(True)  # 卡片本身始终可交互

    def set_enabled_state(self, enabled: bool) -> None:
        self._enabled = enabled
        if _HAS_TOGGLE:
            self._toggle.setChecked(enabled)
            self._toggle.blockSignals(True)
            self._toggle.setChecked(enabled)
            self._toggle.blockSignals(False)
