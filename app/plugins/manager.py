"""
PluginManager — 插件管理器

- 扫描 plugins/ 目录下的 plugin.json 元数据
- 动态加载插件模块
- 维护已加载插件的索引
- 支持启用/禁用/卸载（运行时）
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Type

from app.plugins.base import OpenClassPlugin
from app.utils.resource import resource_path

logger = logging.getLogger("OpenClass")


class PluginManager:
    """插件管理器单例"""

    _instance: PluginManager | None = None

    def __new__(cls) -> PluginManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._plugins: dict[str, OpenClassPlugin] = {}
            cls._instance._metadata: dict[str, dict] = {}
        return cls._instance

    @property
    def plugins(self) -> dict[str, OpenClassPlugin]:
        """返回 {plugin_id: plugin_instance}"""
        if not self._loaded:
            self.scan()
        return self._plugins

    @property
    def plugin_list(self) -> list[OpenClassPlugin]:
        """返回已启用插件的列表"""
        self.scan()
        return [p for p in self._plugins.values() if p.enabled]

    def scan(self) -> None:
        """扫描 plugins/ 目录，加载所有有效插件的 json 元数据。"""
        base = Path(resource_path("plugins"))
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            # 确保在打包环境下也能创建
            real_base = Path(__file__).resolve().parent.parent.parent / "plugins"
            real_base.mkdir(parents=True, exist_ok=True)
            base = real_base
        else:
            # 开发环境：Path(resource_path) 返回的是绝对路径
            pass

        # 兜底：直接用相对路径推断
        root = Path(__file__).resolve().parent.parent.parent
        plugins_dir = root / "plugins"

        if not plugins_dir.exists():
            logger.warning("插件目录不存在: %s", plugins_dir)
            return

        for folder in plugins_dir.iterdir():
            if not folder.is_dir():
                continue
            json_path = folder / "plugin.json"
            if not json_path.exists():
                continue

            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
                pid = meta.get("plugin_id", "")
                if not pid:
                    continue
                self._metadata[pid] = meta

                # 如果已加载则跳过
                if pid not in self._plugins:
                    self._load_plugin(pid, folder, meta)
            except Exception as e:
                logger.error("加载插件 %s 失败: %s", folder.name, e)

        self._loaded = True

    def _load_plugin(self, pid: str, folder: Path, meta: dict) -> None:
        """动态导入插件模块并实例化。"""
        entry = meta.get("entry", "main")
        module_path = folder / f"{entry}.py"
        if not module_path.exists():
            logger.warning("插件入口文件不存在: %s", module_path)
            return

        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{pid}", str(module_path)
            )
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{pid}"] = mod
            spec.loader.exec_module(mod)

            # 查找模块中的 OpenClassPlugin 子类
            plugin_cls: Type[OpenClassPlugin] | None = None
            for name in dir(mod):
                obj = getattr(mod, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, OpenClassPlugin)
                    and obj is not OpenClassPlugin
                ):
                    plugin_cls = obj
                    break

            if plugin_cls is None:
                logger.warning("插件 %s 未找到 OpenClassPlugin 子类", pid)
                return

            instance = plugin_cls()
            # 用 json 中的元数据覆盖类属性（允许 json 优先）
            for key in (
                "plugin_name", "plugin_version", "plugin_description",
                "plugin_icon", "plugin_author", "plugin_category",
            ):
                if key in meta:
                    setattr(instance, key, meta[key])

            instance.initialize()
            self._plugins[pid] = instance
            logger.info("插件已加载: %s v%s", instance.plugin_name, instance.plugin_version)
        except Exception as e:
            logger.error("加载插件 %s 异常: %s", pid, e)

    def get(self, plugin_id: str) -> OpenClassPlugin | None:
        return self.plugins.get(plugin_id)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.enabled = enabled

    def unload(self, plugin_id: str) -> None:
        """卸载插件（cleanup + 从索引移除）。"""
        plugin = self._plugins.pop(plugin_id, None)
        if plugin:
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error("插件卸载异常 %s: %s", plugin_id, e)
            logger.info("插件已卸载: %s", plugin_id)

    def reload(self, plugin_id: str) -> None:
        """重新加载指定插件。"""
        self.unload(plugin_id)
        meta = self._metadata.get(plugin_id)
        if meta is None:
            return
        root = Path(__file__).resolve().parent.parent.parent
        folder = root / "plugins" / plugin_id
        if folder.exists():
            self._load_plugin(plugin_id, folder, meta)

    @classmethod
    def instance(cls) -> PluginManager:
        return cls()
