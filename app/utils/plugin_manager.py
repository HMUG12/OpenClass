"""
轻量级插件管理器 — 基于 plugin.json 的动态导入

功能：
  - 扫描 plugins/ 目录，读取 plugin.json 元数据
  - 导入外部插件（复制文件夹到 plugins/）
  - 动态加载插件 Widget（importlib）
  - 启用/禁用状态持久化（plugins/.plugin_state.json）
  - 卸载插件（删除文件夹）
  - 所有操作写入日志（logs/plugin.log + 主 logger）
"""
from __future__ import annotations

import json
import os as _os
import shutil
import sys as _sys
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.utils.logger import logger as _main_logger


# ── 路径工具：区分开发模式与 PyInstaller 打包模式 ──

def _get_bundled_root() -> Path:
    """返回插件资源所在的根目录（开发模式: 项目根; 打包模式: _MEIPASS）"""
    try:
        return Path(_sys._MEIPASS)  # type: ignore[attr-defined]
    except Exception:
        return Path(__file__).resolve().parent.parent.parent


def _get_writable_root() -> Path:
    """返回可写根目录（开发模式: 项目根; 打包模式: exe 所在目录）"""
    try:
        _ = _sys._MEIPASS  # type: ignore[attr-defined]
        return Path(_sys.executable).parent
    except Exception:
        return Path(__file__).resolve().parent.parent.parent


# ── 插件日志文件 ──
_PLUGIN_LOG_PATH = _get_writable_root() / "logs" / "plugin.log"
_PLUGIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class _PluginFileHandler:
    """为插件操作提供独立的文件日志"""
    _instance: _PluginFileHandler | None = None

    def __new__(cls) -> _PluginFileHandler:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {message}\n"
        try:
            with open(_PLUGIN_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def plugin_log(level: str, message: str) -> None:
    """同时写入主 logger 和插件专用日志文件"""
    _main_logger.info(f"[Plugins] {message}")
    _PluginFileHandler().log(level, message)


# ── 插件状态持久化路径 ──
_STATE_FILE = _get_writable_root() / "plugins" / ".plugin_state.json"
_BUNDLED_PLUGINS = _get_bundled_root() / "plugins"
_WRITABLE_PLUGINS = _get_writable_root() / "plugins"


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class PluginMeta:
    """单个插件的元数据"""

    def __init__(self, folder: Path, manifest: dict[str, Any]):
        self.folder = folder
        self.id: str = manifest.get("id", folder.name)
        self.name: str = manifest.get("name", "未命名插件")
        self.version: str = manifest.get("version", "1.0.0")
        self.author: str = manifest.get("author", "未知")
        self.description: str = manifest.get("description", "")
        self.icon: str = manifest.get("icon", "🧩")
        self.main: str = manifest.get("main", "main.py")
        self.class_name: str = manifest.get("class", "PluginWidget")
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        state = _load_state()
        return state.get(self.id, {}).get("enabled", True)

    @enabled.setter
    def enabled(self, val: bool) -> None:
        state = _load_state()
        state.setdefault(self.id, {})["enabled"] = val
        _save_state(state)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "icon": self.icon,
            "main": self.main,
            "class": self.class_name,
            "enabled": self.enabled,
        }


class PluggableManager(QObject):
    """插件管理器（单例）"""

    plugins_changed = Signal()

    _instance: PluggableManager | None = None

    def __new__(cls) -> PluggableManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._plugins: dict[str, PluginMeta] = {}
        self.scan()

    # ── 扫描 ──────────────────────────────────────────

    def scan(self) -> list[PluginMeta]:
        """扫描 plugins/ 目录，返回所有已安装插件的元数据列表"""
        self._plugins.clear()

        scanned: set[str] = set()

        for src_dir in (_BUNDLED_PLUGINS, _WRITABLE_PLUGINS):
            if not src_dir.exists():
                continue
            for folder in src_dir.iterdir():
                if not folder.is_dir() or folder.name.startswith("."):
                    continue
                if folder.name in scanned:
                    continue
                scanned.add(folder.name)
                manifest_path = folder / "plugin.json"
                if not manifest_path.exists():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    meta = PluginMeta(folder, manifest)
                    self._plugins[meta.id] = meta
                except json.JSONDecodeError as e:
                    plugin_log("ERROR", f"扫描 {folder.name} 失败: JSON 解析错误 — {e}")
                except Exception as e:
                    plugin_log("ERROR", f"扫描 {folder.name} 失败: {e}")

        return list(self._plugins.values())

    @property
    def plugin_list(self) -> list[PluginMeta]:
        return sorted(self._plugins.values(), key=lambda p: p.name)

    def get(self, plugin_id: str) -> PluginMeta | None:
        return self._plugins.get(plugin_id)

    # ── 导入 ──────────────────────────────────────────

    def import_plugin(self, source_folder: str) -> tuple[bool, str]:
        """
        导入外部插件到 plugins/ 目录。
        返回 (success, message)。
        """
        src = Path(source_folder)
        if not src.is_dir():
            plugin_log("ERROR", f"导入失败: {source_folder} 不是有效文件夹")
            return False, "选择的路径不是有效文件夹"

        manifest_path = src / "plugin.json"
        if not manifest_path.exists():
            plugin_log("ERROR", f"导入失败: {source_folder} 缺少 plugin.json")
            return False, "插件文件夹中缺少 plugin.json 文件"

        # 验证 plugin.json
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            plugin_log("ERROR", f"导入失败: plugin.json 解析错误 — {e}")
            return False, f"plugin.json 格式错误: {e}"

        plugin_id = manifest.get("id")
        if not plugin_id:
            plugin_log("ERROR", "导入失败: plugin.json 缺少 'id' 字段")
            return False, "plugin.json 中缺少 'id' 字段"

        main_file = manifest.get("main", "main.py")
        if not (src / main_file).exists():
            plugin_log("ERROR", f"导入失败: 缺少入口文件 {main_file}")
            return False, f"缺少入口文件: {main_file}"

        # 检查是否已存在
        dest = _WRITABLE_PLUGINS / plugin_id
        if dest.exists():
            plugin_log("WARN", f"导入: 插件 '{plugin_id}' 已存在，将被覆盖")
            try:
                shutil.rmtree(dest)
            except OSError as e:
                plugin_log("ERROR", f"导入失败: 无法删除旧版本 — {e}")
                return False, f"无法删除已存在的插件: {e}"

        # 复制整个文件夹
        try:
            shutil.copytree(src, dest)
        except OSError as e:
            plugin_log("ERROR", f"导入失败: 复制文件出错 — {e}")
            return False, f"复制文件失败: {e}"

        # 刷新列表
        self.scan()
        self.plugins_changed.emit()
        plugin_log("INFO", f"导入成功: {manifest.get('name', plugin_id)} v{manifest.get('version', '?')} (id={plugin_id})")
        return True, f"插件 '{manifest.get('name', plugin_id)}' 导入成功"

    # ── 加载 Widget ───────────────────────────────────

    def load_plugin_widget(self, plugin_id: str):
        """
        动态导入插件模块，返回实例化的 QWidget。
        返回 (widget | None, error_message | None)。
        """
        meta = self._plugins.get(plugin_id)
        if meta is None:
            plugin_log("ERROR", f"加载失败: 插件 '{plugin_id}' 不存在")
            return None, "插件不存在"

        if not meta.enabled:
            plugin_log("WARN", f"加载: 插件 '{plugin_id}' 已被禁用")
            return None, "插件已被禁用"

        import sys
        main_path = meta.folder / meta.main
        if not main_path.exists():
            plugin_log("ERROR", f"加载失败: 入口文件不存在 {main_path}")
            return None, f"入口文件不存在: {meta.main}"

        # 动态导入
        try:
            import importlib.util
            module_name = f"plugins.{meta.id}.{meta.main.replace('.py', '')}"
            spec = importlib.util.spec_from_file_location(module_name, str(main_path))
            if spec is None or spec.loader is None:
                raise ImportError(f"无法定位模块: {main_path}")
            module = importlib.util.module_from_spec(spec)
            # 确保插件目录在 path 中（插件可能需要导入本地模块）
            if str(meta.folder) not in sys.path:
                sys.path.insert(0, str(meta.folder))
            spec.loader.exec_module(module)
        except Exception:
            tb = traceback.format_exc()
            plugin_log("ERROR", f"加载失败: 模块导入异常\n{tb}")
            return None, f"模块导入失败:\n{tb}"

        # 获取目标类
        cls = getattr(module, meta.class_name, None)
        if cls is None:
            plugin_log("ERROR", f"加载失败: 找不到类 '{meta.class_name}' 在 {meta.main} 中")
            return None, f"入口文件中找不到类: {meta.class_name}"

        # 实例化
        try:
            widget = cls()
        except Exception:
            tb = traceback.format_exc()
            plugin_log("ERROR", f"加载失败: 实例化异常\n{tb}")
            return None, f"实例化失败:\n{tb}"

        # 验证是 QWidget
        from PySide6.QtWidgets import QWidget
        if not isinstance(widget, QWidget):
            plugin_log("ERROR", f"加载失败: '{meta.class_name}' 不是 QWidget 的子类")
            return None, f"类 '{meta.class_name}' 未继承 QWidget"

        plugin_log("INFO", f"加载成功: {meta.name} v{meta.version}")
        return widget, None

    # ── 启用/禁用 ─────────────────────────────────────

    def toggle_enabled(self, plugin_id: str) -> bool:
        """切换启用/禁用状态，返回新状态"""
        meta = self._plugins.get(plugin_id)
        if meta is None:
            return False
        new_state = not meta.enabled
        meta.enabled = new_state
        label = "启用" if new_state else "禁用"
        plugin_log("INFO", f"{label}: {meta.name} v{meta.version}")
        self.plugins_changed.emit()
        return new_state

    # ── 卸载 ──────────────────────────────────────────

    def uninstall(self, plugin_id: str) -> tuple[bool, str]:
        """
        卸载插件：删除 plugins/ 下的对应文件夹。
        返回 (success, message)。
        """
        meta = self._plugins.get(plugin_id)
        if meta is None:
            return False, "插件不存在"

        plugin_name = meta.name
        try:
            shutil.rmtree(meta.folder)
        except OSError as e:
            plugin_log("ERROR", f"卸载失败: {plugin_name} — {e}")
            return False, f"删除文件夹失败: {e}"

        # 清除状态
        state = _load_state()
        state.pop(plugin_id, None)
        _save_state(state)

        self._plugins.pop(plugin_id, None)
        self.plugins_changed.emit()
        plugin_log("INFO", f"卸载成功: {plugin_name} v{meta.version}")
        return True, f"插件 '{plugin_name}' 已卸载"

    # ── 日志 ──────────────────────────────────────────

    @staticmethod
    def get_recent_logs(count: int = 100) -> str:
        """获取最近 N 条插件日志"""
        if not _PLUGIN_LOG_PATH.exists():
            return "暂无日志"
        try:
            lines = _PLUGIN_LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
            return "\n".join(lines[-count:])
        except Exception:
            return "读取日志失败"
