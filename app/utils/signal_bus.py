"""
OpenClass 全局信号总线 — 组件间解耦通信
"""
from PySide6.QtCore import QObject, Signal


class _SignalBus(QObject):
    """全局单例信号总线，连接各视图组件"""

    # 设置页保存 API 密钥后发射
    config_updated = Signal()

    # 计时器进入/退出全屏
    timer_fullscreen_entered = Signal()
    timer_fullscreen_exited = Signal()

    # 主题切换
    theme_changed = Signal(str)   # "light" | "dark" | "green"

    # 学生名单变动（导入/添加/删除）
    student_list_changed = Signal()

    # API 密钥更新（新增/修改/激活）
    signal_api_updated = Signal()


# 全局单例
signal_bus = _SignalBus()
