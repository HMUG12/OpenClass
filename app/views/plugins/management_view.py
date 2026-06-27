"""插件管理弹窗"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.plugins.manager import PluginManager


class PluginManagementView(QDialog):
    """插件管理弹窗 — 列表展示 + 启用/禁用/重新加载"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("插件管理")
        self.setMinimumSize(600, 500)
        self.resize(700, 550)
        self.setStyleSheet("QDialog { background: #1e1e2e; border-radius: 12px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("🔌 已安装插件")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0; border: none;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)

        pm = PluginManager()
        pm.scan()
        all_plugins = list(pm._plugins.values())

        for plugin in all_plugins:
            card = self._create_card(plugin)
            cl.addWidget(card)

        cl.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(48)
        close_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: #8b5cf6; color: #fff;
                border: none; border-radius: 10px; }
            QPushButton:hover { background: #7c3aed; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _create_card(self, plugin) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; padding: 12px; }
        """)
        hl = QHBoxLayout(card)
        hl.setSpacing(12)

        icon = QLabel(plugin.plugin_icon)
        icon.setStyleSheet("font-size: 32px; border: none;")
        hl.addWidget(icon)

        info = QVBoxLayout()
        name = QLabel(f"{plugin.plugin_name}  v{plugin.plugin_version}")
        name.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        name.setStyleSheet("color: #e0e0e0; border: none;")
        info.addWidget(name)

        author = QLabel(f"作者: {plugin.plugin_author}  |  分类: {plugin.plugin_category}")
        author.setStyleSheet("color: #888; font-size: 13px; border: none;")
        info.addWidget(author)
        hl.addLayout(info, stretch=1)

        status = "✓ 已启用" if plugin.enabled else "✗ 已禁用"
        status_color = "#22c55e" if plugin.enabled else "#ef4444"
        status_label = QLabel(status)
        status_label.setStyleSheet(f"color: {status_color}; font-size: 13px; border: none; font-weight: bold;")
        hl.addWidget(status_label)

        return card
