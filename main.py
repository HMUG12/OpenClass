"""
OpenClass — 教师课堂工具箱（基于 qfluentwidgets）
"""
import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

# ── 全局单例守卫：MainWindow 在整个生命周期内只实例化一次 ──
_main_window = None


def main():
    global _main_window

    app = QApplication(sys.argv)
    app.setApplicationName("OpenClass")
    app.setApplicationVersion("测试版")

    # ── 启动加载动画 ──
    from app.splash_screen import SplashScreen
    splash = SplashScreen()

    def _on_initialization_finished():
        """信号槽：Splash 进度条走完 + 5s 倒计时结束后，实例化 MainWindow（仅一次）。"""
        global _main_window

        if _main_window is not None:
            # 防御性检查：若已存在则直接复用，严禁新建第二个实例
            _main_window.show()
            _main_window.raise_()
            _main_window.activateWindow()
            return

        from app.main_window import MainWindow
        _main_window = MainWindow()
        _main_window.show()

    splash.initialization_finished.connect(_on_initialization_finished)
    splash.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
