"""
🧑‍🏫 实用课堂 — 工具启动台（网格卡片布局）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent


class ToolCard(QFrame):
    """卡片 — 大图标 + 标题 + 描述"""
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, desc: str, tool_id: str, parent=None):
        super().__init__(parent)
        self.setObjectName("toolCard")
        self.tool_id = tool_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(240, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            QFrame#toolCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 20px;
                min-width: 60px;
                min-height: 60px;
            }
            QFrame#toolCard:hover {
                border-color: #6366f1;
                background: #f8faff;
            }
            QFrame#toolCard:pressed {
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
        icon_label.setStyleSheet("font-size: 52px; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        layout.addWidget(desc_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self.tool_id)
        super().mousePressEvent(event)


class ClassroomLauncherView(QWidget):
    """工具启动台 — 3 列网格"""
    card_clicked = Signal(str)

    TOOLS = [
        ("🎰", "随机点名", "老虎机动效滚动抽取\n支持排除已点 + 空格键触发", "random_picker"),
        ("⏱️", "全屏计时器", "正计时 / 倒计时\n全屏超大数字 + 铃声提醒", "timer"),
        ("✏️", "批注白板", "半透明全屏画布\n触摸 / 数位笔 / 鼠标涂鸦", "whiteboard"),
        ("📅", "课程表悬浮窗", "桌面悬浮课程表\n磨砂背景 / 置顶 / 可拖拽", "schedule"),
        # ── 媒体工具 ──
        ("🎬", "视频播放", "VLC内核视频播放器\n播放/暂停/全屏/列表", "video_player"),
        ("🎵", "音频播放", "本地音乐播放器\n播放列表 + 进度控制", "audio_player"),
        # ── 文件工具 ──
        ("📦", "解压工具", "多格式解压\n7z/ZIP/RAR + 密码", "extractor"),
        ("🔄", "音频转换", "音频格式批量转换\nMP3/WAV/FLAC/OGG", "audio_converter"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("classroomLauncher")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(28)

        title_label = QLabel("🧑‍🏫  实用课堂 — 工具启动台")
        title_label.setStyleSheet("font-size: 26px; font-weight: bold; border: none;")
        layout.addWidget(title_label)

        subtitle = QLabel("选择一个课堂工具开始使用")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        layout.addWidget(subtitle)

        self._card_grid = QGridLayout()
        self._card_grid.setSpacing(24)

        for idx, (icon_text, title, desc, tool_id) in enumerate(self.TOOLS):
            card = ToolCard(icon_text, title, desc, tool_id)
            card.clicked.connect(self.card_clicked.emit)
            row, col = divmod(idx, 3)
            self._card_grid.addWidget(card, row, col)

        layout.addLayout(self._card_grid)
        layout.addStretch(1)

    def resizeEvent(self, event) -> None:
        """确保子组件在窗口大小变化时正确重绘"""
        super().resizeEvent(event)
        self.updateGeometry()
