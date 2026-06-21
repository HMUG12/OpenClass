"""
SplashScreen — OpenClass 启动加载动画

- 渐变背景 (#2563EB → #7C3AED)，无边框 QWidget
- 应用名 + 版本号 + 圆角进度条
- 遍历 5 项初始化任务，每步强制 processEvents() 刷新 UI
- 数据库连接失败时进度条变红 + 错误提示 + 2 秒后退出
- 强制最少显示 5 秒（time.time() 循环），全部完成 + 5s 到后关闭
"""
from __future__ import annotations

import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsDropShadowEffect,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush


# ═══════════════════════════════════════════════════════════════
# 渐变背景容器
# ═══════════════════════════════════════════════════════════════

class _GradientBackground(QWidget):
    """自绘渐变背景 (#2563EB → #7C3AED)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#2563EB"))
        gradient.setColorAt(1.0, QColor("#7C3AED"))
        painter.fillRect(self.rect(), QBrush(gradient))
        painter.end()


# ═══════════════════════════════════════════════════════════════
# SplashScreen
# ═══════════════════════════════════════════════════════════════

class SplashScreen(QWidget):
    """启动加载画面 — 纯 UI，初始化任务委托给 Application。

    信号:
        initialization_finished — 进度条走完 + 5s 倒计时结束后发射（仅一次）。
    """

    initialization_finished = Signal()   # 全部完成后发射（单次）
    MIN_DURATION_MS = 5000               # 最低显示 5 秒

    def __init__(self):
        super().__init__(None)
        self._init_ui()
        self._reset_state()

        # 全屏居中
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            w, h = 600, 460
            self.setGeometry(
                geo.x() + (geo.width() - w) // 2,
                geo.y() + (geo.height() - h) // 2,
                w, h,
            )

    def _init_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._bg = _GradientBackground(self)

        container = QVBoxLayout(self)
        container.setContentsMargins(0, 0, 0, 0)
        container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container.setSpacing(0)

        inner = QVBoxLayout()
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(8)

        icon_label = QLabel("🎓")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px; border: none; background: transparent;")
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(32)
        glow.setOffset(0, 0)
        glow.setColor(QColor(255, 255, 255, 80))
        icon_label.setGraphicsEffect(glow)
        inner.addWidget(icon_label)

        name = QLabel("OpenClass")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setFont(QFont("Microsoft YaHei", 42, QFont.Weight.Bold))
        name.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        inner.addWidget(name)

        subtitle = QLabel("教师课堂工具箱")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Microsoft YaHei", 16))
        subtitle.setStyleSheet("color: rgba(255,255,255,0.70); border: none; background: transparent;")
        inner.addWidget(subtitle)

        self._version_label = QLabel("测试版")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._version_label.setFont(QFont("Consolas", 13))
        self._version_label.setStyleSheet("color: rgba(255,255,255,0.45); border: none; background: transparent;")
        inner.addWidget(self._version_label)

        inner.addSpacing(28)

        self._status_label = QLabel("正在初始化...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Microsoft YaHei", 14))
        self._status_label.setStyleSheet("color: rgba(255,255,255,0.80); border: none; background: transparent;")
        inner.addWidget(self._status_label)

        inner.addSpacing(14)

        self._progress = QProgressBar()
        self._progress.setFixedSize(420, 12)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.15);
                border: none;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255,255,255,0.90),
                    stop:1 #FFFFFF);
                border-radius: 6px;
            }
        """)
        inner.addWidget(self._progress, alignment=Qt.AlignmentFlag.AlignCenter)

        inner.addSpacing(14)

        self._tip_label = QLabel("")
        self._tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tip_label.setFont(QFont("Microsoft YaHei", 11))
        self._tip_label.setStyleSheet("color: rgba(255,255,255,0.40); border: none; background: transparent;")
        inner.addWidget(self._tip_label)

        container.addLayout(inner)

    # ═══════════════════════════════════════════════════════════
    # 状态
    # ═══════════════════════════════════════════════════════════

    def _reset_state(self) -> None:
        self._all_done = False
        self._min_expired = False
        self._init_failed = False
        self._start_time = 0.0
        self._finished_emitted = False   # 防止重复发射信号

    # ═══════════════════════════════════════════════════════════
    # 任务定义
    # ═══════════════════════════════════════════════════════════

    def _build_tasks(self) -> list[tuple[str, object, bool]]:
        """
        返回 [(描述, 可调用对象, 是否关键), ...]。
        关键任务失败 → 终止启动。
        """
        from app.application import Application
        app = Application.instance()
        return [
            ("初始化日志系统",   app._init_logging,     False),
            ("检查数据库...",    app._init_database,     True),   # 关键
            ("加载 API 配置...", app._init_api_configs,  False),
            ("加载偏好设置...",  app._init_preferences,   False),
            ("加载班级数据...",  app._init_classes,       False),
        ]

    # ═══════════════════════════════════════════════════════════
    # 启动入口
    # ═══════════════════════════════════════════════════════════

    def start(self) -> None:
        """显示 Splash → 执行初始化任务 → 等待 5s 最低显示时长。"""
        self.show()
        self.raise_()
        QTimer.singleShot(100, self._begin)

    def _begin(self) -> None:
        """逐任务执行初始化 + 5s 最低显示倒计时。两者都完成后统一发射信号。"""
        self._start_time = time.time()

        # 单一 5 秒倒计时，到期后标记 min_expired
        QTimer.singleShot(self.MIN_DURATION_MS, self._on_min_timer)

        tasks = self._build_tasks()
        total = len(tasks)

        for i, (desc, func, is_critical) in enumerate(tasks, start=1):
            self._set_status(desc)
            self._set_progress((i - 1) * 100 // total)
            QApplication.processEvents()

            try:
                func()
            except Exception as e:
                if is_critical:
                    self._handle_init_failure(desc, str(e))
                    return
                else:
                    try:
                        from app.utils.logger import logger
                        logger.warning("init step failed: %s → %s", desc, e)
                    except Exception:
                        pass

            self._set_progress(i * 100 // total)
            QApplication.processEvents()

        # ── 全部任务完成 ──
        self._all_done = True
        self._set_status("初始化完成 ✓")
        self._set_progress(100)
        QApplication.processEvents()

        # 检查是否已经可以完成（若 5s 已过则直接发射信号）
        self._try_finish()

    # ═══════════════════════════════════════════════════════════
    # 最低 5 秒计时器
    # ═══════════════════════════════════════════════════════════

    def _on_min_timer(self) -> None:
        """5 秒倒计时到期。（注：任务可能仍在执行或已完成）"""
        self._min_expired = True
        self._try_finish()

    # ═══════════════════════════════════════════════════════════
    # 统一完成检测（消除双计时器竞态条件）
    # ═══════════════════════════════════════════════════════════

    def _try_finish(self) -> None:
        """当 _all_done 和 _min_expired 都满足时，延迟关闭 → 发射信号（仅一次）。"""
        if self._finished_emitted:
            return
        if not self._all_done or not self._min_expired:
            # 若任一方未满足，显示等待提示
            if self._all_done and not self._min_expired:
                elapsed = (time.time() - self._start_time) * 1000
                remaining = max(0, self.MIN_DURATION_MS - elapsed)
                if remaining > 500:  # 避免最后几百毫秒的闪烁
                    self._set_status("即将完成...")
                    self._tip_label.setText(f"启动用时 {elapsed/1000:.1f}s，即将进入")
                    QApplication.processEvents()
            return

        # 双条件满足 → 300ms 后关闭并发射信号
        self._finished_emitted = True
        self._set_status("")
        self._tip_label.setText("")
        QApplication.processEvents()
        QTimer.singleShot(300, self._emit_finished)

    def _emit_finished(self) -> None:
        """关闭窗口并发射初始化完成信号。"""
        self.close()
        self.initialization_finished.emit()

    def _handle_init_failure(self, step_desc: str, error_msg: str) -> None:
        """关键任务失败 → 进度条变红 + 错误提示 + 2 秒后退出。"""
        self._init_failed = True
        self._all_done = False

        self._status_label.setText("初始化失败，请检查权限")
        self._status_label.setStyleSheet(
            "color: #ff6b6b; font-size: 14px; font-weight: bold; border: none; background: transparent;"
        )
        self._tip_label.setText(f"错误: {error_msg[:60]}")
        self._tip_label.setStyleSheet(
            "color: #ff6b6b; font-size: 11px; border: none; background: transparent;"
        )

        # 进度条变红
        self._progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.15);
                border: none;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: #ef4444;
                border-radius: 6px;
            }
        """)
        self._set_progress(100)
        QApplication.processEvents()

        # 2 秒后退出
        QTimer.singleShot(2000, self._close_and_exit)

    def _close_and_exit(self) -> None:
        """初始化失败后的强制退出。"""
        self.close()
        QApplication.quit()

    # ═══════════════════════════════════════════════════════════
    # 进度 & 状态
    # ═══════════════════════════════════════════════════════════

    def _set_progress(self, value: int) -> None:
        """直接设值（不用动画，因为同步执行时动画无法渲染）。"""
        self._progress.setValue(value)

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._bg:
            self._bg.setGeometry(self.rect())
