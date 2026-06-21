"""
🖥️ 电教工具 — 工具启动台（网格卡片布局）

与"实用课堂"风格统一：图标卡片网格 + 点击加载对应工具组件。
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent


# ═══════════════════════════════════════════════════════════════
# 工具卡片
# ═══════════════════════════════════════════════════════════════

class AVToolCard(QFrame):
    """卡片 — 大图标(60px) + 名称(20pt) + 描述(14pt)。"""
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, desc: str, tool_id: str, parent=None):
        super().__init__(parent)
        self.setObjectName("avToolCard")
        self.tool_id = tool_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(240, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            QFrame#avToolCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 20px;
            }
            QFrame#avToolCard:hover {
                border-color: #6366f1;
                background: #f8faff;
            }
            QFrame#avToolCard:pressed {
                border-color: #4F46E5;
                background: #EEF2FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 28, 24, 28)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 60px; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        layout.addWidget(desc_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self.tool_id)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════
# 工具启动台
# ═══════════════════════════════════════════════════════════════

class AVToolsLauncherView(QWidget):
    """电教工具启动台 — 2 列网格卡片。"""
    card_clicked = Signal(str)

    TOOLS = [
        ("🖥️", "KMS激活", "设置KMS服务器并激活\nWindows系统授权", "kms_activation"),
        ("📊", "系统信息", "查看一体机CPU、内存\n磁盘、系统版本", "system_info"),
        ("🌐", "网络测速", "测试当前网络上下行\n速度与延迟", "network_speed"),
        ("🎥", "屏幕录制", "录制课堂屏幕内容\n保存为视频文件", "screen_recorder"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("avToolsLauncher")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(28)

        # ── 标题 ──
        title_label = QLabel("🖥️  电教工具 — 工具启动台")
        title_label.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        title_label.setStyleSheet("border: none;")
        layout.addWidget(title_label)

        subtitle = QLabel("选择一个工具开始使用")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        layout.addWidget(subtitle)

        # ── 2 列网格 ──
        grid = QGridLayout()
        grid.setSpacing(24)

        for idx, (icon_text, title, desc, tool_id) in enumerate(self.TOOLS):
            card = AVToolCard(icon_text, title, desc, tool_id)
            card.clicked.connect(self.card_clicked.emit)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)
        layout.addStretch(1)
