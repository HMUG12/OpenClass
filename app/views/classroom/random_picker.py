"""
🎰 随机点名器 — 触控一体机优化版

状态机:  IDLE → SCROLLING (40ms, 2.5s) → DECELERATING → STOPPED
动画:    100pt 姓名轮播 | 180px 圆形按钮呼吸灯 + pressed 缩小回弹
        released 触发点名 | 定格后姓名跳动两下 | 底部横幅滑入
数据:    students / call_records 表读写 | 防重 + 全员点完自动重置
"""
from __future__ import annotations

import random
from datetime import datetime
from enum import Enum, auto

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QFrame, QSizePolicy, QGraphicsDropShadowEffect, QAbstractItemView,
    QPushButton,
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QPoint,
)
from PySide6.QtGui import QFont, QColor, QAction, QPainter, QBrush, QPen, QPaintEvent

from qfluentwidgets import (
    FluentIcon, isDarkTheme, SwitchButton,
)

from app.database.db_manager import db
from app.utils.signal_bus import signal_bus


# ═══════════════════════════════════════════════════════════════
# 点名状态机
# ═══════════════════════════════════════════════════════════════

class PickerState(Enum):
    IDLE = auto()
    SCROLLING = auto()
    DECELERATING = auto()
    STOPPED = auto()


# ═══════════════════════════════════════════════════════════════
# 底部横幅通知 — 滑动动画 + 3s 淡出
# ═══════════════════════════════════════════════════════════════

class _BannerWidget(QFrame):
    """底部横条 — 从底部滑入，3s 后自动淡出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pickerBanner")
        self.setFixedHeight(60)
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)

        self._icon = QLabel("🎯")
        self._icon.setStyleSheet("font-size: 28px; border: none; background: transparent;")
        layout.addWidget(self._icon)

        self._text = QLabel()
        self._text.setStyleSheet(
            "color: #FFFFFF; font-size: 20px; font-weight: 700; border: none; background: transparent;"
        )
        layout.addWidget(self._text, stretch=1)

        # 淡出定时器
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._fade_out)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(600)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(lambda: self.setVisible(False))

    def show_message(self, name: str, count: int) -> None:
        self._text.setText(f"{name}  已点，累计 {count} 次")
        self.setWindowOpacity(1.0)
        self.setVisible(True)
        self.raise_()
        self._fade_timer.start(3000)

    def _fade_out(self) -> None:
        if self.isVisible():
            self._fade_anim.start()

    def apply_theme(self, dark: bool) -> None:
        bg = "rgba(0,212,255,0.85)" if dark else "rgba(37,99,235,0.88)"
        self.setStyleSheet(f"""
            QFrame#pickerBanner {{
                background: {bg};
                border: none;
                border-radius: 14px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# 圆形点名按钮 — 180px | 呼吸灯 | pressed 缩小回弹
# ═══════════════════════════════════════════════════════════════

class _DrawButton(QPushButton):
    """180px 圆形按钮，呼吸灯 + pressed 缩小回弹，released 触发点名。"""
    draw_triggered = Signal()

    DIAMETER = 180
    PRESSED_SCALE = 0.88

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pickerDrawBtn")
        self.setFixedSize(self.DIAMETER, self.DIAMETER)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("抽")
        self.setStyleSheet(f"""
            QPushButton#pickerDrawBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7C3AED, stop:1 #5B21B6
                );
                color: #FFFFFF;
                border: 4px solid rgba(255,255,255,0.20);
                border-radius: {self.DIAMETER // 2}px;
                font-size: 40px;
                font-weight: 900;
            }}
            QPushButton#pickerDrawBtn:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5B21B6, stop:1 #4C1D95
                );
                border-color: rgba(255,255,255,0.40);
            }}
        """)

        # ── 呼吸灯 ──
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(24)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(124, 58, 237, 200))
        self.setGraphicsEffect(self._glow)

        self._breathe_anim = QPropertyAnimation(self._glow, b"blurRadius")
        self._breathe_anim.setDuration(1800)
        self._breathe_anim.setStartValue(20)
        self._breathe_anim.setKeyValueAt(0.5, 44)
        self._breathe_anim.setEndValue(20)
        self._breathe_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breathe_anim.setLoopCount(-1)
        self._breathe_anim.start()

        # ── 点击缩放动画 ──
        self._press_anim = QPropertyAnimation(self, b"geometry")
        self._press_anim.setDuration(120)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._pressed = False

    def mousePressEvent(self, event) -> None:
        """按下时缩小到 88%。"""
        self._pressed = True
        center = self.geometry().center()
        s = int(self.DIAMETER * self.PRESSED_SCALE)
        offset = (self.DIAMETER - s) // 2
        self._press_anim.stop()
        self._press_anim.setStartValue(self.geometry())
        self._press_anim.setEndValue(
            self.geometry().__class__(center.x() - s // 2, center.y() - s // 2, s, s)
        )
        self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """抬起时恢复大小并触发点名。"""
        if self._pressed:
            self._pressed = False
            center = self.geometry().center()
            d = self.DIAMETER
            x, y = center.x() - d // 2, center.y() - d // 2
            self._press_anim.stop()
            self._press_anim.setStartValue(self.geometry())
            self._press_anim.setEndValue(self.geometry().__class__(x, y, d, d))
            self._press_anim.start()
            self.draw_triggered.emit()
        super().mouseReleaseEvent(event)

    def set_glow_color(self, color: QColor) -> None:
        self._glow.setColor(color)


# ═══════════════════════════════════════════════════════════════
# 主页面
# ═══════════════════════════════════════════════════════════════

class RandomPickerPage(QWidget):
    """随机点名 — 触控大屏优化"""

    SCROLL_INTERVAL = 40        # ms — 快速轮播
    SCROLL_DURATION = 2500      # ms — 快速阶段持续
    DECEL_MAX_INTERVAL = 520    # ms — 最慢间隔
    DECEL_STEP = 30             # ms — 每 tick 递增

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("randomPickerPage")

        self._state: PickerState = PickerState.IDLE
        self._pool: list[dict] = []
        self._all_students: list[dict] = []
        self._tick_count: int = 0
        self._current_interval: int = self.SCROLL_INTERVAL
        self._picked: dict | None = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self._on_tick)
        self._loaded: bool = False  # 懒加载标记

        self._build_ui()

        # 监听名单变动（信号连接，无 DB 操作）
        signal_bus.student_list_changed.connect(self._on_student_list_changed)

    # ═══════════════════════════════════════════════════════════
    # 懒加载
    # ═══════════════════════════════════════════════════════════

    def _ensure_loaded(self) -> None:
        """首次访问时加载 DB 数据（避免启动时卡顿）。"""
        if self._loaded:
            return
        self._loaded = True
        self._load_classes()
        self._refresh_list()

    # ═══════════════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 左侧：点名核心区 ──
        left = QWidget()
        left.setObjectName("pickerCore")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(36, 20, 36, 12)
        left_layout.setSpacing(12)

        # ── 顶部控制栏：班级 + 排除开关 + 剩余人数 ──
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(20)

        ctrl_bar.addWidget(QLabel("班级:"))
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(160)
        self.class_combo.setStyleSheet("font-size: 18px; padding: 10px 16px; min-height: 56px;")
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        ctrl_bar.addWidget(self.class_combo)

        ctrl_bar.addSpacing(8)

        exclude_label = QLabel("排除已点")
        exclude_label.setStyleSheet("font-size: 18px; font-weight: 500; border: none;")
        ctrl_bar.addWidget(exclude_label)

        self.exclude_switch = SwitchButton()
        self.exclude_switch.setChecked(True)
        self.exclude_switch.checkedChanged.connect(self._refresh_list)
        ctrl_bar.addWidget(self.exclude_switch)

        ctrl_bar.addSpacing(16)

        self.remaining_label = QLabel("剩余 0 人")
        self.remaining_label.setStyleSheet(
            "color: #00D4FF; font-size: 24px; font-weight: 900; border: none;"
        )
        ctrl_bar.addWidget(self.remaining_label)

        ctrl_bar.addStretch()
        left_layout.addLayout(ctrl_bar)

        # ── 中央姓名展示区（占主要空间）────
        name_card = QFrame()
        name_card.setObjectName("pickerNameCard")
        name_card.setStyleSheet("""
            QFrame#pickerNameCard {
                background: rgba(0,0,0,0.02);
                border: 2px dashed rgba(0,0,0,0.06);
                border-radius: 28px;
            }
        """)
        name_card_layout = QVBoxLayout(name_card)
        name_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel("准备好了吗？")
        self.name_label.setObjectName("pickerName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Microsoft YaHei", 64, QFont.Weight.Black))
        self.name_label.setMinimumHeight(240)
        self.name_label.setStyleSheet("border: none; background: transparent;")
        name_card_layout.addWidget(self.name_label)

        # 空池提示标签
        self._empty_hint = QLabel("请前往设置 → 👥 名单 导入学生")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setFont(QFont("Microsoft YaHei", 18))
        self._empty_hint.setStyleSheet(
            "color: #f59e0b; border: none; background: transparent; padding: 8px;"
        )
        self._empty_hint.setVisible(False)
        name_card_layout.addWidget(self._empty_hint)

        left_layout.addWidget(name_card, stretch=1)

        # ── 180px 圆形点名按钮（居中）──
        btn_area = QHBoxLayout()
        btn_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.draw_btn = _DrawButton()
        self.draw_btn.draw_triggered.connect(self._on_draw_triggered)
        btn_area.addWidget(self.draw_btn)
        left_layout.addLayout(btn_area)

        # ── 底部横幅 ──
        self.banner = _BannerWidget()
        left_layout.addWidget(self.banner)

        root.addWidget(left, stretch=3)

        # ── 右侧：学生名单 ──
        right = QFrame()
        right.setObjectName("pickerListPanel")
        right.setFixedWidth(280)
        right.setStyleSheet("""
            QFrame#pickerListPanel {
                background: rgba(0,0,0,0.02);
                border-left: 1px solid rgba(0,0,0,0.06);
            }
        """)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 20, 16, 16)
        right_layout.setSpacing(10)

        list_title = QLabel("🧑‍🎓  学生名单")
        list_title.setStyleSheet("font-size: 18px; font-weight: bold; border: none;")
        right_layout.addWidget(list_title)

        hint_label = QLabel("长按条目弹出菜单")
        hint_label.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        right_layout.addWidget(hint_label)

        self.student_list = QListWidget()
        self.student_list.setObjectName("studentList")
        self.student_list.setAlternatingRowColors(True)
        self.student_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.student_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.student_list.setStyleSheet("""
            QListWidget#studentList {
                border: 1px solid rgba(0,0,0,0.06);
                border-radius: 12px;
                padding: 6px;
                font-size: 18px;
                outline: none;
            }
            QListWidget#studentList::item {
                padding: 12px 16px;
                border-radius: 10px;
                min-height: 50px;
            }
            QListWidget#studentList::item:hover {
                background: rgba(0,0,0,0.04);
            }
            QListWidget#studentList::item:selected {
                background: rgba(99,102,241,0.12);
                color: inherit;
            }
            QListWidget#studentList::item:pressed {
                background: rgba(99,102,241,0.22);
            }
        """)

        # ── 长按检测 ──
        self.student_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.student_list.customContextMenuRequested.connect(self._on_context_menu)
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(600)
        self._long_press_timer.timeout.connect(self._on_long_press)
        self._long_press_pending: QPoint | None = None

        def on_mouse_press(event):
            self._long_press_pending = event.pos()
            self._long_press_timer.start()

        def on_mouse_release(event):
            self._long_press_timer.stop()
            self._long_press_pending = None

        def on_mouse_move(event):
            if self._long_press_pending is not None:
                delta = (event.pos() - self._long_press_pending).manhattanLength()
                if delta > 10:
                    self._long_press_timer.stop()
                    self._long_press_pending = None

        self._orig_press = on_mouse_press
        self._orig_release = on_mouse_release
        self._orig_move = on_mouse_move
        self.student_list.viewport().installEventFilter(self)

        right_layout.addWidget(self.student_list, stretch=1)
        root.addWidget(right)

        self._apply_theme()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.student_list.viewport():
            if event.type() == event.Type.MouseButtonPress:
                self._orig_press(event)
            elif event.type() == event.Type.MouseButtonRelease:
                self._orig_release(event)
            elif event.type() == event.Type.MouseMove:
                self._orig_move(event)
        return super().eventFilter(obj, event)

    def _on_long_press(self) -> None:
        """长按弹出菜单。"""
        if self._long_press_pending is not None:
            item = self.student_list.itemAt(self._long_press_pending)
            if item:
                self.student_list.setCurrentItem(item)
                self._show_context_menu(self._long_press_pending)

    # ═══════════════════════════════════════════════════════════
    # 主题适配
    # ═══════════════════════════════════════════════════════════

    def _apply_theme(self) -> None:
        dark = isDarkTheme()
        if dark:
            hex_color = "#00D4FF"
            card_bg = "rgba(255,255,255,0.04)"
            card_border = "rgba(255,255,255,0.08)"
            panel_bg = "rgba(255,255,255,0.02)"
            panel_border = "rgba(255,255,255,0.06)"
            item_hover = "rgba(255,255,255,0.05)"
            item_selected = "rgba(0,212,255,0.15)"
            list_border = "rgba(255,255,255,0.08)"
            list_bg = "transparent"
            glow_color = QColor(0, 212, 255, 200)
        else:
            hex_color = "#1E293B"
            card_bg = "rgba(0,0,0,0.02)"
            card_border = "rgba(0,0,0,0.08)"
            panel_bg = "rgba(0,0,0,0.02)"
            panel_border = "rgba(0,0,0,0.06)"
            item_hover = "rgba(0,0,0,0.04)"
            item_selected = "rgba(99,102,241,0.12)"
            list_border = "rgba(0,0,0,0.06)"
            list_bg = "transparent"
            glow_color = QColor(124, 58, 237, 200)

        self.name_label.setStyleSheet(
            f"color: {hex_color}; font-weight: 900; border: none; background: transparent;"
        )

        name_card = self.findChild(QFrame, "pickerNameCard")
        if name_card:
            name_card.setStyleSheet(f"""
                QFrame#pickerNameCard {{
                    background: {card_bg};
                    border: 2px dashed {card_border};
                    border-radius: 28px;
                }}
            """)

        panel = self.findChild(QFrame, "pickerListPanel")
        if panel:
            panel.setStyleSheet(f"""
                QFrame#pickerListPanel {{
                    background: {panel_bg};
                    border-left: 1px solid {panel_border};
                }}
            """)

        self.student_list.setStyleSheet(f"""
            QListWidget#studentList {{
                border: 1px solid {list_border};
                border-radius: 12px;
                padding: 6px;
                font-size: 18px;
                outline: none;
                background: {list_bg};
            }}
            QListWidget#studentList::item {{
                padding: 12px 16px;
                border-radius: 10px;
                min-height: 50px;
            }}
            QListWidget#studentList::item:hover {{
                background: {item_hover};
            }}
            QListWidget#studentList::item:selected {{
                background: {item_selected};
                color: inherit;
            }}
            QListWidget#studentList::item:pressed {{
                background: rgba(99,102,241,0.25);
            }}
        """)

        self.draw_btn.set_glow_color(glow_color)
        self.banner.apply_theme(dark)

    def refresh_theme(self) -> None:
        self._apply_theme()

    # ═══════════════════════════════════════════════════════════
    # 数据
    # ═══════════════════════════════════════════════════════════

    def _load_classes(self) -> None:
        rows = db.fetch_all("SELECT id, name FROM classes ORDER BY id")
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        for row in rows:
            self.class_combo.addItem(row["name"], row["id"])
        self.class_combo.blockSignals(False)

    def _active_class_id(self) -> int:
        return self.class_combo.currentData() or 1

    def _load_students(self) -> list[dict]:
        cid = self._active_class_id()
        return db.fetch_all(
            "SELECT id, class_id, name, called_count, points FROM students WHERE class_id=? ORDER BY id",
            (cid,),
        )

    def _build_pool(self) -> list[dict]:
        all_s = self._all_students
        if not self.exclude_switch.isChecked():
            return list(all_s)
        remaining = [s for s in all_s if s["called_count"] == 0]
        if not remaining and all_s:
            # 全员已点 → 自动重置（静默）
            cid = self._active_class_id()
            db.execute("UPDATE students SET called_count=0 WHERE class_id=?", (cid,))
            self._all_students = self._load_students()
            return list(self._all_students)
        return remaining

    def _refresh_list(self) -> None:
        self._all_students = self._load_students()
        self._pool = self._build_pool()

        self.student_list.clear()
        total = len(self._all_students)
        called_count = sum(1 for s in self._all_students if s["called_count"] > 0)
        remaining = total - called_count

        for s in self._all_students:
            name = s["name"]
            suffix = f"  ✓×{s['called_count']}" if s["called_count"] > 0 else ""
            item = QListWidgetItem(f"{name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, s["called_count"])
            # 确保最小高度 50px
            sh = item.sizeHint()
            if sh.height() < 50:
                sh.setHeight(50)
            item.setSizeHint(sh)
            if s["called_count"] > 0:
                item.setForeground(QColor("#94a3b8"))
            self.student_list.addItem(item)

        self.remaining_label.setText(f"剩余 {max(remaining, 0)} 人")
        self._check_pool_empty()

    def _on_class_changed(self) -> None:
        if self._state != PickerState.IDLE:
            self._reset_state()
        self._refresh_list()

    def _on_student_list_changed(self) -> None:
        """名单变动信号 → 安静刷新名单"""
        self._load_classes()
        if self._state != PickerState.IDLE:
            self._reset_state()
        self._refresh_list()

    def _check_pool_empty(self) -> None:
        """名单为空时禁用点名按钮，显示提示"""
        empty = len(self._pool) == 0
        self.draw_btn.setEnabled(not empty)
        self._empty_hint.setVisible(empty)
        if empty:
            self.name_label.setText("暂无学生")

    # ═══════════════════════════════════════════════════════════
    # 点名核心
    # ═══════════════════════════════════════════════════════════

    def _on_draw_triggered(self) -> None:
        """按钮 released 触发。"""
        if self._state == PickerState.IDLE:
            self._start_scroll()
        elif self._state == PickerState.SCROLLING:
            self._enter_deceleration()
        elif self._state == PickerState.DECELERATING:
            self._force_stop()
        elif self._state == PickerState.STOPPED:
            self._reset_state()

    def _start_scroll(self) -> None:
        if not self._pool:
            # 无可用学生弹窗
            QMessageBox.warning(self, "无学生", "当前班级没有可抽选的学生。")
            return

        self._state = PickerState.SCROLLING
        self._tick_count = 0
        self._current_interval = self.SCROLL_INTERVAL
        self._picked = None

        self.draw_btn.setText("停")
        self.class_combo.setEnabled(False)
        self.exclude_switch.setEnabled(False)

        # 字号设为 100pt
        self.name_label.setFont(QFont("Microsoft YaHei", 100, QFont.Weight.Black))
        self._tick_timer.start(self.SCROLL_INTERVAL)

    def _on_tick(self) -> None:
        if self._state == PickerState.SCROLLING:
            self._tick_scrolling()
        elif self._state == PickerState.DECELERATING:
            self._tick_decelerating()

    def _tick_scrolling(self) -> None:
        if not self._pool:
            return
        self._tick_count += 1
        student = random.choice(self._pool)
        self.name_label.setText(student["name"])

        elapsed = self._tick_count * self.SCROLL_INTERVAL
        if elapsed >= self.SCROLL_DURATION:
            self._enter_deceleration()

    def _enter_deceleration(self) -> None:
        self._state = PickerState.DECELERATING
        self._tick_count = 0
        self._current_interval = self.SCROLL_INTERVAL
        self._tick_timer.start(self._current_interval)

    def _tick_decelerating(self) -> None:
        if not self._pool:
            return
        self._tick_count += 1
        student = random.choice(self._pool)
        self.name_label.setText(student["name"])

        self._current_interval = min(
            self.SCROLL_INTERVAL + self._tick_count * self.DECEL_STEP,
            self.DECEL_MAX_INTERVAL,
        )
        self._tick_timer.setInterval(self._current_interval)

        if self._current_interval >= self.DECEL_MAX_INTERVAL or self._tick_count >= 16:
            self._force_stop()

    def _force_stop(self) -> None:
        self._tick_timer.stop()
        self._state = PickerState.STOPPED

        if not self._pool:
            self._reset_state()
            return

        self._picked = random.choice(self._pool)
        self.name_label.setText(self._picked["name"])

        # 恢复字号 80pt
        self.name_label.setFont(QFont("Microsoft YaHei", 80, QFont.Weight.Black))

        # ── 跳动两下动画 ──
        self._bounce_label()

        # 写入数据库
        self._record_pick()

        self.draw_btn.setText("抽")
        self.class_combo.setEnabled(True)
        self.exclude_switch.setEnabled(True)

        # 刷新列表 + 底部横幅
        self._refresh_list()
        times = self._picked["called_count"] + 1
        self.banner.show_message(self._picked["name"], times)

    def _bounce_label(self) -> None:
        """姓名定格后放大并跳动两下。"""
        font = QFont("Microsoft YaHei", 80, QFont.Weight.Black)
        self.name_label.setFont(font)

        # 使用 scale 动画（QPropertyAnimation 无法直接动画 font size）
        anim = QPropertyAnimation(self.name_label, b"geometry")
        base = self.name_label.geometry()
        cx, cy, w, h = base.x(), base.y(), base.width(), base.height()

        anim.setDuration(600)
        anim.setKeyValueAt(0.0, base)
        # 第一跳
        zoom1 = base.__class__(cx - 10, cy - 8, w + 20, h + 16)
        anim.setKeyValueAt(0.25, zoom1)
        anim.setKeyValueAt(0.5, base)
        # 第二跳
        anim.setKeyValueAt(0.75, zoom1)
        anim.setKeyValueAt(1.0, base)
        anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        anim.start()

    def _record_pick(self) -> None:
        if not self._picked:
            return
        sid = self._picked["id"]
        cid = self._picked.get("class_id", self._active_class_id())
        db.execute(
            "UPDATE students SET called_count = called_count + 1 WHERE id=?",
            (sid,),
        )
        db.execute(
            "INSERT INTO call_records (student_id, class_id, called_at) VALUES (?, ?, ?)",
            (sid, cid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

    def _reset_state(self) -> None:
        self._tick_timer.stop()
        self._state = PickerState.IDLE
        self._picked = None
        self.draw_btn.setText("抽")
        self.name_label.setText("准备好了吗？")
        self.name_label.setFont(QFont("Microsoft YaHei", 64, QFont.Weight.Black))
        self.class_combo.setEnabled(True)
        self.exclude_switch.setEnabled(True)

    # ═══════════════════════════════════════════════════════════
    # 右键菜单 / 长按菜单
    # ═══════════════════════════════════════════════════════════

    def _on_context_menu(self, pos) -> None:
        item = self.student_list.itemAt(pos)
        if not item:
            return
        self.student_list.setCurrentItem(item)
        self._show_context_menu(pos)

    def _show_context_menu(self, pos) -> None:
        item = self.student_list.currentItem()
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        times = item.data(Qt.ItemDataRole.UserRole + 1) or 0
        name = item.text().replace(f"  ✓×{times}", "").strip()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { font-size: 18px; padding: 8px; }
            QMenu::item { padding: 14px 32px 14px 20px; min-height: 48px; }
        """)

        mark = menu.addAction("✅ 标记已点")
        mark_plus = menu.addAction("🔁 标记已点 +1")
        menu.addSeparator()
        reset = menu.addAction("🔄 重置该生")
        reset_all = menu.addAction("🔄 重置全班")

        action = menu.exec(self.student_list.mapToGlobal(pos))
        if action == mark:
            db.execute("UPDATE students SET called_count=1 WHERE id=?", (sid,))
        elif action == mark_plus:
            new_count = times + 1
            db.execute("UPDATE students SET called_count=? WHERE id=?", (new_count, sid))
        elif action == reset:
            db.execute("UPDATE students SET called_count=0 WHERE id=?", (sid,))
        elif action == reset_all:
            cid = self._active_class_id()
            db.execute("UPDATE students SET called_count=0 WHERE class_id=?", (cid,))

        if action:
            self._refresh_list()

    # ═══════════════════════════════════════════════════════════
    # 键盘空格
    # ═══════════════════════════════════════════════════════════

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._on_draw_triggered()
            return
        super().keyPressEvent(event)
