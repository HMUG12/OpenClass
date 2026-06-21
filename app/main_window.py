"""
OpenClass 主窗口 — 优先使用 qfluentwidgets，降级为纯 PySide6
"""
import sys
from PySide6.QtWidgets import QStackedWidget, QWidget
from PySide6.QtCore import Signal as Sig

# 尝试导入 qfluentwidgets
try:
    from qfluentwidgets import (
        FluentWindow, FluentIcon, NavigationItemPosition,
        setTheme, Theme, setThemeColor
    )
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False
    from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget

from app.views.settings.settings_page import SettingsPage
from app.views.classroom.launcher_view import ClassroomLauncherView
from app.views.classroom.random_picker import RandomPickerPage
from app.views.classroom.fullscreen_timer import FullscreenTimerPage
from app.views.classroom.whiteboard import WhiteboardPage
from app.views.agent.agent_page import AgentPage
from app.views.av_tools.launcher_view import AVToolsLauncherView
from app.views.av_tools.kms_activation_view import KMSActivationView
from app.views.av_tools.system_info_view import SystemInfoView


# ═══════════════════════════════════════════════════════════════
# 敬请期待占位组件
# ═══════════════════════════════════════════════════════════════

class _ComingSoonView(QWidget):
    """占位工具页面 — 大图标 + "敬请期待" + 返回按钮。"""
    back_requested = Sig()

    def __init__(self, icon: str, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("comingSoonView")
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 20, 48, 32)
        layout.setSpacing(20)

        # 返回按钮
        back_btn = QPushButton("←  返回工具列表")
        back_btn.setFixedHeight(60)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px; font-weight: bold;
                background: rgba(128,128,128,0.08);
                color: #6366f1;
                border: 1px solid rgba(128,128,128,0.15);
                border-radius: 12px; padding: 12px 28px;
            }
            QPushButton:hover {
                background: rgba(99,102,241,0.10);
                border-color: rgba(99,102,241,0.30);
            }
        """)
        layout.addWidget(back_btn)

        layout.addStretch(1)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 80px; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 26, QFont.Weight.Bold))
        title_label.setStyleSheet("border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #94a3b8; font-size: 18px; border: none;")
        layout.addWidget(desc_label)

        layout.addStretch(2)
        back_btn.clicked.connect(self.back_requested.emit)


# ═══════════════════════════════════════════════════════════════
# AV 工具路由索引常量
# ═══════════════════════════════════════════════════════════════

_AV_LAUNCHER = 0
_AV_KMS = 1
_AV_SYSINFO = 2
_AV_NETSPEED = 3
_AV_SCREENREC = 4

_AV_TOOL_INDEX: dict[str, int] = {
    "kms_activation": _AV_KMS,
    "system_info": _AV_SYSINFO,
    "network_speed": _AV_NETSPEED,
    "screen_recorder": _AV_SCREENREC,
}


if _HAS_FLUENT:

    class MainWindow(FluentWindow):
        """主窗口 — FluentWindow 自带左侧导航"""

        def __init__(self):
            super().__init__()
            self.setWindowTitle("OpenClass — 教师课堂工具箱")
            self.resize(1400, 900)
            self.setMinimumSize(1100, 700)

            # 从持久化配置读取主题偏好，调用 ThemeManager 统一处理
            from PySide6.QtWidgets import QApplication
            from app.utils.theme_manager import ThemeManager
            from app.views.settings.settings_page import cfg, qconfig
            saved_theme = qconfig.get(cfg.themeMode) if hasattr(cfg, 'themeMode') else "light"
            app = QApplication.instance()
            if app:
                ThemeManager.apply_theme(app, saved_theme)

            self.agent_page = AgentPage()

            # ── 实用课堂容器 ──
            self.classroom_container = QStackedWidget()
            self.classroom_container.setObjectName("classroomContainer")
            self.classroom_launcher = ClassroomLauncherView()
            self.random_picker = RandomPickerPage()
            self.timer_page = FullscreenTimerPage()
            self.whiteboard_page = WhiteboardPage()
            self.classroom_container.addWidget(self.classroom_launcher)   # 0
            self.classroom_container.addWidget(self.random_picker)        # 1
            self.classroom_container.addWidget(self.timer_page)           # 2
            self.classroom_container.addWidget(self.whiteboard_page)      # 3

            # ── 电教工具容器 ──
            self.av_container = QStackedWidget()
            self.av_container.setObjectName("avToolsContainer")
            self.av_launcher = AVToolsLauncherView()
            self.kms_activation = KMSActivationView()
            self.system_info = SystemInfoView()
            self.av_coming_net = _ComingSoonView("🌐", "网络测速", "正在开发中，敬请期待...")
            self.av_coming_rec = _ComingSoonView("🎥", "屏幕录制", "正在开发中，敬请期待...")

            self.av_container.addWidget(self.av_launcher)      # 0 → 启动台
            self.av_container.addWidget(self.kms_activation)   # 1 → KMS 激活
            self.av_container.addWidget(self.system_info)      # 2 → 系统信息
            self.av_container.addWidget(self.av_coming_net)    # 3 → 网络测速（占位）
            self.av_container.addWidget(self.av_coming_rec)    # 4 → 屏幕录制（占位）

            self.av_container.setCurrentIndex(_AV_LAUNCHER)

            self.settings_page = SettingsPage()

            self._init_navigation()
            self._connect_signals()

        def _init_navigation(self) -> None:
            self.addSubInterface(
                self.agent_page, FluentIcon.ROBOT, "Agent",
                NavigationItemPosition.SCROLL
            )
            self.addSubInterface(
                self.classroom_container, FluentIcon.EDUCATION, "实用课堂",
                NavigationItemPosition.SCROLL
            )
            self.addSubInterface(
                self.av_container, FluentIcon.IOT, "电教工具",
                NavigationItemPosition.SCROLL
            )
            self.addSubInterface(
                self.settings_page, FluentIcon.SETTING, "设置",
                NavigationItemPosition.BOTTOM
            )

        def _connect_signals(self) -> None:
            self.classroom_launcher.card_clicked.connect(self._on_tool_selected)
            self.av_launcher.card_clicked.connect(self._on_av_tool_selected)
            self.stackedWidget.currentChanged.connect(self._on_main_tab_changed)

            # ── 返回按钮信号 ──
            self.kms_activation.back_requested.connect(self._return_to_av_launcher)
            self.system_info.back_requested.connect(self._return_to_av_launcher)
            self.av_coming_net.back_requested.connect(self._return_to_av_launcher)
            self.av_coming_rec.back_requested.connect(self._return_to_av_launcher)

        # ── 实用课堂 ──

        def _on_tool_selected(self, tool_id: str) -> None:
            tool_map = {"random_picker": 1, "timer": 2, "whiteboard": 3}
            idx = tool_map.get(tool_id)
            if idx is not None:
                self.classroom_container.setCurrentIndex(idx)
                if tool_id == "random_picker":
                    self.random_picker._ensure_loaded()

        # ── 电教工具 ──

        def _on_av_tool_selected(self, tool_id: str) -> None:
            idx = _AV_TOOL_INDEX.get(tool_id)
            if idx is not None:
                self.av_container.setCurrentIndex(idx)

        def _return_to_av_launcher(self) -> None:
            self.av_container.setCurrentIndex(_AV_LAUNCHER)

        # ── Tab 切换 ──

        def _on_main_tab_changed(self, index: int) -> None:
            widget = self.stackedWidget.widget(index)
            if widget is self.classroom_container:
                self.classroom_container.setCurrentIndex(0)
            elif widget is self.av_container:
                self.av_container.setCurrentIndex(_AV_LAUNCHER)
            elif widget is self.agent_page:
                self.agent_page._ensure_loaded()
            elif widget is self.settings_page:
                self.settings_page._ensure_loaded()

else:
    # ── 降级：纯 PySide6 实现 ───────────────────
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel
    from PySide6.QtCore import Qt, Signal
    from app.utils.theme_manager import ThemeManager

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("OpenClass — 教师课堂工具箱")
            self.resize(1400, 900)
            self.setMinimumSize(1100, 700)

            central = QWidget()
            self.setCentralWidget(central)
            root = QHBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # 左侧导航
            nav = QWidget()
            nav.setObjectName("navigationBar")
            nav.setFixedWidth(80)
            nav.setStyleSheet("""
                #navigationBar {
                    background: #1a1a2e; border-right: 1px solid #16213e;
                }
                #navigationBar QPushButton {
                    color: #a0a0c0; background: transparent; border: none;
                    border-radius: 10px; padding: 12px 10px; font-size: 16px;
                    text-align: center; min-height: 56px;
                }
                #navigationBar QPushButton:hover {
                    background: rgba(255,255,255,0.08); color: #e0e0ff;
                }
                #navigationBar QPushButton:checked {
                    background: rgba(99,102,241,0.3); color: #fff;
                }
            """)
            nav_layout = QVBoxLayout(nav)
            nav_layout.setContentsMargins(6, 16, 6, 16)
            nav_layout.setSpacing(4)

            logo = QLabel("OC")
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0ff;")
            nav_layout.addWidget(logo)
            nav_layout.addStretch(1)

            self._nav_btns: list[QPushButton] = []
            nav_items = [
                ("🤖\nAgent", 0), ("🧑‍🏫\n课堂", 1),
                ("🖥️\n电教", 2), ("⚙️\n设置", 3),
            ]
            for text, idx in nav_items:
                btn = QPushButton(text)
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, i=idx: self._on_nav(i))
                nav_layout.addWidget(btn)
                self._nav_btns.append(btn)

            nav_layout.addStretch(1)
            root.addWidget(nav)

            # ── 右侧内容 ──
            self.content_stack = QStackedWidget()
            self.content_stack.setObjectName("contentStack")

            self.agent_page = AgentPage()
            self.content_stack.addWidget(self.agent_page)       # 0

            # 实用课堂容器
            self.classroom_container = QStackedWidget()
            self.classroom_launcher = ClassroomLauncherView()
            self.random_picker = RandomPickerPage()
            self.timer_page = FullscreenTimerPage()
            self.whiteboard_page = WhiteboardPage()
            self.classroom_container.addWidget(self.classroom_launcher)   # 0
            self.classroom_container.addWidget(self.random_picker)        # 1
            self.classroom_container.addWidget(self.timer_page)           # 2
            self.classroom_container.addWidget(self.whiteboard_page)      # 3
            self.content_stack.addWidget(self.classroom_container)        # 1

            # 电教工具容器
            self.av_container = QStackedWidget()
            self.av_container.setObjectName("avToolsContainer")
            self.av_launcher = AVToolsLauncherView()
            self.kms_activation = KMSActivationView()
            self.system_info = SystemInfoView()
            self.av_coming_net = _ComingSoonView("🌐", "网络测速", "正在开发中，敬请期待...")
            self.av_coming_rec = _ComingSoonView("🎥", "屏幕录制", "正在开发中，敬请期待...")

            self.av_container.addWidget(self.av_launcher)      # 0
            self.av_container.addWidget(self.kms_activation)   # 1
            self.av_container.addWidget(self.system_info)      # 2
            self.av_container.addWidget(self.av_coming_net)    # 3
            self.av_container.addWidget(self.av_coming_rec)    # 4
            self.av_container.setCurrentIndex(_AV_LAUNCHER)
            self.content_stack.addWidget(self.av_container)     # 2

            self.settings_page = SettingsPage()
            self.content_stack.addWidget(self.settings_page)    # 3

            root.addWidget(self.content_stack, stretch=1)

            self._nav_btns[1].setChecked(True)
            self.content_stack.setCurrentIndex(1)

            self.classroom_launcher.card_clicked.connect(self._on_tool_selected)
            self.av_launcher.card_clicked.connect(self._on_av_tool_selected)
            self.content_stack.currentChanged.connect(self._on_main_tab_changed)

            self.kms_activation.back_requested.connect(self._return_to_av_launcher)
            self.system_info.back_requested.connect(self._return_to_av_launcher)
            self.av_coming_net.back_requested.connect(self._return_to_av_launcher)
            self.av_coming_rec.back_requested.connect(self._return_to_av_launcher)

        # ── 导航 ──

        def _on_nav(self, idx: int) -> None:
            for i, btn in enumerate(self._nav_btns):
                btn.setChecked(i == idx)
            self.content_stack.setCurrentIndex(idx)

        def _on_tool_selected(self, tool_id: str) -> None:
            tool_map = {"random_picker": 1, "timer": 2, "whiteboard": 3}
            idx = tool_map.get(tool_id)
            if idx is not None:
                self.classroom_container.setCurrentIndex(idx)

        def _on_av_tool_selected(self, tool_id: str) -> None:
            idx = _AV_TOOL_INDEX.get(tool_id)
            if idx is not None:
                self.av_container.setCurrentIndex(idx)

        def _return_to_av_launcher(self) -> None:
            self.av_container.setCurrentIndex(_AV_LAUNCHER)

        def _on_main_tab_changed(self, index: int) -> None:
            if index == 1:
                self.classroom_container.setCurrentIndex(0)
            elif index == 2:
                self.av_container.setCurrentIndex(_AV_LAUNCHER)
            elif index == 0:
                self.agent_page._ensure_loaded()
            elif index == 3:
                self.settings_page._ensure_loaded()
