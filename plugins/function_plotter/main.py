"""
📈 函数几何画板 — PyQtGraph 交互式函数绘图插件

支持：
  - 多函数表达式输入（sin(x), x**2, 2*x+3）
  - 多条曲线叠加，自动配色
  - 鼠标/手指拖拽平移 + 滚轮/双指缩放
  - 坐标轴 + 网格线 + 悬停坐标显示
"""
from __future__ import annotations

import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QColorDialog,
    QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

try:
    import pyqtgraph as pg
    _HAS_PYQTGRAPH = True
except ImportError:
    _HAS_PYQTGRAPH = False

try:
    from sympy import sympify, lambdify, symbols
    _HAS_SYMPY = True
except ImportError:
    _HAS_SYMPY = False

from app.plugins.base import OpenClassPlugin

# 默认配色（10 种）
CURVE_COLORS = [
    "#6366f1", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
    "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#3b82f6",
]


class FunctionPlotterWidget(QWidget):
    """函数绘图主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("functionPlotter")
        self.setMinimumSize(600, 500)
        self._functions: list[dict] = []  # [{expr, color, data}]
        self._x = symbols("x")

        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── 左侧控制面板 ──
        left = QWidget()
        left.setFixedWidth(280)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(10)

        title = QLabel("函数表达式")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        ll.addWidget(title)

        expr_row = QHBoxLayout()
        self._expr_input = QLineEdit()
        self._expr_input.setPlaceholderText("如: sin(x), x**2, 2*x+3")
        self._expr_input.setMinimumHeight(40)
        self._expr_input.setStyleSheet("""
            QLineEdit { font-size: 15px; padding: 6px 12px;
                border: 1px solid #cbd5e1; border-radius: 8px; }
            QLineEdit:focus { border-color: #6366f1; }
        """)
        self._expr_input.returnPressed.connect(self._add_function)
        expr_row.addWidget(self._expr_input, stretch=1)

        self._color_btn = QPushButton("🎨")
        self._color_btn.setToolTip("选择颜色")
        self._color_btn.setMinimumSize(40, 40)
        self._color_btn.clicked.connect(self._pick_color)
        expr_row.addWidget(self._color_btn)
        ll.addLayout(expr_row)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ 添加曲线")
        add_btn.setMinimumHeight(48)
        add_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; padding: 8px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        add_btn.clicked.connect(self._add_function)
        btn_row.addWidget(add_btn, stretch=1)

        clear_btn = QPushButton("清空")
        clear_btn.setMinimumHeight(48)
        clear_btn.setStyleSheet("""
            QPushButton { font-size: 15px; background: rgba(128,128,128,0.08); color: #888;
                border: none; border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { background: rgba(128,128,128,0.18); }
        """)
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        ll.addLayout(btn_row)

        # 已添加函数列表
        list_label = QLabel("已添加函数")
        list_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.DemiBold))
        list_label.setStyleSheet("border: none; margin-top: 8px;")
        ll.addWidget(list_label)

        self._func_list = QListWidget()
        self._func_list.setMinimumHeight(150)
        self._func_list.setStyleSheet("""
            QListWidget { font-size: 14px; border: 1px solid #e2e8f0;
                border-radius: 8px; padding: 4px; }
        """)
        self._func_list.itemDoubleClicked.connect(self._remove_function)
        ll.addWidget(self._func_list)

        # 快捷按钮
        quick_label = QLabel("快捷函数 (点击添加)")
        quick_label.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
        ll.addWidget(quick_label)

        quick_funcs = ["sin(x)", "cos(x)", "tan(x)", "x**2", "x**3", "exp(x)", "log(x)", "sqrt(x)", "1/x", "abs(x)"]
        q_grid = QHBoxLayout()
        q_grid.setSpacing(4)
        btn_count = 0
        for fn in quick_funcs:
            btn = QPushButton(fn)
            btn.setMinimumHeight(36)
            btn.setStyleSheet("""
                QPushButton { font-size: 12px; padding: 4px 8px;
                    background: rgba(99,102,241,0.06); color: #6366f1;
                    border: 1px solid rgba(99,102,241,0.15); border-radius: 6px; }
                QPushButton:hover { background: rgba(99,102,241,0.12); }
            """)
            btn.clicked.connect(lambda checked, f=fn: self._quick_add(f))
            q_grid.addWidget(btn)
            btn_count += 1
            if btn_count % 5 == 0 and fn != quick_funcs[-1]:
                ll.addLayout(q_grid)
                q_grid = QHBoxLayout()
                q_grid.setSpacing(4)
        if q_grid.count() > 0:
            ll.addLayout(q_grid)

        ll.addStretch()
        root.addWidget(left)

        # ── 右侧绘图区 ──
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        if not _HAS_PYQTGRAPH:
            err = QLabel("请安装 pyqtgraph: pip install pyqtgraph")
            err.setStyleSheet("color: #ef4444; font-size: 18px; padding: 40px;")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(err)
            root.addWidget(right, stretch=1)
            return

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground("#fafbfc")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.setLabel("bottom", "x")
        self._plot_widget.setLabel("left", "y")
        self._plot_widget.setMouseEnabled(x=True, y=True)
        self._plot_widget.addLegend(size=None, offset=(-10, 10))

        # 十字光标 / 悬停标签
        self._cursor_label = pg.TextItem("", anchor=(0, 0))
        self._plot_widget.addItem(self._cursor_label)
        self._cursor_label.setPos(0, 0)
        self._cursor_label.setVisible(False)

        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        rl.addWidget(self._plot_widget, stretch=1)
        root.addWidget(right, stretch=1)

    def _current_color(self) -> str:
        idx = len(self._functions) % len(CURVE_COLORS)
        return CURVE_COLORS[idx]

    def _add_function(self) -> None:
        if not _HAS_SYMPY:
            QMessageBox.warning(self, "提示", "请安装 sympy: pip install sympy")
            return
        if not _HAS_PYQTGRAPH:
            QMessageBox.warning(self, "提示", "请安装 pyqtgraph: pip install pyqtgraph")
            return

        expr = self._expr_input.text().strip()
        if not expr:
            return

        try:
            parsed = sympify(expr)
            f = lambdify(self._x, parsed, "numpy")
            # 快速测试
            _ = f(np.array([0.0, 1.0]))
        except Exception as e:
            QMessageBox.warning(self, "表达式错误", str(e))
            return

        color = self._current_color()
        x = np.linspace(-10, 10, 2000)
        try:
            y = f(x)
            if isinstance(y, complex) or (isinstance(y, np.ndarray) and np.issubdtype(y.dtype, np.complexfloating)):
                y = np.real(y)
        except Exception as e:
            QMessageBox.warning(self, "计算错误", str(e))
            return

        self._functions.append({"expr": expr, "color": color, "x": x, "y": y, "parsed": parsed})

        # 绘图
        pen = pg.mkPen(color=color, width=2.5)
        self._plot_widget.plot(x, y, pen=pen, name=expr)

        self._func_list.addItem(f"  {color} {expr}")
        self._expr_input.clear()
        self._expr_input.setFocus()

    def _remove_function(self, item: QListWidgetItem) -> None:
        row = self._func_list.row(item)
        if 0 <= row < len(self._functions):
            self._functions.pop(row)
        self._func_list.takeItem(row)
        self._redraw()

    def _clear_all(self) -> None:
        self._functions.clear()
        self._func_list.clear()
        self._plot_widget.clear()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

    def _redraw(self) -> None:
        if not _HAS_PYQTGRAPH:
            return
        self._plot_widget.clear()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        for fn in self._functions:
            pen = pg.mkPen(color=fn["color"], width=2.5)
            self._plot_widget.plot(fn["x"], fn["y"], pen=pen, name=fn["expr"])

    def _quick_add(self, expr: str) -> None:
        self._expr_input.setText(expr)
        self._add_function()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            # 将选中的颜色缓存到临时属性
            self._custom_color = color.name()

    def _on_mouse_moved(self, pos) -> None:
        if not self._plot_widget.plotItem.vb.sceneBoundingRect().contains(pos):
            self._cursor_label.setVisible(False)
            return
        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        x_val = mouse_point.x()
        y_val = mouse_point.y()
        self._cursor_label.setText(f"({x_val:.3f}, {y_val:.3f})")
        self._cursor_label.setPos(x_val, y_val)
        self._cursor_label.setVisible(True)


class _FunctionGeometryPlugin(OpenClassPlugin):
    plugin_id = "function_plotter"
    plugin_name = "函数几何画板"
    plugin_version = "1.0.0"
    plugin_description = "交互式函数绘图工具，支持拖拽平移与双指缩放"
    plugin_icon = "📈"
    plugin_author = "OpenClass Team"
    plugin_category = "课堂工具"

    def create_widget(self) -> QWidget:
        return FunctionPlotterWidget()


# 供 PluginManager 扫描
plugin_instance = _FunctionGeometryPlugin


# ── PluginWidget — 供新版插件系统 (PluggableManager) 加载 ──
class PluginWidget(QWidget):
    """插件入口 Widget，直接继承 QWidget。"""
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = FunctionPlotterWidget()
        layout.addWidget(self._inner)
