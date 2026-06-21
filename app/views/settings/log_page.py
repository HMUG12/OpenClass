"""
📋 日志管理子页面 — QTextEdit 实时日志 + 筛选 + 导出 + 清空

- 自定义 logging.Handler 将日志流重定向到 QTextEdit
- RotatingFileHandler 10MB 自动轮转
- 14pt / 1.5 倍行距，双击复制，手指滑动
- 级别筛选下拉框 + 导出 .txt + 二次确认清空
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler as _RotatingFileHandler

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat


# ═══════════════════════════════════════════════════════════════
# 日志信号桥接 — 线程安全地将 log 记录抛到主线程
# ═══════════════════════════════════════════════════════════════

class _LogSignalEmitter(QObject):
    """从 logging.Handler 发射信号到 QTextEdit"""
    log_received = Signal(str, str, str)  # time_str, level, message


_emitter: _LogSignalEmitter | None = None


def get_log_emitter() -> _LogSignalEmitter:
    """获取全局单例 emitter，供 LogManagePage 连接"""
    global _emitter
    if _emitter is None:
        _emitter = _LogSignalEmitter()
    return _emitter


# ═══════════════════════════════════════════════════════════════
# logging.Handler → QTextEdit 桥接
# ═══════════════════════════════════════════════════════════════

class QTextEditLogHandler(logging.Handler):
    """自定义 Handler：格式化日志 → 通过信号发送到主线程 UI"""

    def __init__(self, level=logging.DEBUG):
        super().__init__(level)
        self._emitter = get_log_emitter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            t = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            msg = self.format(record)
            self._emitter.log_received.emit(t, record.levelname, msg)
        except Exception:
            self.handleError(record)


# ═══════════════════════════════════════════════════════════════
# 日志系统初始化 — 安装 RotatingFileHandler(10MB) + QTextEditHandler
# ═══════════════════════════════════════════════════════════════

def setup_logging(log_dir: Path | None = None) -> QTextEditLogHandler:
    """
    配置日志系统：
    - RotatingFileHandler: 10MB 自动轮转，保留 3 个备份
    - StreamHandler: 控制台输出
    - QTextEditLogHandler: UI 实时显示

    返回 ui_handler 供 LogManagePage 引用
    """
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 清除已有的 handlers（防止重复初始化）
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件输出 — 10MB 自动轮转
    file_handler = _RotatingFileHandler(
        log_dir / "openclass.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 控制台
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    root.addHandler(console)

    # UI 实时显示
    ui_handler = QTextEditLogHandler(level=logging.DEBUG)
    # 使用简洁格式（时间已在 signal 中带）
    ui_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(ui_handler)

    from app.utils.logger import logger
    logger.info("日志系统初始化完成")
    return ui_handler


# ═══════════════════════════════════════════════════════════════
# 日志管理 UI 页面
# ═══════════════════════════════════════════════════════════════

# 级别颜色映射
_LEVEL_COLORS = {
    "DEBUG":    "#94a3b8",
    "INFO":     "#22c55e",
    "WARNING":  "#f59e0b",
    "ERROR":    "#ef4444",
    "CRITICAL": "#dc2626",
}

_FILTER_LEVELS = {
    "全部":     logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
}


class LogManagePage(QWidget):
    """日志管理子页面 — 实时日志 + 筛选 + 导出 + 清空"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logManagePage")

        # 存储所有条目
        self._entries: list[tuple[str, str, str]] = []  # (time, level, message)
        self._current_filter = logging.DEBUG

        self._build_ui()
        self._connect_signals()

    # ═══════════════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(14)

        # ── 标题 ──
        title = QLabel("📋  日志管理")
        title.setStyleSheet("font-size: 22px; font-weight: bold; border: none;")
        layout.addWidget(title)

        desc = QLabel("查看应用运行日志，支持级别筛选、导出和清空。日志文件超过 10MB 自动轮转。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 16px; border: none;")
        layout.addWidget(desc)

        # ── 顶部工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(14)

        # 左侧：筛选下拉框
        toolbar.addWidget(QLabel("级别筛选:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(list(_FILTER_LEVELS.keys()))
        self._filter_combo.setCurrentIndex(0)
        self._filter_combo.setFixedWidth(120)
        self._filter_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid rgba(128,128,128,0.30);
                border-radius: 8px; padding: 6px 12px;
                font-size: 15px; min-height: 32px;
            }
            QComboBox QAbstractItemView { font-size: 15px; }
        """)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_combo)

        toolbar.addStretch()

        # 右侧：导出按钮
        export_btn = QPushButton("📥 导出日志")
        export_btn.setMinimumHeight(44)
        export_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: 600;
                background: rgba(99,102,241,0.15); color: #6366f1;
                border: 1px solid rgba(99,102,241,0.30); border-radius: 10px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: rgba(99,102,241,0.25); }
            QPushButton:pressed { background: rgba(99,102,241,0.35); }
        """)
        export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(export_btn)

        # 清除按钮
        clear_btn = QPushButton("🗑 清空日志")
        clear_btn.setMinimumHeight(44)
        clear_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: 600;
                background: rgba(239,68,68,0.12); color: #ef4444;
                border: 1px solid rgba(239,68,68,0.25); border-radius: 10px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: rgba(239,68,68,0.22); }
            QPushButton:pressed { background: rgba(239,68,68,0.32); }
        """)
        clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # ── 中央日志文本框 ──
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 14))
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(15, 15, 20, 0.90);
                color: #E4E4E7;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px 16px;
                line-height: 1.5;
                selection-background-color: rgba(99,102,241,0.40);
            }
            QScrollBar:vertical {
                background: transparent; width: 12px; margin: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15); border-radius: 6px; min-height: 40px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        # 触控：双击复制行内容
        self._text_edit.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self._text_edit.mouseDoubleClickEvent = self._on_double_click

        layout.addWidget(self._text_edit, stretch=1)

        # ── 底部状态栏 ──
        self._status_label = QLabel("日志条目: 0")
        self._status_label.setStyleSheet("color: #888; font-size: 14px; border: none;")
        layout.addWidget(self._status_label)

    # ═══════════════════════════════════════════════════════════
    # 信号绑定
    # ═══════════════════════════════════════════════════════════

    def _connect_signals(self) -> None:
        emitter = get_log_emitter()
        emitter.log_received.connect(self._on_log)

    # ═══════════════════════════════════════════════════════════
    # 日志接收
    # ═══════════════════════════════════════════════════════════

    def _on_log(self, time_str: str, level: str, message: str) -> None:
        self._entries.append((time_str, level, message))

        # 筛选级别
        min_level = _FILTER_LEVELS.get(self._filter_combo.currentText(), logging.DEBUG)
        level_value = getattr(logging, level, logging.DEBUG)
        if level_value < min_level:
            return

        color = _LEVEL_COLORS.get(level, "#E4E4E7")

        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # 灰色时间
        fmt_time = QTextCharFormat()
        fmt_time.setForeground(QColor("#64748b"))
        cursor.insertText(f"[{time_str}] ", fmt_time)

        # 彩色级别
        fmt_level = QTextCharFormat()
        fmt_level.setForeground(QColor(color))
        fmt_level.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"[{level}] ", fmt_level)

        # 消息内容
        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor("#D1D5DB"))
        cursor.insertText(f"{message}\n", fmt_msg)

        # 自动滚动到底部
        self._text_edit.setTextCursor(cursor)
        sb = self._text_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        self._update_status()

    # ═══════════════════════════════════════════════════════════
    # 级别筛选
    # ═══════════════════════════════════════════════════════════

    def _on_filter_changed(self, text: str) -> None:
        self._current_filter = _FILTER_LEVELS.get(text, logging.DEBUG)
        self._rebuild_display()

    def _rebuild_display(self) -> None:
        """根据当前筛选重建全部文本"""
        self._text_edit.clear()
        for time_str, level, message in self._entries:
            level_value = getattr(logging, level, logging.DEBUG)
            if level_value < self._current_filter:
                continue

            color = _LEVEL_COLORS.get(level, "#E4E4E7")
            cursor = self._text_edit.textCursor()

            fmt_time = QTextCharFormat()
            fmt_time.setForeground(QColor("#64748b"))
            cursor.insertText(f"[{time_str}] ", fmt_time)

            fmt_level = QTextCharFormat()
            fmt_level.setForeground(QColor(color))
            fmt_level.setFontWeight(QFont.Weight.Bold)
            cursor.insertText(f"[{level}] ", fmt_level)

            fmt_msg = QTextCharFormat()
            fmt_msg.setForeground(QColor("#D1D5DB"))
            cursor.insertText(f"{message}\n", fmt_msg)

        self._text_edit.setTextCursor(self._text_edit.textCursor())
        self._update_status()

    # ═══════════════════════════════════════════════════════════
    # 双击复制
    # ═══════════════════════════════════════════════════════════

    def _on_double_click(self, event) -> None:
        cursor = self._text_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        text = cursor.selectedText().strip()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)

    # ═══════════════════════════════════════════════════════════
    # 导出日志
    # ═══════════════════════════════════════════════════════════

    def _on_export(self) -> None:
        default_dir = str(Path.home() / "Desktop")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"OpenClass_日志_{ts}.txt"

        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志",
            str(Path(default_dir) / default_name),
            "文本文件 (*.txt);;所有文件 (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                for time_str, level, message in self._entries:
                    level_value = getattr(logging, level, logging.DEBUG)
                    if level_value < self._current_filter:
                        continue
                    f.write(f"[{time_str}] [{level}] {message}\n")
            QMessageBox.information(self, "导出成功", f"日志已保存到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"无法写入文件:\n{e}")

    # ═══════════════════════════════════════════════════════════
    # 清空日志
    # ═══════════════════════════════════════════════════════════

    def _on_clear(self) -> None:
        reply = QMessageBox.question(
            self, "清空日志",
            "确定要清空当前显示的日志内容吗？\n\n"
            "注意：仅清空界面展示，磁盘日志文件不受影响。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._entries.clear()
            self._text_edit.clear()
            self._update_status()

    # ═══════════════════════════════════════════════════════════
    # 状态
    # ═══════════════════════════════════════════════════════════

    def _update_status(self) -> None:
        visible = sum(
            1 for _, level, _ in self._entries
            if getattr(logging, level, logging.DEBUG) >= self._current_filter
        )
        self._status_label.setText(
            f"日志条目: {len(self._entries)}  显示: {visible}"
        )
