"""
OpenClass 插件接口 — 标准化插件抽象基类

所有插件必须继承 OpenClassPlugin 并实现以下方法：
  - create_widget()   → 返回功能主界面 QWidget
  - initialize()      → 插件加载时调用（注册事件、加载数据）
  - cleanup()         → 插件卸载时调用（释放资源、保存状态）

插件元数据通过类属性声明：
  - plugin_id          (str)  唯一标识
  - plugin_name        (str)  显示名称
  - plugin_version     (str)  版本号
  - plugin_description (str)  功能描述
  - plugin_icon        (str)  emoji 图标
  - plugin_author      (str)  作者
  - plugin_category    (str)  分类："课堂工具" / "电教工具" / "其他"
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget


class OpenClassPlugin(ABC):
    """插件抽象基类 — 定义标准化接口。"""

    # ── 元数据（子类必须覆盖） ──
    plugin_id: str = ""
    plugin_name: str = "未命名插件"
    plugin_version: str = "1.0.0"
    plugin_description: str = ""
    plugin_icon: str = "🧩"
    plugin_author: str = "未知"
    plugin_category: str = "其他"

    # ── 状态 ──
    _enabled: bool = True
    _widget: QWidget | None = None

    def __init__(self):
        self._initialized = False

    # ═══════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════

    def initialize(self) -> None:
        """插件加载时调用一次。子类可覆盖以注册事件、加载数据等。"""
        self._initialized = True

    def cleanup(self) -> None:
        """插件卸载前调用。子类可覆盖以保存状态、释放资源等。"""
        self._initialized = False

    @abstractmethod
    def create_widget(self) -> QWidget:
        """创建并返回插件的主界面 Widget。每次调用应返回新实例。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # 状态属性
    # ═══════════════════════════════════════════════════════════

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def to_dict(self) -> dict:
        """导出插件元数据为字典（供插件管理器索引）。"""
        return {
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "plugin_description": self.plugin_description,
            "plugin_icon": self.plugin_icon,
            "plugin_author": self.plugin_author,
            "plugin_category": self.plugin_category,
            "enabled": self._enabled,
        }
