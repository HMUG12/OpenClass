"""
路径工具 — PyInstaller 打包兼容

所有读取资源文件（qss、json、sql、图片等）的代码
统一通过 resource_path() 获取路径，确保在
python main.py 开发模式和 PyInstaller 打包后
都能正确定位文件。
"""
from __future__ import annotations

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    返回资源的绝对路径，兼容开发模式与 PyInstaller 打包模式。

    开发模式: 基于当前工作目录（通常为项目根目录）
    打包模式: 基于 sys._MEIPASS（PyInstaller 临时解压目录）
    """
    try:
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        # 开发模式：以项目根目录为基准
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
