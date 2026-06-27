"""🔌 插件启动台 — 网格卡片布局"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
    QMenu, QMessageBox, QSizePolicy, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QAction

from app.plugins.manager import PluginManager


class PluginCard(QFrame):
    """插件卡片 — 图标 + 名称 + 描述"""
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, desc: str, plugin_id: str, parent=None):
        super().__init__(parent)
        self.setObjectName("pluginCard")
        self._plugin_id = plugin_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            QFrame#pluginCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
            }
            QFrame#pluginCard:hover {
                border-color: #8b5cf6;
                background: #faf8ff;
            }
            QFrame#pluginCard:pressed {
                border-color: #7c3aed;
                background: #f5f0ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 24, 20, 24)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #94a3b8; font-size: 13px; border: none;")
        layout.addWidget(desc_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self._plugin_id)
        super().mousePressEvent(event)


class PluginsLauncherView(QWidget):
    """插件启动台 — 网格卡片 + 标题栏"""

    back_requested = Signal()
    card_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pluginsLauncher")
        self._mgmt_page = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 20, 48, 32)
        layout.setSpacing(20)

        # 标题行
        header_row = QHBoxLayout()
        title = QLabel("🔌  插件启动台")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        header_row.addWidget(title)
        header_row.addStretch()

        mgmt_btn = QPushButton("管理插件")
        mgmt_btn.setMinimumHeight(48)
        mgmt_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold;
                background: rgba(139,92,246,0.10); color: #8b5cf6;
                border: 1px solid rgba(139,92,246,0.25); border-radius: 10px;
                padding: 8px 20px; }
            QPushButton:hover { background: rgba(139,92,246,0.18); }
        """)
        mgmt_btn.clicked.connect(self._show_plugin_management)
        header_row.addWidget(mgmt_btn)
        layout.addLayout(header_row)

        subtitle = QLabel("发现已安装的功能插件，点击卡片加载")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 15px; border: none;")
        layout.addWidget(subtitle)

        # 网格
        self._grid = QGridLayout()
        self._grid.setSpacing(20)
        layout.addLayout(self._grid)
        layout.addStretch(1)

        self.reload_cards()

    def reload_cards(self) -> None:
        """重新扫描插件并刷新卡片网格。"""
        # 清空旧卡片
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pm = PluginManager()
        pm.scan()
        plugins = pm.plugin_list

        cols = 3
        for idx, plugin in enumerate(plugins):
            card = PluginCard(
                plugin.plugin_icon,
                plugin.plugin_name,
                plugin.plugin_description,
                plugin.plugin_id,
            )
            card.clicked.connect(self.card_clicked.emit)
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(
                lambda pos, p=plugin: self._on_card_context_menu(pos, p)
            )
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)

    def _on_card_context_menu(self, pos, plugin) -> None:
        menu = QMenu(self)
        toggle_text = "禁用" if plugin.enabled else "启用"
        toggle_action = QAction(f"⏸ {toggle_text}", self)
        toggle_action.triggered.connect(lambda: self._toggle_plugin(plugin))
        menu.addAction(toggle_action)

        menu.addSeparator()
        reload_action = QAction("🔄 重新加载", self)
        reload_action.triggered.connect(lambda: self._reload_plugin(plugin))
        menu.addAction(reload_action)

        menu.exec(self.sender().mapToGlobal(pos))

    def _toggle_plugin(self, plugin) -> None:
        plugin.enabled = not plugin.enabled
        self.reload_cards()

    def _reload_plugin(self, plugin) -> None:
        pm = PluginManager()
        pm.reload(plugin.plugin_id)
        self.reload_cards()

    def _show_plugin_management(self) -> None:
        from app.views.plugins.management_view import PluginManagementView
        dlg = PluginManagementView(self)
        dlg.exec()
        self.reload_cards()
