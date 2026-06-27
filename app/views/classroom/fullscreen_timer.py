"""
⏱️ 全屏计时器 — 正计时/倒计时 | 状态机 | 静态深色渐变 | qfluentwidgets 按钮

状态:  Idle → Running ⇄ Paused → Finished
全屏:  独立 FramelessWindow，静态深色渐变背景，霓虹数字 + 磨砂按钮
铃声:  QSoundEffect 播放动态生成 WAV（非阻塞）
"""
from __future__ import annotations

import math
import struct
import wave
import tempfile
from enum import Enum, auto
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QButtonGroup, QRadioButton, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect, QDialog, QPushButton,
)
from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QFont, QKeyEvent, QColor, QResizeEvent, QShowEvent, QMouseEvent,
    QPainter, QBrush, QPaintEvent, QLinearGradient,
)
from PySide6.QtMultimedia import QSoundEffect

from qfluentwidgets import (
    PrimaryPushButton, ToolButton, FluentIcon,
    themeColor, isDarkTheme,
)

# ═══════════════════════════════════════════════════════════════
# 铃声 — 动态生成 WAV → QSoundEffect 异步播放
# ═══════════════════════════════════════════════════════════════

_BEEP_WAV: str | None = None


def _ensure_beep_wav() -> str:
    """按需生成一次 beep WAV 文件，返回路径。"""
    global _BEEP_WAV
    if _BEEP_WAV is not None:
        return _BEEP_WAV

    dst = Path(tempfile.gettempdir()) / "openclass_timer_beep.wav"
    if dst.exists():
        _BEEP_WAV = str(dst)
        return _BEEP_WAV

    sample_rate = 22050
    duration = 0.32          # 秒
    freq = 880               # Hz
    n_samples = int(sample_rate * duration)
    frames: list[bytes] = []

    for i in range(n_samples):
        t = i / sample_rate
        envelope = max(0.0, 1.0 - t / duration)          # 淡出包络
        val = int(32767 * 0.65 * envelope * math.sin(2.0 * math.pi * freq * t))
        frames.append(struct.pack("<h", val))

    with wave.open(str(dst), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))

    _BEEP_WAV = str(dst)
    return _BEEP_WAV


class _RingPlayer:
    """非阻塞铃声播放器 — QSoundEffect + winsound 降级。"""

    _effect: QSoundEffect | None = None

    @classmethod
    def play(cls, times: int = 3, interval_ms: int = 500) -> None:
        """播放铃声 times 次，间隔 interval_ms。"""
        path = _ensure_beep_wav()

        # 主方案：QSoundEffect（真正非阻塞）
        try:
            if cls._effect is None:
                cls._effect = QSoundEffect()
                cls._effect.setSource(QUrl.fromLocalFile(path))
                cls._effect.setVolume(0.8)
            if not cls._effect.isPlaying():
                cls._effect.play()

            # 多次播放用 QTimer 驱动
            if times > 1:
                def _chain(remaining: int) -> None:
                    if remaining <= 1:
                        return
                    QTimer.singleShot(interval_ms, lambda: _inner(remaining - 1))

                def _inner(remaining: int) -> None:
                    if cls._effect:
                        cls._effect.play()
                    _chain(remaining)

                _chain(times)
            return
        except Exception:
            pass

        # 降级：Windows 系统蜂鸣
        try:
            import winsound
            import threading

            def _beep_thread() -> None:
                for _ in range(times):
                    winsound.Beep(880, 320)
                    if times > 1:
                        import time
                        time.sleep(interval_ms / 1000.0)

            t = threading.Thread(target=_beep_thread, daemon=True)
            t.start()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 环形进度条 — QPainter 自绘（触控友好）
# ═══════════════════════════════════════════════════════════════

class _FullscreenTimerWindow(QWidget):
    """独立全屏窗口 — 静态深色渐变背景 + 霓虹数字 + 磨砂底部控制栏。"""
    closed = Signal()
    toggle_requested = Signal()   # 点击数字 → 切换开始/暂停
    pause_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setObjectName("fullscreenTimerWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setStyleSheet("QWidget#fullscreenTimerWindow { border: none; }")
        self.setCursor(Qt.CursorShape.BlankCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 静态深色渐变背景 ──
        self._bg = _StaticGradientBg(self)

        # ── 中央数字 ──
        self.time_label = QLabel("00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFont(QFont("Microsoft YaHei", 200, QFont.Weight.Black))
        self.time_label.setStyleSheet(
            "color: #00D4FF; background: transparent; border: none; font-weight: 900;"
        )
        self.time_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.time_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.time_label.installEventFilter(self)

        # 静态霓虹发光 — blur=10px，淡色
        glow = QGraphicsDropShadowEffect(self.time_label)
        glow.setBlurRadius(10)
        glow.setOffset(0, 0)
        glow.setColor(QColor(0, 212, 255, 80))
        self.time_label.setGraphicsEffect(glow)

        layout.addWidget(self.time_label, stretch=1)

        # ── 底部半透明磨砂控制栏 ──
        self._build_bottom_bar(layout)

    def _build_bottom_bar(self, parent_layout: QVBoxLayout) -> None:
        """底部磨砂按钮栏：暂停/继续 | 重置 | 退出全屏。"""
        bar = QWidget()
        bar.setObjectName("fsBottomBar")
        bar.setFixedHeight(80)
        bar.setStyleSheet("""
            QWidget#fsBottomBar {
                background: rgba(15, 18, 25, 0.75);
                border-top: 1px solid rgba(255,255,255,0.06);
            }
        """)

        btn_row = QHBoxLayout(bar)
        btn_row.setContentsMargins(30, 12, 30, 12)
        btn_row.setSpacing(16)

        self._pause_btn = QPushButton("⏸  暂停")
        self._pause_btn.setMinimumSize(160, 56)
        self._pause_btn.setStyleSheet(_FS_BTN_STYLE)
        self._pause_btn.clicked.connect(self.pause_requested.emit)
        btn_row.addWidget(self._pause_btn)

        self._reset_btn = QPushButton("↺  重置")
        self._reset_btn.setMinimumSize(140, 56)
        self._reset_btn.setStyleSheet(_FS_BTN_STYLE)
        self._reset_btn.clicked.connect(self.reset_requested.emit)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()

        self._exit_btn = QPushButton("✕  退出")
        self._exit_btn.setMinimumSize(140, 56)
        self._exit_btn.setStyleSheet(_FS_EXIT_BTN_STYLE)
        self._exit_btn.clicked.connect(self._exit)
        btn_row.addWidget(self._exit_btn)

        parent_layout.addWidget(bar)

    # ── 公开接口 ──

    def set_time(self, text: str) -> None:
        self.time_label.setText(text)

    def set_pause_text(self, text: str) -> None:
        self._pause_btn.setText(text)

    # ── 事件 ──

    def eventFilter(self, obj, event) -> bool:
        if obj is self.time_label and event.type() == event.Type.MouseButtonPress:
            self.toggle_requested.emit()
            return True
        return super().eventFilter(obj, event)

    def showEvent(self, event: QShowEvent) -> None:
        self.setCursor(Qt.CursorShape.BlankCursor)
        QTimer.singleShot(3000, lambda: self.setCursor(Qt.CursorShape.BlankCursor))
        super().showEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._bg:
            self._bg.setGeometry(self.rect())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def _exit(self) -> None:
        self.hide()
        self.closed.emit()


# ═══════════════════════════════════════════════════════════════
# 磨砂按钮样式
# ═══════════════════════════════════════════════════════════════

_FS_BTN_STYLE = """
    QPushButton {
        font-size: 18px; font-weight: bold;
        background: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.75);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
    }
    QPushButton:hover {
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.95);
        border-color: rgba(255,255,255,0.20);
    }
    QPushButton:pressed {
        background: rgba(255,255,255,0.18);
        color: #FFFFFF;
    }
"""

_FS_EXIT_BTN_STYLE = """
    QPushButton {
        font-size: 18px; font-weight: bold;
        background: rgba(239,68,68,0.18);
        color: rgba(255,255,255,0.70);
        border: 1px solid rgba(239,68,68,0.30);
        border-radius: 12px;
    }
    QPushButton:hover {
        background: rgba(239,68,68,0.32);
        color: rgba(255,255,255,0.95);
        border-color: rgba(239,68,68,0.50);
    }
    QPushButton:pressed {
        background: rgba(239,68,68,0.45);
        color: #FFFFFF;
    }
"""


# ═══════════════════════════════════════════════════════════════
# 静态渐变背景 Widget
# ═══════════════════════════════════════════════════════════════

class _StaticGradientBg(QWidget):
    """静态深色渐变 (#0B0E14 → #1A1F2E)，无动画。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#0B0E14"))
        gradient.setColorAt(0.5, QColor("#121624"))
        gradient.setColorAt(1.0, QColor("#1A1F2E"))
        painter.fillRect(self.rect(), QBrush(gradient))
        painter.end()


# ═══════════════════════════════════════════════════════════════
# 计时器主页面
# ═══════════════════════════════════════════════════════════════

# 状态枚举
class TimerState(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    FINISHED = auto()


# ═══════════════════════════════════════════════════════════════
# 计时结束弹窗
# ═══════════════════════════════════════════════════════════════

class _TimerFinishedDialog(QDialog):
    """500×300 弹窗，显示 '⏰ 时间到！'。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 300)
        self.setModal(True)

        container = QFrame(self)
        container.setObjectName("finishedDialog")
        container.setGeometry(0, 0, 500, 300)
        container.setStyleSheet("""
            QFrame#finishedDialog {
                background: rgba(10, 10, 15, 0.92);
                border: 2px solid rgba(0, 212, 255, 0.40);
                border-radius: 28px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        icon_label = QLabel("⏰")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px; border: none; background: transparent;")
        layout.addWidget(icon_label)

        text_label = QLabel("时间到！")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(
            "color: #00D4FF; font-size: 42px; font-weight: 900; "
            "border: none; background: transparent;"
        )
        layout.addWidget(text_label)

        sub_text = QLabel("点击下方按钮关闭")
        sub_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_text.setStyleSheet("color: rgba(255,255,255,0.40); font-size: 16px; border: none;")
        layout.addWidget(sub_text)

        close_btn = QPushButton("✓  确定")
        close_btn.setFixedSize(200, 70)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00D4FF, stop:1 #00B4D8);
                color: #0A0A0C; font-size: 22px; font-weight: 900;
                border: none; border-radius: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33DEFF, stop:1 #00D4FF);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00A8C8, stop:1 #0098B0);
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # 居中于屏幕
        screen = self.screen() or (self.window().windowHandle().screen() if self.window() else None)
        if screen:
            geo = screen.geometry()
            self.move((geo.width() - 500) // 2, (geo.height() - 300) // 2)


class FullscreenTimerPage(QWidget):
    """全屏计时器 — 教师课堂计时核心组件。"""

    PRESETS = [3, 5, 10, 15]  # 分钟

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("timerPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── 内部状态 ──
        self._state: TimerState = TimerState.IDLE
        self._mode: str = "countdown"           # "countdown" | "stopwatch"
        self._remaining: int = 0                 # 倒计时剩余秒数
        self._elapsed: int = 0                   # 正计时已走秒数
        self._total_seconds: int = 300           # 参考总秒数（用于进度条分母）

        # ── 定时器 ──
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self._on_tick)

        # ── 全屏窗口 ──
        self._fs_window = _FullscreenTimerWindow()
        self._fs_window.closed.connect(self._on_fullscreen_closed)
        self._fs_window.toggle_requested.connect(self._on_start_clicked)
        self._fs_window.pause_requested.connect(self._on_start_clicked)
        self._fs_window.reset_requested.connect(self._reset)

        # ── 结束弹窗 ──
        self._finished_dialog = _TimerFinishedDialog()

        self._build_ui()
        self._sync_button_state()

    # ═══════════════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(20)

        # ── 标题 ──
        title = QLabel("⏱️  全屏计时器")
        title.setStyleSheet("font-size: 28px; font-weight: bold; border: none;")
        title.setObjectName("timerPageTitle")
        layout.addWidget(title)

        subtitle = QLabel("适用于课堂限时练习、考试倒计时等场景")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        layout.addWidget(subtitle)

        # ── 模式切换 ──
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)

        mode_label = QLabel("计时模式")
        mode_label.setStyleSheet("font-size: 16px; font-weight: 500; border: none;")
        mode_row.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self._countdown_radio = QRadioButton("⏲  倒计时")
        self._stopwatch_radio = QRadioButton("⏱  正计时")
        for r in (self._countdown_radio, self._stopwatch_radio):
            r.setStyleSheet("font-size: 16px; min-width: 120px; min-height: 48px;")
            self.mode_group.addButton(r)
        self._countdown_radio.setChecked(True)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)

        mode_row.addWidget(self._countdown_radio)
        mode_row.addWidget(self._stopwatch_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── 预设按钮行 + 手动输入 ──
        preset_row = QHBoxLayout()
        preset_row.setSpacing(15)

        preset_label = QLabel("快捷预设")
        preset_label.setStyleSheet("font-size: 16px; font-weight: 500; border: none;")
        preset_row.addWidget(preset_label)

        # ToolButton 作为预设按钮 — 70px 高防误触
        self._preset_btns: list[ToolButton] = []
        for mins in self.PRESETS:
            btn = ToolButton(FluentIcon.HISTORY, self)
            btn.setText(f"{mins} 分钟")
            btn.setToolTip(f"设为 {mins} 分钟倒计时")
            btn.setMinimumSize(120, 70)
            btn.clicked.connect(lambda checked, m=mins: self._set_preset(m))
            preset_row.addWidget(btn)
            self._preset_btns.append(btn)

        preset_row.addSpacing(20)

        spin_label = QLabel("自定义")
        spin_label.setStyleSheet("font-size: 16px; border: none;")
        preset_row.addWidget(spin_label)

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(1, 120)
        self.minute_spin.setValue(5)
        self.minute_spin.setFixedWidth(80)
        self.minute_spin.setSuffix(" min")
        self.minute_spin.setStyleSheet("font-size: 16px; padding: 8px 12px; min-height: 48px;")
        preset_row.addWidget(self.minute_spin)

        preset_row.addStretch()
        layout.addLayout(preset_row)

        # ── 中央时间数字（可点击切换开始/暂停）──
        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("timerNumber")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFont(QFont("Microsoft YaHei", 80, QFont.Weight.Black))
        self.time_label.setMinimumHeight(160)
        self.time_label.setStyleSheet("""
            border: 2px solid rgba(0,0,0,0.06);
            border-radius: 20px;
            background: transparent;
        """)
        self.time_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.time_label.installEventFilter(self)
        layout.addWidget(self.time_label)

        # ── 控制按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)

        self.start_btn = PrimaryPushButton(FluentIcon.PLAY, "开始计时")
        self.start_btn.setMinimumSize(200, 80)
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.start_btn)

        self.reset_btn = PrimaryPushButton(FluentIcon.CANCEL, "重置")
        self.reset_btn.setMinimumSize(140, 80)
        self.reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch()

        self.fullscreen_btn = PrimaryPushButton(FluentIcon.FULL_SCREEN, "全屏显示")
        self.fullscreen_btn.setMinimumSize(180, 80)
        self.fullscreen_btn.clicked.connect(self._enter_fullscreen)
        btn_row.addWidget(self.fullscreen_btn)

        layout.addLayout(btn_row)
        layout.addStretch(1)

    # ═══════════════════════════════════════════════════════════
    # 状态管理
    # ═══════════════════════════════════════════════════════════

    def _sync_button_state(self) -> None:
        """根据当前 TimerState 刷新按钮文字和启用状态。"""
        s = self._state

        if s == TimerState.IDLE:
            self.start_btn.setText("▶  开始计时")
            self.start_btn.setIcon(FluentIcon.PLAY)
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.minute_spin.setEnabled(True)
            self._countdown_radio.setEnabled(True)
            self._stopwatch_radio.setEnabled(True)
            for b in self._preset_btns:
                b.setEnabled(True)

        elif s == TimerState.RUNNING:
            self.start_btn.setText("⏸  暂停")
            self.start_btn.setIcon(FluentIcon.PAUSE)
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.minute_spin.setEnabled(False)
            self._countdown_radio.setEnabled(False)
            self._stopwatch_radio.setEnabled(False)
            for b in self._preset_btns:
                b.setEnabled(False)

        elif s == TimerState.PAUSED:
            self.start_btn.setText("▶  继续")
            self.start_btn.setIcon(FluentIcon.PLAY)
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.minute_spin.setEnabled(False)
            self._countdown_radio.setEnabled(False)
            self._stopwatch_radio.setEnabled(False)
            for b in self._preset_btns:
                b.setEnabled(False)

        elif s == TimerState.FINISHED:
            self.start_btn.setText("▶  重新开始")
            self.start_btn.setIcon(FluentIcon.PLAY)
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.minute_spin.setEnabled(True)
            self._countdown_radio.setEnabled(True)
            self._stopwatch_radio.setEnabled(True)
            for b in self._preset_btns:
                b.setEnabled(True)

    # ═══════════════════════════════════════════════════════════
    # 动作
    # ═══════════════════════════════════════════════════════════

    def _on_mode_changed(self, btn: QRadioButton) -> None:
        self._mode = "stopwatch" if "正计时" in btn.text() else "countdown"
        self._reset()

    def _set_preset(self, mins: int) -> None:
        self._reset()
        self.minute_spin.setValue(mins)
        self._remaining = mins * 60
        self._total_seconds = self._remaining
        self._update_display()

    def _on_start_clicked(self) -> None:
        if self._state == TimerState.RUNNING:
            self._pause()
        else:
            self._start()

    def _start(self) -> None:
        if self._state == TimerState.FINISHED:
            self._reset()

        # 倒计时：确保有剩余时间
        if self._mode == "countdown" and self._remaining <= 0:
            self._remaining = self.minute_spin.value() * 60
            self._total_seconds = self._remaining

        # 正计时：记录参考总时间（用于进度条）
        if self._mode == "stopwatch":
            self._total_seconds = self.minute_spin.value() * 60

        self._tick_timer.start(1000)
        self._state = TimerState.RUNNING
        self._sync_button_state()
        self._update_display()

    def _pause(self) -> None:
        self._tick_timer.stop()
        self._state = TimerState.PAUSED
        self._sync_button_state()

    def _reset(self) -> None:
        self._tick_timer.stop()
        self._remaining = 0
        self._elapsed = 0
        self._total_seconds = self.minute_spin.value() * 60
        self._state = TimerState.IDLE
        self._sync_button_state()
        self._update_display()

    # ═══════════════════════════════════════════════════════════
    # 秒级 tick
    # ═══════════════════════════════════════════════════════════

    def _on_tick(self) -> None:
        if self._mode == "countdown":
            self._remaining -= 1
            if self._remaining <= 0:
                self._remaining = 0
                self._tick_timer.stop()
                self._state = TimerState.FINISHED
                self._sync_button_state()
                self._update_display()
                _RingPlayer.play(times=3, interval_ms=600)
                # 弹出巨大闪烁结束弹窗
                self._finished_dialog.show()
                return
        else:
            self._elapsed += 1
            if self._elapsed >= self._total_seconds:
                self._elapsed = self._total_seconds
                self._tick_timer.stop()
                self._state = TimerState.FINISHED
                self._sync_button_state()
                self._update_display()
                _RingPlayer.play(times=3, interval_ms=600)
                self._finished_dialog.show()
                return

        self._update_display()

    # ═══════════════════════════════════════════════════════════
    # 显示刷新
    # ═══════════════════════════════════════════════════════════

    def _update_display(self) -> None:
        # 分钟:秒 格式化
        total = max(self._remaining, 0) if self._mode == "countdown" else self._elapsed
        mins, secs = divmod(total, 60)
        text = f"{mins:02d}:{secs:02d}"
        self.time_label.setText(text)

        # 同步全屏窗口
        if self._fs_window.isVisible():
            self._fs_window.set_time(text)
            # 同步暂停按钮文字
            if self._state == TimerState.RUNNING:
                self._fs_window.set_pause_text("⏸  暂停")
            elif self._state == TimerState.PAUSED:
                self._fs_window.set_pause_text("▶  继续")

    # ═══════════════════════════════════════════════════════════
    # 事件过滤：点击时间数字 → 切换开始/暂停
    # ═══════════════════════════════════════════════════════════

    def eventFilter(self, obj, event) -> bool:
        if obj is self.time_label and event.type() == event.Type.MouseButtonPress:
            self._on_start_clicked()
            return True
        return super().eventFilter(obj, event)

    def _enter_fullscreen(self) -> None:
        screen = self.screen() or self.window().windowHandle().screen()
        self._fs_window.setGeometry(screen.geometry())
        self._fs_window.set_time(self.time_label.text())
        if self._state == TimerState.PAUSED:
            self._fs_window.set_pause_text("▶  继续")
        else:
            self._fs_window.set_pause_text("⏸  暂停")

        # 深色主题处理主窗口
        self._override_dark_theme(True)

        self._fs_window.showFullScreen()
        self._fs_window.activateWindow()

        from app.utils.signal_bus import signal_bus
        signal_bus.timer_fullscreen_entered.emit()

    def _on_fullscreen_closed(self) -> None:
        self._fs_window.hide()
        # 主窗口恢复实际主题
        self._override_dark_theme(False)

        if self.window():
            self.window().activateWindow()
            self.window().raise_()

        from app.utils.signal_bus import signal_bus
        signal_bus.timer_fullscreen_exited.emit()

    def _override_dark_theme(self, forced: bool) -> None:
        """强制深色主题色值 / 恢复实际主题。"""
        if forced:
            hex_color = "#00D4FF"
        else:
            hex_color = "#00D4FF" if isDarkTheme() else "#2563EB"
        self.time_label.setStyleSheet(
            self.time_label.styleSheet()
            + f"color: {hex_color}; font-weight: 900;"
        )
