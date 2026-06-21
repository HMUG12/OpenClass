"""
🖥️ 电教工具 — 占位页面
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class AVToolsPlaceholderView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("avToolsPlaceholder")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        icon = QLabel("🖥️")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 96px; border: none;")
        layout.addWidget(icon)

        title = QLabel("电教工具")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; border: none;")
        layout.addWidget(title)

        subtitle = QLabel("敬请期待...")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #999; font-size: 18px; border: none;")
        layout.addWidget(subtitle)

        desc = QLabel("此板块正在开发中，将提供实用的电教辅助功能")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #bbb; font-size: 16px; border: none;")
        layout.addWidget(desc)
