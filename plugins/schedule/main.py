"""
📅 电子课程表 — 可编辑的周课程表插件

支持：
  - 周一至周五，每天 6 节课（可配置）
  - 课程名、教师、教室、颜色
  - JSON 持久化存储
  - 当前时间对应课程自动高亮
  - 添加/编辑/删除课程
  - 导出/导入课程表
"""
from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QLineEdit,
    QFormLayout, QColorDialog, QComboBox, QMessageBox, QFileDialog,
    QSizePolicy, QHeaderView, QMenu,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QBrush

from app.plugins.base import OpenClassPlugin

# 时间段定义（8:00 开始，每节课 45 分钟 + 10 分钟休息）
PERIOD_TIMES = [
    ("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45"),
    ("10:55", "11:40"), ("14:00", "14:45"), ("14:55", "15:40"),
]

DAYS = ["周一", "周二", "周三", "周四", "周五"]

# 默认配色
SUBJECT_COLORS = [
    "#6366f1", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
    "#06b6d4", "#ec4899", "#14b8a6",
]

import sys as _sys

DATA_FILE: Path = Path("schedule_data.json")  # default fallback

def _get_data_file() -> Path:
    """返回课程表数据文件的路径（打包后写入 exe 同级目录）"""
    try:
        _ = _sys._MEIPASS  # type: ignore[attr-defined]
        return Path(_sys.executable).parent / "schedule_data.json"
    except Exception:
        return Path(__file__).resolve().parent / "schedule_data.json"

DATA_FILE = _get_data_file()


def _load_data() -> dict:
    """加载课程表数据"""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_data(data: dict) -> None:
    """保存课程表数据"""
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class _CourseEditDialog(QDialog):
    """课程编辑弹窗"""

    def __init__(self, course: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑课程" if course else "添加课程")
        self.setMinimumSize(400, 300)
        self.setStyleSheet("QDialog { background: #1e1e2e; border-radius: 12px; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit(course.get("name", "") if course else "")
        self._name_input.setMinimumHeight(40)
        self._name_input.setStyleSheet("QLineEdit { font-size: 15px; padding: 6px 12px; border-radius: 8px; }")
        form.addRow("课程名称:", self._name_input)

        self._teacher_input = QLineEdit(course.get("teacher", "") if course else "")
        self._teacher_input.setMinimumHeight(40)
        self._teacher_input.setStyleSheet("QLineEdit { font-size: 15px; padding: 6px 12px; border-radius: 8px; }")
        form.addRow("教师:", self._teacher_input)

        self._room_input = QLineEdit(course.get("room", "") if course else "")
        self._room_input.setMinimumHeight(40)
        self._room_input.setStyleSheet("QLineEdit { font-size: 15px; padding: 6px 12px; border-radius: 8px; }")
        form.addRow("教室:", self._room_input)

        self._color = course.get("color", SUBJECT_COLORS[0]) if course else SUBJECT_COLORS[0]
        self._color_btn = QPushButton("  " + self._color)
        self._color_btn.setMinimumHeight(40)
        self._color_btn.clicked.connect(self._pick_color)
        form.addRow("颜色:", self._color_btn)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.setMinimumHeight(48)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        ok = QPushButton("确定")
        ok.setMinimumHeight(48)
        ok.setStyleSheet("QPushButton { background: #6366f1; color: #fff; font-weight: bold; }")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color))
        if color.isValid():
            self._color = color.name()
            self._color_btn.setText("  " + self._color)

    def get_course(self) -> dict:
        return {
            "name": self._name_input.text().strip(),
            "teacher": self._teacher_input.text().strip(),
            "room": self._room_input.text().strip(),
            "color": self._color,
        }


class ScheduleWidget(QWidget):
    """课程表主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scheduleWidget")
        self.setMinimumSize(700, 550)
        self._data: dict = {}

        self._build_ui()
        self._load_and_display()
        # 每分钟刷新高亮
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._highlight_current)
        self._timer.start(30000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 顶部工具栏
        toolbar = QHBoxLayout()

        title = QLabel("📅 电子课程表")
        title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        export_btn = QPushButton("导出")
        export_btn.setMinimumHeight(44)
        export_btn.setStyleSheet("""
            QPushButton { font-size: 14px; padding: 8px 18px;
                background: rgba(99,102,241,0.08); color: #6366f1;
                border: 1px solid rgba(99,102,241,0.15); border-radius: 8px; }
            QPushButton:hover { background: rgba(99,102,241,0.15); }
        """)
        export_btn.clicked.connect(self._export_data)
        toolbar.addWidget(export_btn)

        import_btn = QPushButton("导入")
        import_btn.setMinimumHeight(44)
        import_btn.setStyleSheet("""
            QPushButton { font-size: 14px; padding: 8px 18px;
                background: rgba(34,197,94,0.08); color: #22c55e;
                border: 1px solid rgba(34,197,94,0.15); border-radius: 8px; }
            QPushButton:hover { background: rgba(34,197,94,0.15); }
        """)
        import_btn.clicked.connect(self._import_data)
        toolbar.addWidget(import_btn)

        layout.addLayout(toolbar)

        # 课程表格
        self._table = QTableWidget()
        self._table.setRowCount(len(PERIOD_TIMES))
        self._table.setColumnCount(len(DAYS))
        self._table.setHorizontalHeaderLabels(DAYS)

        # 行头：时间段
        period_labels = [f"第{i+1}节\n{t[0]}-{t[1]}" for i, t in enumerate(PERIOD_TIMES)]
        self._table.setVerticalHeaderLabels(period_labels)

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setMinimumHeight(450)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        self._table.setStyleSheet("""
            QTableWidget { font-size: 13px; border: 1px solid #e2e8f0;
                border-radius: 10px; gridline-color: #f1f5f9; }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section { font-size: 14px; font-weight: bold;
                padding: 10px; border: 1px solid #e2e8f0; }
        """)
        layout.addWidget(self._table, stretch=1)

        # 底部操作提示
        hint = QLabel("右键单元格可添加/编辑/删除课程  |  课程数据自动保存")
        hint.setStyleSheet("color: #94a3b8; font-size: 13px; border: none;")
        layout.addWidget(hint)

    def _load_and_display(self) -> None:
        self._data = _load_data()
        self._refresh_table()

    def _refresh_table(self) -> None:
        """刷新整个表格"""
        self._table.clearContents()
        for row in range(len(PERIOD_TIMES)):
            for col in range(len(DAYS)):
                key = f"{col}_{row}"
                course = self._data.get(key)
                item = QTableWidgetItem()
                if course:
                    item.setText(f"{course['name']}\n{course.get('teacher','')}  {course.get('room','')}")
                    color = course.get("color", SUBJECT_COLORS[0])
                    item.setBackground(QBrush(QColor(color)))
                    item.setForeground(QBrush(QColor("#ffffff")))
                    item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
                self._table.setItem(row, col, item)
        self._highlight_current()

    def _highlight_current(self) -> None:
        """高亮当前时间对应的课程"""
        now = datetime.now()
        current_weekday = now.weekday()  # 0=周一, ..., 4=周五
        current_time = now.time()

        if current_weekday > 4:  # 周末
            return

        col = current_weekday

        for row, (start_str, end_str) in enumerate(PERIOD_TIMES):
            s_h, s_m = map(int, start_str.split(":"))
            e_h, e_m = map(int, end_str.split(":"))
            start = time(s_h, s_m)
            end = time(e_h, e_m)

            item = self._table.item(row, col)
            if item is None:
                continue

            if start <= current_time <= end:
                # 当前课程 — 加粗边框
                item.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
                # 闪烁提示：已有背景色保持，增加边框
            else:
                if self._data.get(f"{col}_{row}"):
                    item.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
                else:
                    item.setFont(QFont("Microsoft YaHei", 11))

    def _on_context_menu(self, pos) -> None:
        cell = self._table.itemAt(pos)
        row = self._table.rowAt(pos.y())
        col = self._table.columnAt(pos.x())
        if row < 0 or col < 0:
            return
        key = f"{col}_{row}"

        menu = QMenu(self)
        existing = self._data.get(key)

        if existing:
            edit_action = menu.addAction("✏️ 编辑课程")
            del_action = menu.addAction("🗑 删除课程")
            menu.addSeparator()

        add_action = menu.addAction("➕ 添加课程")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if existing and action == edit_action:
            self._edit_course(col, row, key, existing)
        elif existing and action == del_action:
            del self._data[key]
            _save_data(self._data)
            self._refresh_table()
        elif action == add_action:
            self._edit_course(col, row, key, None)

    def _edit_course(self, col: int, row: int, key: str, course: dict | None) -> None:
        dlg = _CourseEditDialog(course, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._data[key] = dlg.get_course()
            _save_data(self._data)
            self._refresh_table()

    def _export_data(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出课程表", "schedule_backup.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "导出成功", f"课程表已导出至:\n{path}")

    def _import_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入课程表", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                self._data.update(imported)
                _save_data(self._data)
                self._refresh_table()
                QMessageBox.information(self, "导入成功", f"已导入 {len(imported)} 条课程数据")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", str(e))


class _SchedulePlugin(OpenClassPlugin):
    plugin_id = "schedule"
    plugin_name = "电子课程表"
    plugin_version = "1.0.0"
    plugin_description = "可编辑的周课程表，自动高亮当前课程"
    plugin_icon = "📅"
    plugin_author = "OpenClass Team"
    plugin_category = "课堂工具"

    def create_widget(self) -> QWidget:
        return ScheduleWidget()


plugin_instance = _SchedulePlugin


# ── PluginWidget — 供新版插件系统 (PluggableManager) 加载 ──
class PluginWidget(QWidget):
    """插件入口 Widget，直接继承 QWidget。"""
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = ScheduleWidget()
        layout.addWidget(self._inner)
