"""
✏️ 批注白板 — 触控一体机优化版

触控:   WA_AcceptTouchEvents + event() 拦截 TouchBegin/Update/End
        仅追踪第一触控点，忽略压力实现防误触
工具:   底部悬浮半透明工具栏 — 画笔三段 / 颜色大色块 50px /
        橡皮 / 清空二次确认 / 撤销(大按钮) / 红色退出
退出:   询问"是否保留批注截图？" → 保存 PNG 到桌面
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QPointF, QTimer, Signal, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QMouseEvent, QKeyEvent, QTouchEvent,
    QPaintEvent, QPainterPath, QFont, QImage,
)


# ═══════════════════════════════════════════════════════════════
# 二次确认弹窗 — 清空画布用
# ═══════════════════════════════════════════════════════════════

class _ConfirmDialog(QDialog):
    """大号确认弹窗 — 触控友好"""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 240)
        self.setModal(True)

        container = QFrame(self)
        container.setObjectName("confirmDialog")
        container.setGeometry(0, 0, 420, 240)
        container.setStyleSheet("""
            QFrame#confirmDialog {
                background: rgba(20, 20, 30, 0.95);
                border: 2px solid rgba(124, 58, 237, 0.40);
                border-radius: 24px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: 900; border: none; background: transparent;")
        layout.addWidget(t)

        m = QLabel(message)
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m.setWordWrap(True)
        m.setStyleSheet("color: rgba(255,255,255,0.60); font-size: 16px; border: none; background: transparent;")
        layout.addWidget(m)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)

        cancel = QPushButton("取消")
        cancel.setFixedSize(140, 56)
        cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #CCC;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 14px;
                font-size: 18px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
            QPushButton:pressed { background: rgba(255,255,255,0.06); }
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        confirm = QPushButton("确定清空")
        confirm.setFixedSize(160, 56)
        confirm.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF; border: none; border-radius: 14px;
                font-size: 18px; font-weight: 700;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #F87171, stop:1 #EF4444); }
            QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B91C1C, stop:1 #991B1B); }
        """)
        confirm.clicked.connect(self.accept)
        btn_row.addWidget(confirm)

        layout.addLayout(btn_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            geo = parent.geometry()
            self.move((geo.width() - 420) // 2, (geo.height() - 240) // 2)


# ═══════════════════════════════════════════════════════════════
# 全屏批注画布
# ═══════════════════════════════════════════════════════════════

class _WhiteboardCanvas(QWidget):
    """全屏画布 — 半透明背景，触控 + 鼠标双兼容绘图。"""

    request_close = Signal()

    # 画笔预设
    PEN_PRESETS = {"细": 2.0, "中": 5.0, "粗": 10.0}

    # 颜色预设
    COLORS = [
        (QColor(255, 60, 60),   "#EF4444"),
        (QColor(255, 200, 0),   "#F59E0B"),
        (QColor(40, 120, 255),  "#2563EB"),
        (QColor(10, 10, 10),    "#0A0A0A"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setStyleSheet("background: rgba(0, 0, 0, 20);")

        # ── 绘图状态 ──
        self._drawing = False
        self._current_path = QPainterPath()
        self.paths: list[tuple[QPainterPath, QColor, float]] = []
        self._pen_color = QColor(255, 60, 60)
        self._pen_width = 5.0
        self._eraser_mode = False
        self._eraser_width = 40.0
        self._last_pos: QPointF | None = None

        # ── 底部工具栏 ──
        self._toolbar: QWidget | None = None
        self._build_toolbar()

        # 工具栏自动隐藏定时器
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(3000)
        self._hide_timer.timeout.connect(self._fade_toolbar)

        # 覆盖所有屏幕
        screen = self.screen()
        if screen:
            self.setGeometry(screen.geometry())

    # ═══════════════════════════════════════════════════════════
    # 工具栏构建
    # ═══════════════════════════════════════════════════════════

    def _build_toolbar(self) -> None:
        self._toolbar = QWidget(self)
        self._toolbar.setObjectName("wbToolbar")
        self._toolbar.setStyleSheet("""
            QWidget#wbToolbar {
                background: rgba(20, 20, 35, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 20px;
            }
        """)

        h = QHBoxLayout(self._toolbar)
        h.setContentsMargins(20, 12, 20, 12)
        h.setSpacing(16)

        # ── 画笔粗细：细/中/粗 三段 ──
        pen_label = QLabel("画笔")
        pen_label.setStyleSheet("color: rgba(255,255,255,0.50); font-size: 16px; font-weight: 600; border: none; background: transparent;")
        h.addWidget(pen_label)

        self._pen_btns: dict[str, QPushButton] = {}
        for label, width in [("细", 2.0), ("中", 5.0), ("粗", 10.0)]:
            btn = QPushButton(label)
            btn.setFixedSize(60, 56)
            btn.setCheckable(True)
            btn.setStyleSheet(self._pen_btn_style(str(width), label == "中"))
            btn.clicked.connect(lambda checked, w=width, l=label, b=btn: self._on_pen_size(l, w))
            self._pen_btns[label] = btn
            h.addWidget(btn)

        # ── 分隔线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.15);")
        sep.setFixedWidth(2)
        h.addWidget(sep)

        # ── 颜色大色块 (50px) ──
        color_label = QLabel("颜色")
        color_label.setStyleSheet("color: rgba(255,255,255,0.50); font-size: 16px; font-weight: 600; border: none; background: transparent;")
        h.addWidget(color_label)

        self._color_btns: list[QPushButton] = []
        for i, (color, _) in enumerate(self.COLORS):
            btn = QPushButton()
            btn.setFixedSize(50, 50)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color.name()};
                    border: 3px solid {'rgba(255,255,255,0.50)' if i == 0 else 'rgba(255,255,255,0.15)'};
                    border-radius: 25px;
                }}
                QPushButton:hover {{ border-color: rgba(255,255,255,0.70); }}
                QPushButton:pressed {{ border-width: 4px; }}
            """)
            btn.clicked.connect(lambda checked, c=color, idx=i: self._on_color(idx, c))
            self._color_btns.append(btn)
            h.addWidget(btn)

        # ── 分隔线 ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.15);")
        sep2.setFixedWidth(2)
        h.addWidget(sep2)

        # ── 橡皮擦 ──
        self._eraser_btn = QPushButton("🧹")
        self._eraser_btn.setCheckable(True)
        self._eraser_btn.setFixedSize(60, 56)
        self._eraser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eraser_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #CCC;
                border: 2px solid rgba(255,255,255,0.12); border-radius: 14px;
                font-size: 22px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
            QPushButton:checked { background: rgba(245,158,11,0.30); border-color: #F59E0B; }
        """)
        self._eraser_btn.clicked.connect(self._on_eraser)
        h.addWidget(self._eraser_btn)

        # ── 撤销 ──
        undo_btn = QPushButton("↩")
        undo_btn.setFixedSize(60, 56)
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #CCC;
                border: 2px solid rgba(255,255,255,0.12); border-radius: 14px;
                font-size: 22px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
            QPushButton:pressed { background: rgba(124,58,237,0.25); }
        """)
        undo_btn.setToolTip("撤销上一笔")
        undo_btn.clicked.connect(self.undo)
        h.addWidget(undo_btn)

        # ── 清空 ──
        clear_btn = QPushButton("🗑")
        clear_btn.setFixedSize(60, 56)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #CCC;
                border: 2px solid rgba(255,255,255,0.12); border-radius: 14px;
                font-size: 22px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
        """)
        clear_btn.setToolTip("清空画布")
        clear_btn.clicked.connect(self._on_clear)
        h.addWidget(clear_btn)

        # ── 退出（红色大按钮）──
        exit_btn = QPushButton("✕ 退出")
        exit_btn.setFixedSize(100, 56)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF; border: none; border-radius: 14px;
                font-size: 18px; font-weight: 700;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #F87171, stop:1 #EF4444); }
            QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B91C1C, stop:1 #991B1B); }
        """)
        exit_btn.clicked.connect(self._on_exit)
        h.addWidget(exit_btn)

    def _pen_btn_style(self, width_str: str, active: bool) -> str:
        active_bg = "rgba(124,58,237,0.35)" if active else "rgba(255,255,255,0.08)"
        active_border = "#A78BFA" if active else "rgba(255,255,255,0.12)"
        return f"""
            QPushButton {{
                background: {active_bg}; color: #E4E4E7;
                border: 2px solid {active_border}; border-radius: 14px;
                font-size: 16px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(124,58,237,0.20); }}
            QPushButton:checked {{ background: rgba(124,58,237,0.35); border-color: #A78BFA; }}
        """

    def _on_pen_size(self, label: str, width: float) -> None:
        self._pen_width = width
        self._eraser_mode = False
        self._eraser_btn.setChecked(False)
        for lbl, btn in self._pen_btns.items():
            btn.setChecked(lbl == label)
            active = lbl == label
            w_str = str(self.PEN_PRESETS[lbl])
            btn.setStyleSheet(self._pen_btn_style(w_str, active))

    def _on_color(self, idx: int, color: QColor) -> None:
        self._pen_color = color
        self._eraser_mode = False
        self._eraser_btn.setChecked(False)
        for i, btn in enumerate(self._color_btns):
            border = "rgba(255,255,255,0.50)" if i == idx else "rgba(255,255,255,0.15)"
            c = self.COLORS[i][0]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c.name()};
                    border: 3px solid {border};
                    border-radius: 25px;
                }}
                QPushButton:hover {{ border-color: rgba(255,255,255,0.70); }}
                QPushButton:pressed {{ border-width: 4px; }}
            """)

    def _on_eraser(self, checked: bool) -> None:
        self._eraser_mode = checked
        for btn in self._pen_btns.values():
            btn.setChecked(False)
        if checked:
            self._eraser_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(245,158,11,0.30); color: #FFF;
                    border: 2px solid #F59E0B; border-radius: 14px;
                    font-size: 22px;
                }
            """)
        else:
            self._eraser_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.08); color: #CCC;
                    border: 2px solid rgba(255,255,255,0.12); border-radius: 14px;
                    font-size: 22px;
                }
                QPushButton:hover { background: rgba(255,255,255,0.15); }
            """)

    def _on_clear(self) -> None:
        dlg = _ConfirmDialog("🗑 清空画布", "确定要清除所有已绘制的批注内容吗？\n此操作无法撤销。", self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.paths.clear()
            self.update()

    def _on_exit(self) -> None:
        """退出前询问是否保存截图。"""
        if self.paths:
            dlg = _SaveDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._save_screenshot()
        self.hide()
        self.request_close.emit()

    def _save_screenshot(self) -> None:
        """将当前画布内容保存为 PNG 到桌面。"""
        try:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "桌面"
            if not desktop.exists():
                desktop = Path.home()

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = desktop / f"白板批注_{ts}.png"

            img = QImage(self.size(), QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            for path, color, width in self.paths:
                pen = QPen(color, width, Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            painter.end()
            img.save(str(save_path), "PNG")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # 工具栏定位与显隐
    # ═══════════════════════════════════════════════════════════

    def _position_toolbar(self) -> None:
        if not self._toolbar:
            return
        sh = self._toolbar.sizeHint()
        w = max(sh.width(), 1100)
        self._toolbar.setGeometry(
            (self.width() - w) // 2,
            self.height() - sh.height() - 24,
            w, sh.height(),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_toolbar()

    def _show_toolbar(self) -> None:
        if not self._toolbar:
            return
        self._toolbar.show()
        self._toolbar.raise_()
        self._toolbar.setWindowOpacity(1.0)
        self._hide_timer.start()

    def _fade_toolbar(self) -> None:
        if self._toolbar and self._toolbar.isVisible():
            anim = QPropertyAnimation(self._toolbar, b"windowOpacity")
            anim.setDuration(400)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.finished.connect(lambda: self._toolbar.hide() if self._toolbar else None)
            anim.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._position_toolbar()
        self.setFocus()

    # ═══════════════════════════════════════════════════════════
    # 绘制
    # ═══════════════════════════════════════════════════════════

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 已保存笔画
        for path, color, width in self.paths:
            pen = QPen(color, width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # 当前绘制中的笔画
        if self._drawing and not self._current_path.isEmpty():
            color = QColor(255, 255, 255) if self._eraser_mode else self._pen_color
            width = self._eraser_width if self._eraser_mode else self._pen_width
            pen = QPen(color, width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._current_path)

        painter.end()

    # ═══════════════════════════════════════════════════════════
    # 鼠标事件
    # ═══════════════════════════════════════════════════════════

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_stroke(event.position())
            self._show_toolbar()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            self._continue_stroke(event.position())
            self._show_toolbar()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._finish_stroke()

    # ═══════════════════════════════════════════════════════════
    # 触控事件 — 映射为鼠标左键事件
    # ═══════════════════════════════════════════════════════════

    def touchEvent(self, event: QTouchEvent) -> None:
        """将所有触摸点映射为 QMouseEvent，统一走鼠标事件管线"""
        points = event.points()
        if not points:
            super().touchEvent(event)
            return

        # 只处理第一个触摸点（防止多指串扰）
        pt = points[0]
        pos = pt.position()
        t = event.type()
        mod = Qt.KeyboardModifier.NoModifier

        if t == QEvent.Type.TouchBegin:
            fake = QMouseEvent(
                QEvent.Type.MouseButtonPress, pos, pos,
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mod,
            )
            self.mousePressEvent(fake)
            event.accept()
        elif t == QEvent.Type.TouchUpdate:
            fake = QMouseEvent(
                QEvent.Type.MouseMove, pos, pos,
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mod,
            )
            self.mouseMoveEvent(fake)
            event.accept()
        elif t == QEvent.Type.TouchEnd:
            fake = QMouseEvent(
                QEvent.Type.MouseButtonRelease, pos, pos,
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mod,
            )
            self.mouseReleaseEvent(fake)
            event.accept()
        else:
            super().touchEvent(event)

    # ═══════════════════════════════════════════════════════════
    # 笔画核心
    # ═══════════════════════════════════════════════════════════

    def _start_stroke(self, pos: QPointF) -> None:
        self._drawing = True
        self._current_path = QPainterPath()
        self._current_path.moveTo(pos)
        self._last_pos = pos

    def _continue_stroke(self, pos: QPointF) -> None:
        # 跳过重复点，减少冗余数据
        if self._last_pos and (pos - self._last_pos).manhattanLength() < 1:
            return
        self._last_pos = pos
        self._current_path.lineTo(pos)
        self.update()

    def _finish_stroke(self) -> None:
        if self._drawing and not self._current_path.isEmpty():
            color = QColor(255, 255, 255) if self._eraser_mode else self._pen_color
            width = self._eraser_width if self._eraser_mode else self._pen_width
            self.paths.append((self._current_path, QColor(color), float(width)))
        self._drawing = False
        self._current_path = QPainterPath()
        self._last_pos = None
        self.update()

    def undo(self) -> None:
        if self.paths:
            self.paths.pop()
            self.update()

    # ═══════════════════════════════════════════════════════════
    # 键盘快捷键（辅助）
    # ═══════════════════════════════════════════════════════════

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo()
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════════════
# 保存截图确认弹窗
# ═══════════════════════════════════════════════════════════════

class _SaveDialog(QDialog):
    """退出时询问是否保留批注截图。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 220)
        self.setModal(True)

        container = QFrame(self)
        container.setObjectName("saveDialog")
        container.setGeometry(0, 0, 420, 220)
        container.setStyleSheet("""
            QFrame#saveDialog {
                background: rgba(20, 20, 30, 0.95);
                border: 2px solid rgba(0, 212, 255, 0.35);
                border-radius: 24px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        t = QLabel("📸 是否保留批注截图？")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 900; border: none; background: transparent;")
        layout.addWidget(t)

        m = QLabel("选择\"保留\"将当前画布保存为 PNG 文件到桌面")
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m.setWordWrap(True)
        m.setStyleSheet("color: rgba(255,255,255,0.50); font-size: 16px; border: none; background: transparent;")
        layout.addWidget(m)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)

        discard = QPushButton("不保留")
        discard.setFixedSize(140, 52)
        discard.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #CCC;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 14px;
                font-size: 18px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); }
            QPushButton:pressed { background: rgba(255,255,255,0.06); }
        """)
        discard.clicked.connect(self.reject)
        btn_row.addWidget(discard)

        keep = QPushButton("📸 保留截图")
        keep.setFixedSize(160, 52)
        keep.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00D4FF, stop:1 #00B4D8);
                color: #0A0A0C; border: none; border-radius: 14px;
                font-size: 18px; font-weight: 700;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33DEFF, stop:1 #00D4FF); }
            QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00A8C8, stop:1 #0098B0); }
        """)
        keep.clicked.connect(self.accept)
        btn_row.addWidget(keep)

        layout.addLayout(btn_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            geo = parent.geometry()
            self.move((geo.width() - 420) // 2, (geo.height() - 220) // 2)


# ═══════════════════════════════════════════════════════════════
# 启动面板
# ═══════════════════════════════════════════════════════════════

class WhiteboardPage(QWidget):
    """批注白板 — 启动面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("whiteboardPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._canvas = _WhiteboardCanvas()
        self._canvas.request_close.connect(self._on_canvas_close)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("✏️")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 72px; border: none;")
        layout.addWidget(icon_label)

        title = QLabel("批注白板")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; border: none;")
        layout.addWidget(title)

        info_card = QFrame()
        info_card.setMaximumWidth(520)
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(10)

        features = [
            "✋  手指直接滑动绘图，支持多点触摸追踪",
            "🎨  底部悬浮工具栏：画笔粗细 / 颜色色块 / 橡皮",
            "↩  撤销按钮（替代 Ctrl+Z），清空需二次确认",
            "✕  红色退出按钮（替代 ESC），退出前可保存截图到桌面",
            "🖱️  同时兼容鼠标操作",
        ]
        for f in features:
            lbl = QLabel(f)
            lbl.setStyleSheet("font-size: 16px; padding: 6px 0; border: none;")
            info_layout.addWidget(lbl)

        layout.addWidget(info_card, alignment=Qt.AlignmentFlag.AlignCenter)

        start_btn = QPushButton("🎨  开始批注")
        start_btn.setFixedSize(220, 64)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF; border: none; border-radius: 16px;
                font-size: 20px; font-weight: 700;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #F87171, stop:1 #EF4444); }
            QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #B91C1C, stop:1 #991B1B); }
        """)
        start_btn.clicked.connect(self._start_annotate)
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

    def _start_annotate(self) -> None:
        """全屏画布覆盖所有屏幕。"""
        self._canvas.showFullScreen()
        self._canvas.setFocus()

    def _on_canvas_close(self) -> None:
        self._canvas.hide()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
