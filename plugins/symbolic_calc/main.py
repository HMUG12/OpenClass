"""
🧮 函数计算器 — SymPy 符号计算插件

支持：
  - 数学表达式实时计算
  - 变量定义（如 x=5）
  - 求导 (diff)、积分 (integrate)、方程求解 (solve)
  - 计算历史记录，点击可重用
  - 常用函数快捷按钮
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.plugins.base import OpenClassPlugin

try:
    from sympy import sympify, symbols, diff, integrate, solve, Symbol, lambdify, latex
    _HAS_SYMPY = True
except ImportError:
    _HAS_SYMPY = False


class SymbolicCalcWidget(QWidget):
    """符号计算器主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("symbolicCalculator")
        self.setMinimumSize(600, 500)
        self._variables: dict[str, Symbol] = {str(s): s for s in symbols("x y z t a b c n m")}
        self._history: list[str] = []

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # ── 左侧主输入区 ──
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(12)

        # 表达式输入
        expr_label = QLabel("数学表达式")
        expr_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        expr_label.setStyleSheet("border: none;")
        lv.addWidget(expr_label)

        self._expr_input = QLineEdit()
        self._expr_input.setPlaceholderText("如: sin(pi/4), diff(x**2, x), int(x**2, x), solve(x**2-4, x)")
        self._expr_input.setMinimumHeight(48)
        self._expr_input.setStyleSheet("""
            QLineEdit { font-size: 17px; padding: 8px 16px;
                border: 2px solid #6366f1; border-radius: 10px; }
        """)
        self._expr_input.returnPressed.connect(self._calculate)
        lv.addWidget(self._expr_input)

        # 主按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        calc_btn = QPushButton("⚡ 计算")
        calc_btn.setMinimumHeight(56)
        calc_btn.setStyleSheet("""
            QPushButton { font-size: 17px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; padding: 8px 24px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        calc_btn.clicked.connect(self._calculate)
        btn_row.addWidget(calc_btn, stretch=2)

        diff_btn = QPushButton("∂ 求导")
        diff_btn.setMinimumHeight(56)
        diff_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: rgba(139,92,246,0.10);
                color: #8b5cf6; border: 1px solid rgba(139,92,246,0.20); border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { background: rgba(139,92,246,0.18); }
        """)
        diff_btn.clicked.connect(self._quick_diff)
        btn_row.addWidget(diff_btn, stretch=1)

        int_btn = QPushButton("∫ 积分")
        int_btn.setMinimumHeight(56)
        int_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: rgba(34,197,94,0.10);
                color: #22c55e; border: 1px solid rgba(34,197,94,0.20); border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { background: rgba(34,197,94,0.18); }
        """)
        int_btn.clicked.connect(self._quick_integrate)
        btn_row.addWidget(int_btn, stretch=1)

        solve_btn = QPushButton("= 求解")
        solve_btn.setMinimumHeight(56)
        solve_btn.setStyleSheet("""
            QPushButton { font-size: 15px; font-weight: bold; background: rgba(245,158,11,0.10);
                color: #f59e0b; border: 1px solid rgba(245,158,11,0.20); border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { background: rgba(245,158,11,0.18); }
        """)
        solve_btn.clicked.connect(self._quick_solve)
        btn_row.addWidget(solve_btn, stretch=1)

        lv.addLayout(btn_row)

        # 快捷函数按钮
        quick_label = QLabel("常用函数")
        quick_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        lv.addWidget(quick_label)

        funcs = [
            ("sin", "sin()"), ("cos", "cos()"), ("tan", "tan()"),
            ("log", "log()"), ("sqrt", "sqrt()"), ("exp", "exp()"),
            ("π", "pi"), ("e", "E"),
        ]
        quick_grids = [QHBoxLayout(), QHBoxLayout()]
        quick_grids[0].setSpacing(6)
        quick_grids[1].setSpacing(6)
        for i, (name, code) in enumerate(funcs):
            idx = i // 4
            btn = QPushButton(name)
            btn.setMinimumHeight(42)
            btn.setStyleSheet("""
                QPushButton { font-size: 16px; font-weight: 600;
                    background: rgba(99,102,241,0.05); color: #6366f1;
                    border: 1px solid rgba(99,102,241,0.15); border-radius: 8px; }
                QPushButton:hover { background: rgba(99,102,241,0.12); }
            """)
            btn.clicked.connect(lambda checked, c=code: self._insert_func(c))
            quick_grids[idx].addWidget(btn, stretch=1)
        lv.addLayout(quick_grids[0])
        lv.addLayout(quick_grids[1])

        # 结果区
        result_label = QLabel("计算结果")
        result_label.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.DemiBold))
        result_label.setStyleSheet("border: none; margin-top: 8px;")
        lv.addWidget(result_label)

        self._result_display = QTextEdit()
        self._result_display.setReadOnly(True)
        self._result_display.setMinimumHeight(180)
        self._result_display.setStyleSheet("""
            QTextEdit { font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 16px; padding: 14px;
                border: 1px solid #e2e8f0; border-radius: 10px;
                background: rgba(0,0,0,0.01); }
        """)
        lv.addWidget(self._result_display, stretch=1)

        layout.addWidget(left, stretch=3)

        # ── 右侧历史 ──
        right = QWidget()
        right.setFixedWidth(260)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(10)

        hist_title = QLabel("📜 计算历史")
        hist_title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        hist_title.setStyleSheet("border: none;")
        rv.addWidget(hist_title)

        self._history_list = QListWidget()
        self._history_list.setStyleSheet("""
            QListWidget { font-size: 13px; border: 1px solid #e2e8f0;
                border-radius: 8px; padding: 6px; }
        """)
        self._history_list.itemClicked.connect(self._on_history_clicked)
        rv.addWidget(self._history_list, stretch=1)

        clear_hist = QPushButton("清空历史")
        clear_hist.setMinimumHeight(40)
        clear_hist.setStyleSheet("""
            QPushButton { font-size: 13px; background: rgba(128,128,128,0.06); color: #888;
                border: none; border-radius: 8px; }
            QPushButton:hover { background: rgba(128,128,128,0.15); }
        """)
        clear_hist.clicked.connect(self._history_list.clear)
        rv.addWidget(clear_hist)

        layout.addWidget(right, stretch=1)

    def _calculate(self) -> None:
        if not _HAS_SYMPY:
            self._result_display.setHtml("<span style='color:#ef4444'>请安装 sympy: pip install sympy</span>")
            return

        expr_str = self._expr_input.text().strip()
        if not expr_str:
            return

        # 检查是否是变量赋值
        if "=" in expr_str and "==" not in expr_str.replace(" ", ""):
            parts = expr_str.split("=", 1)
            var_name = parts[0].strip()
            var_value = parts[1].strip()
            try:
                val = sympify(var_value)
                sym = Symbol(var_name)
                self._variables[var_name] = sym
                self._result_display.setHtml(
                    f"<span style='color:#6366f1;font-weight:bold'>{var_name}</span> = "
                    f"<span style='font-size:20px'>{val}</span>"
                )
                self._add_history(f"{var_name} = {var_value} → {val}")
                return
            except Exception as e:
                self._result_display.setHtml(f"<span style='color:#ef4444'>错误: {e}</span>")
                return

        try:
            result = sympify(expr_str)
            # 尝试在某些情况下进一步简化
            try:
                result_simplified = result.evalf(8)
            except Exception:
                result_simplified = result

            display = f"""
            <p style='color:#64748b;font-size:14px'>表达式: <b>{expr_str}</b></p>
            <p style='color:#6366f1;font-size:22px;font-weight:bold;margin-top:8px'>
            {result_simplified}</p>
            """
            if hasattr(result, 'free_symbols') and result.free_symbols:
                syms = ', '.join(str(s) for s in result.free_symbols)
                display += f"<p style='color:#94a3b8;font-size:13px'>包含变量: {syms}</p>"

            self._result_display.setHtml(display)
            self._add_history(f"{expr_str} → {result_simplified}")
        except Exception as e:
            self._result_display.setHtml(f"<span style='color:#ef4444;font-size:15px'>计算错误: {e}</span>")

    def _quick_diff(self) -> None:
        expr = self._expr_input.text().strip()
        if expr:
            self._expr_input.setText(f"diff({expr}, x)")
        self._calculate()

    def _quick_integrate(self) -> None:
        expr = self._expr_input.text().strip()
        if expr:
            self._expr_input.setText(f"integrate({expr}, x)")
        self._calculate()

    def _quick_solve(self) -> None:
        expr = self._expr_input.text().strip()
        if expr:
            self._expr_input.setText(f"solve({expr}, x)")
        self._calculate()

    def _insert_func(self, code: str) -> None:
        cursor = self._expr_input.cursorPosition()
        text = self._expr_input.text()
        self._expr_input.setText(text[:cursor] + code + text[cursor:])
        self._expr_input.setFocus()

    def _add_history(self, entry: str) -> None:
        self._history.append(entry)
        # 简化显示
        short = entry[:80] + ("..." if len(entry) > 80 else "")
        item = QListWidgetItem(short)
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self._history_list.insertItem(0, item)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        full = item.data(Qt.ItemDataRole.UserRole)
        self._expr_input.setText(full)
        self._calculate()


class _SymbolicCalcPlugin(OpenClassPlugin):
    plugin_id = "symbolic_calc"
    plugin_name = "函数计算器"
    plugin_version = "1.0.0"
    plugin_description = "符号计算器，支持求导、积分、方程求解"
    plugin_icon = "🧮"
    plugin_author = "OpenClass Team"
    plugin_category = "课堂工具"

    def create_widget(self) -> QWidget:
        return SymbolicCalcWidget()


plugin_instance = _SymbolicCalcPlugin


# ── PluginWidget — 供新版插件系统 (PluggableManager) 加载 ──
class PluginWidget(QWidget):
    """插件入口 Widget，直接继承 QWidget。"""
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = SymbolicCalcWidget()
        layout.addWidget(self._inner)
