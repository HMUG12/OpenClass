"""
📅 电子课程表 — 桌面悬浮窗口

特性：
  - 无边框、半透明磨砂（Acrylic 效果）、圆角
  - 默认右下角贴边，可拖拽移动
  - 置顶显示（WindowStaysOnTopHint）
  - 收起/展开按钮，收起后仅显示标题栏（30px 高）
  - 当前时间课程高亮闪烁
  - 数据 JSON 持久化，复用已有 schedule_data.json
  - 单例模式：全局仅一个悬浮窗实例
"""
from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QLineEdit, QFormLayout, QColorDialog,
    QMessageBox, QApplication, QSizePolicy, QScrollArea,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import (
    QFont, QColor, QMouseEvent, QPainter, QBrush, QPen,
    QPaintEvent, QLinearGradient,
)

# ── 数据路径（与旧课程表共享） ──
import sys as _sys

def _get_data_file() -> Path:
    try:
        _ = _sys._MEIPASS  # type: ignore[attr-defined]
        return Path(_sys.executable).parent / "schedule_data.json"
    except Exception:
        return Path(__file__).resolve().parent.parent.parent.parent / "plugins" / "schedule" / "schedule_data.json"

DATA_FILE = _get_data_file()

# ── 时间段 ──
PERIOD_TIMES = [
    ("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45"),
    ("10:55", "11:40"), ("14:00", "14:45"), ("14:55", "15:40"),
]
DAYS = ["周一", "周二", "周三", "周四", "周五"]

SUBJECT_COLORS = [
    "#6366f1", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
    "#06b6d4", "#ec4899", "#14b8a6",
]


def load_schedule_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_schedule_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# 编辑对话框
# ═══════════════════════════════════════════════════════════════

class _ScheduleEditDialog(QDialog):
    """独立编辑对话框 — 表格形式增删改查"""

    data_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑课程表")
        self.setMinimumSize(700, 500)
        self.resize(780, 580)
        self.setStyleSheet("QDialog { background: #1e1e2e; border-radius: 14px; }")
        self._data = load_schedule_data()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("📅 编辑课程表")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0; border: none;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        self._form_layout = QFormLayout(container)
        self._form_layout.setSpacing(8)

        self._rows: list[dict] = []

        for row in range(len(PERIOD_TIMES)):
            for col, day_name in enumerate(DAYS):
                key = f"{col}_{row}"
                course = self._data.get(key, {})
                row_widget = QHBoxLayout()
                row_widget.setSpacing(6)

                label = QLabel(f"{day_name} 第{row+1}节")
                label.setStyleSheet("color: #94a3b8; font-size: 13px; border: none; min-width: 90px;")
                row_widget.addWidget(label)

                name_edit = QLineEdit(course.get("name", ""))
                name_edit.setPlaceholderText("课程名")
                name_edit.setMinimumHeight(36)
                name_edit.setStyleSheet("QLineEdit { font-size: 13px; padding: 4px 8px; border-radius: 6px; border: 1px solid #374151; background: rgba(255,255,255,0.04); color: #e0e0e0; }")
                row_widget.addWidget(name_edit, stretch=2)

                teacher_edit = QLineEdit(course.get("teacher", ""))
                teacher_edit.setPlaceholderText("教师")
                teacher_edit.setMinimumHeight(36)
                teacher_edit.setStyleSheet(name_edit.styleSheet())
                row_widget.addWidget(teacher_edit, stretch=1)

                room_edit = QLineEdit(course.get("room", ""))
                room_edit.setPlaceholderText("教室")
                room_edit.setMinimumHeight(36)
                room_edit.setStyleSheet(name_edit.styleSheet())
                row_widget.addWidget(room_edit, stretch=1)

                color = course.get("color", SUBJECT_COLORS[(row * len(DAYS) + col) % len(SUBJECT_COLORS)])
                color_btn = QPushButton("  ")
                color_btn.setFixedSize(36, 36)
                color_btn.setStyleSheet(f"background: {color}; border: 1px solid #555; border-radius: 6px;")
                color_btn.clicked.connect(lambda checked, b=color_btn, k=key: self._pick_color(b, k))
                row_widget.addWidget(color_btn)

                self._form_layout.addRow(row_widget)
                self._rows.append({
                    "key": key,
                    "name": name_edit,
                    "teacher": teacher_edit,
                    "room": room_edit,
                    "color": color_btn,
                    "default_color": color,
                })

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(48)
        cancel_btn.setStyleSheet("""
            QPushButton { font-size: 15px; background: rgba(128,128,128,0.08); color: #aaa; border-radius: 10px; padding: 8px 24px; }
            QPushButton:hover { background: rgba(128,128,128,0.18); }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.setMinimumHeight(48)
        save_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; padding: 8px 28px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _pick_color(self, btn: QPushButton, key: str) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            btn.setStyleSheet(f"background: {color.name()}; border: 1px solid #555; border-radius: 6px;")
            for r in self._rows:
                if r["key"] == key:
                    r["default_color"] = color.name()
                    break

    def _save(self) -> None:
        new_data: dict = {}
        for row_info in self._rows:
            name = row_info["name"].text().strip()
            teacher = row_info["teacher"].text().strip()
            room = row_info["room"].text().strip()
            if name or teacher or room:
                new_data[row_info["key"]] = {
                    "name": name,
                    "teacher": teacher,
                    "room": room,
                    "color": row_info["default_color"],
                }
        save_schedule_data(new_data)
        self._data = new_data
        self.data_updated.emit()
        QMessageBox.information(self, "保存成功", "课程表数据已保存")
        self.accept()


# ═══════════════════════════════════════════════════════════════
# 课程卡片 — 悬浮窗内显示
# ═══════════════════════════════════════════════════════════════

class _CourseCard(QFrame):
    """单门课程卡片 — 右侧彩色竖条 + 课程名/教师/教室/时间"""

    def __init__(self, name: str, teacher: str, room: str, time_str: str, color: str,
                 is_active: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("scheduleCard")
        self._color = color
        self._is_active = is_active

        self.setMinimumHeight(56)
        self.setStyleSheet(f"""
            QFrame#scheduleCard {{
                background: rgba(255,255,255,0.06);
                border: {('2px solid ' + color) if is_active else '1px solid rgba(255,255,255,0.06)'};
                border-radius: 10px;
            }}
        """)

        hl = QHBoxLayout(self)
        hl.setContentsMargins(8, 8, 12, 8)
        hl.setSpacing(10)

        # 颜色竖条
        bar = QFrame()
        bar.setFixedWidth(5)
        bar.setStyleSheet(f"background: {color}; border-radius: 3px; border: none;")
        hl.addWidget(bar)

        # 内容
        content = QVBoxLayout()
        content.setSpacing(2)

        top_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: #e0e0e0; border: none;")
        top_row.addWidget(name_label)
        top_row.addStretch()
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
        top_row.addWidget(time_label)
        content.addLayout(top_row)

        sub_row = QHBoxLayout()
        if teacher:
            t = QLabel(f"👤 {teacher}")
            t.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
            sub_row.addWidget(t)
        if room:
            r = QLabel(f"🏫 {room}")
            r.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
            sub_row.addWidget(r)
        sub_row.addStretch()
        content.addLayout(sub_row)

        hl.addLayout(content, stretch=1)


# ═══════════════════════════════════════════════════════════════
# 悬浮窗主体
# ═══════════════════════════════════════════════════════════════

class ScheduleFloatWindow(QWidget):
    """桌面课程表悬浮窗 — 单例"""

    _instance: ScheduleFloatWindow | None = None

    @classmethod
    def get_or_create(cls) -> ScheduleFloatWindow:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def close_instance(cls) -> None:
        if cls._instance:
            cls._instance.close()
            cls._instance = None

    def __init__(self):
        if ScheduleFloatWindow._instance is not None:
            raise RuntimeError("ScheduleFloatWindow 是单例，请使用 get_or_create()")
        super().__init__()
        self.setWindowTitle("课程表")
        self.setObjectName("scheduleFloatWindow")

        # ── 窗口标志 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(420, 520)
        self._collapsed = False
        self._drag_pos: QPoint | None = None

        self._data = load_schedule_data()
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(800)
        self._flash_timer.timeout.connect(self._update)
        self._flash_timer.start()

        self._build_ui()
        self._position_bottom_right()

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 20, geo.bottom() - self.height() - 20)

    def _build_ui(self) -> None:
        # ── 阴影效果 ──
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 内容容器（磨砂背景 + 圆角） ──
        self._container = QFrame()
        self._container.setObjectName("floatContainer")
        self._container.setStyleSheet("""
            QFrame#floatContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30,30,46,0.92), stop:1 rgba(15,15,30,0.92));
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }
        """)
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # ── 标题栏（可拖拽） ──
        self._title_bar = QFrame()
        self._title_bar.setObjectName("titleBar")
        self._title_bar.setFixedHeight(40)
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        self._title_bar.setStyleSheet("""
            QFrame#titleBar {
                background: transparent;
                border-top-left-radius: 16px; border-top-right-radius: 16px;
            }
        """)
        tb = QHBoxLayout(self._title_bar)
        tb.setContentsMargins(16, 0, 8, 0)

        title_icon = QLabel("📅")
        title_icon.setStyleSheet("font-size: 18px; border: none;")
        tb.addWidget(title_icon)

        self._title_label = QLabel("电子课程表")
        self._title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        self._title_label.setStyleSheet("color: #e0e0e0; border: none;")
        tb.addWidget(self._title_label)
        tb.addStretch()

        self._collapse_btn = QPushButton("—")
        self._collapse_btn.setFixedSize(32, 32)
        self._collapse_btn.setToolTip("收起/展开")
        self._collapse_btn.setStyleSheet("""
            QPushButton { font-size: 16px; font-weight: bold; color: #94a3b8;
                background: transparent; border: none; border-radius: 8px; }
            QPushButton:hover { background: rgba(255,255,255,0.08); color: #e0e0e0; }
        """)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        tb.addWidget(self._collapse_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("关闭悬浮窗")
        close_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; color: #94a3b8;
                background: transparent; border: none; border-radius: 8px; }
            QPushButton:hover { background: rgba(239,68,68,0.20); color: #ef4444; }
        """)
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        cl.addWidget(self._title_bar)

        # ── 内容区 ──
        self._content_area = QWidget()
        ca = QVBoxLayout(self._content_area)
        ca.setContentsMargins(16, 12, 16, 12)
        ca.setSpacing(8)

        # 日期标题
        now = datetime.now()
        weekday = now.weekday()
        weekday_name = DAYS[weekday] if weekday < 5 else "周末"
        date_str = now.strftime("%Y年%m月%d日")
        date_header = QLabel(f"{date_str}  {weekday_name}")
        date_header.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        date_header.setStyleSheet("color: #e0e0e0; border: none;")
        ca.addWidget(date_header)

        # 课程卡片滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)
        scroll.setWidget(self._cards_container)
        ca.addWidget(scroll, stretch=1)

        # 无课提示
        self._empty_hint = QLabel("今天没有课程安排\n点击「编辑」添加课程")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setStyleSheet("color: #64748b; font-size: 14px; padding: 40px; border: none;")
        self._empty_hint.setVisible(False)
        ca.addWidget(self._empty_hint)

        # 底部按钮栏
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        edit_btn = QPushButton("✏️ 编辑课程表")
        edit_btn.setMinimumHeight(44)
        edit_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: rgba(99,102,241,0.15);
                color: #a5b4fc; border: 1px solid rgba(99,102,241,0.25); border-radius: 10px; }
            QPushButton:hover { background: rgba(99,102,241,0.25); color: #c7d2fe; }
        """)
        edit_btn.clicked.connect(self._open_editor)
        btn_bar.addWidget(edit_btn, stretch=1)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setMinimumHeight(44)
        refresh_btn.setStyleSheet("""
            QPushButton { font-size: 13px; background: rgba(255,255,255,0.04); color: #94a3b8;
                border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { background: rgba(255,255,255,0.08); }
        """)
        refresh_btn.clicked.connect(self._refresh)
        btn_bar.addWidget(refresh_btn)
        ca.addLayout(btn_bar)

        cl.addWidget(self._content_area)
        root_layout.addWidget(self._container)

        self._refresh()

    # ── 拖拽 ──

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 只在标题栏区域拖拽
            if self._title_bar.geometry().contains(event.position().toPoint()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── 收起/展开 ──

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content_area.hide()
            self.setFixedSize(420, 40)
            self._collapse_btn.setText("□")
        else:
            self._content_area.show()
            self.setFixedSize(420, 520)
            self._collapse_btn.setText("—")

    # ── 刷新课程内容 ──

    def _refresh(self) -> None:
        self._data = load_schedule_data()
        # 清空旧卡片
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        now = datetime.now()
        weekday = now.weekday()
        current_time = now.time()

        if weekday > 4:
            self._empty_hint.setText("周末愉快！🎉")
            self._empty_hint.setVisible(True)
            self._cards_layout.addStretch()
            return

        has_courses = False
        for row, (start_str, end_str) in enumerate(PERIOD_TIMES):
            key = f"{weekday}_{row}"
            course = self._data.get(key)
            if not course:
                continue
            has_courses = True

            s_h, s_m = map(int, start_str.split(":"))
            e_h, e_m = map(int, end_str.split(":"))
            start = time(s_h, s_m)
            end = time(e_h, e_m)
            is_active = start <= current_time <= end

            time_str = f"{start_str} - {end_str}"
            card = _CourseCard(
                course.get("name", ""),
                course.get("teacher", ""),
                course.get("room", ""),
                time_str,
                course.get("color", SUBJECT_COLORS[row % len(SUBJECT_COLORS)]),
                is_active=is_active,
            )
            self._cards_layout.addWidget(card)

        if not has_courses:
            self._empty_hint.setText(f"{DAYS[weekday]}暂无课程安排")
            self._empty_hint.setVisible(True)
        else:
            self._empty_hint.setVisible(False)

        self._cards_layout.addStretch()

        # 更新日期标题
        date_str = now.strftime("%Y年%m月%d日")
        if hasattr(self, '_header_date'):
            weekday_name = DAYS[weekday] if weekday < 5 else "周末"

    # ── 打开编辑器 ──

    def _open_editor(self) -> None:
        dlg = _ScheduleEditDialog(None)
        dlg.data_updated.connect(self._refresh)
        dlg.exec()

    def closeEvent(self, event) -> None:
        self._flash_timer.stop()
        ScheduleFloatWindow._instance = None
        super().closeEvent(event)
