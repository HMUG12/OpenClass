"""
主题管理 — qfluentwidgets + 自定义 QSS 文件加载 + 霓虹发光特效
"""
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel

try:
    from qfluentwidgets import setTheme, setThemeColor, Theme
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False

from app.utils.resource import resource_path

_QSS_DIR = Path(resource_path("resources"))
_DARK_QSS_PATH = _QSS_DIR / "dark_theme.qss"
_DARK_QSS: str | None = None


def _load_dark_qss() -> str:
    """懒加载 dark_theme.qss 文件内容"""
    global _DARK_QSS
    if _DARK_QSS is None:
        try:
            _DARK_QSS = _DARK_QSS_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            _DARK_QSS = ""
    return _DARK_QSS


class ThemeManager:
    """统一主题切换入口 —— 静态方法"""

    # 跟踪需要清理的发光控件
    _glow_widgets: list[QLabel] = []

    @staticmethod
    def apply_theme(app: QApplication, theme: str) -> None:
        """
        根据 theme 切换：
          - "dark"  → qfluentwidgets Theme.DARK + dark_theme.qss + 发光特效
          - "green" → qfluentwidgets Theme.LIGHT + #4caf50
          - "light" → qfluentwidgets Theme.LIGHT + #6366f1
        """
        # 1) 先移除上一种主题的特效
        ThemeManager._remove_glow_effects()

        # 2) 清除上次载入的自定义 QSS
        app.setStyleSheet("")

        # 3) 按主题分支处理
        if _HAS_FLUENT:
            if theme == "dark":
                setTheme(Theme.DARK)
                setThemeColor('#7C3AED')          # 紫色主色调
                # 叠加自定义深色 QSS
                qss = _load_dark_qss()
                if qss:
                    app.setStyleSheet(qss)
                # 注入霓虹发光特效（QSS 不支持 text-shadow 的补救方案）
                ThemeManager._apply_glow_effects()
            elif theme == "green":
                setTheme(Theme.LIGHT)
                setThemeColor('#4caf50')
            else:
                setTheme(Theme.LIGHT)
                setThemeColor('#6366f1')
        else:
            ThemeManager._apply_fallback_qss(app, theme)

    # ──────────────────────────────────────────────
    # 霓虹发光 — QGraphicsDropShadowEffect 模拟 text-shadow
    # ──────────────────────────────────────────────

    @staticmethod
    def _apply_glow_effects() -> None:
        """找到所有 #timerNumber / #pickerName 标签并附上青光发光"""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        app = QApplication.instance()
        if not app:
            return

        glow = QColor(0, 212, 255, 128)  # #00D4FF @ 50%

        for widget in app.allWidgets():
            if not isinstance(widget, QLabel):
                continue
            name = widget.objectName()
            if name not in ("timerNumber", "pickerName"):
                continue
            # 已有效果则跳过
            if widget.graphicsEffect() is not None:
                continue

            effect = QGraphicsDropShadowEffect(widget)
            effect.setBlurRadius(24)
            effect.setOffset(0, 0)
            effect.setColor(glow)
            widget.setGraphicsEffect(effect)
            ThemeManager._glow_widgets.append(widget)

    @staticmethod
    def _remove_glow_effects() -> None:
        """清理上一轮注入的发光特效"""
        for w in ThemeManager._glow_widgets:
            try:
                w.setGraphicsEffect(None)
            except RuntimeError:
                pass
        ThemeManager._glow_widgets.clear()

    # ──────────────────────────────────────────────
    # 降级方案 — 纯 PySide6 setStyleSheet
    # ──────────────────────────────────────────────

    @staticmethod
    def _apply_fallback_qss(app: QApplication, theme: str) -> None:
        from PySide6.QtGui import QColor

        if theme == "dark":
            # 优先尝试加载 .qss 文件
            qss = _load_dark_qss()
            if qss:
                app.setStyleSheet(qss)
                ThemeManager._apply_glow_effects()
                return
            # 文件缺失则用内联降级
            app.setStyleSheet("""
                QMainWindow { background: #0D0D0F; }
                QWidget { color: #E4E4E7; }
                #contentStack { background: #0D0D0F; }
                QGroupBox {
                    background: #1C1C1E; border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px; color: #D4D4D8;
                }
                QLineEdit, QTextEdit, QSpinBox, QComboBox {
                    background: #2C2C2E; border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 10px; padding: 8px 14px; color: #E4E4E7;
                }
                QLabel#timerNumber { color: #00D4FF; font-weight: 900; }
                QLabel#pickerName { color: #00D4FF; font-weight: 900; }
                QPushButton {
                    background: #2C2C2E; border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 10px; padding: 10px 22px; color: #D4D4D8;
                }
                QPushButton:hover { background: #3A3A3E; }
                QScrollBar:vertical { background: #0D0D0F; width: 10px; }
                QScrollBar::handle:vertical {
                    background: #3A3A3C; border-radius: 4px; min-height: 40px; margin: 2px;
                }
                QScrollBar::handle:vertical:hover { background: #5A5A5C; }
            """)
            ThemeManager._apply_glow_effects()
        elif theme == "green":
            app.setStyleSheet("""
                QMainWindow { background: #e8f5e9; }
                #contentStack { background: #e8f5e9; }
                QLabel { color: #1b5e20; }
                QGroupBox { color: #2e7d32; border-color: #a5d6a7; }
                QLineEdit, QTextEdit, QSpinBox, QComboBox {
                    background: #fff; border: 1px solid #a5d6a7;
                    color: #1b5e20; border-radius: 8px; padding: 6px 10px;
                }
            """)
        else:
            app.setStyleSheet("""
                QMainWindow { background: #f0f2f5; }
                #contentStack { background: #f0f2f5; }
                QLabel { color: #1e293b; }
                QGroupBox { color: #334155; border-color: #e2e8f0; }
                QLineEdit, QTextEdit, QSpinBox, QComboBox {
                    background: #fff; border: 1px solid #cbd5e1;
                    color: #1e293b; border-radius: 8px; padding: 6px 10px;
                }
            """)
