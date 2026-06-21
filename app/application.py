"""
Application 全局单例 — 串联启动流程

- init_all(): 分步执行数据库→配置→日志→名单，每步回调进度
- 由 SplashScreen 调用，确保初始化在启动画面期间完成
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class Application:
    """全局应用单例 — 集中管理初始化生命周期"""

    _instance: Application | None = None

    def __new__(cls) -> Application:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls) -> Application:
        """获取全局单例"""
        return cls()

    def __init__(self) -> None:
        if hasattr(self, "_init_done"):
            return
        self._init_done = False

    # ═══════════════════════════════════════════════════════════
    # 总入口 — SplashScreen 调用此方法
    # ═══════════════════════════════════════════════════════════

    def init_all(self, on_progress: Callable[[int, int, str], None] | None = None) -> None:
        """
        执行全部初始化步骤。
        on_progress(step, total, description) — 每步完成时回调。
        """
        steps: list[tuple[str, Callable[[], None]]] = [
            ("初始化日志系统",   self._init_logging),
            ("检查数据库...",    self._init_database),
            ("加载 API 配置...", self._init_api_configs),
            ("加载偏好设置...",  self._init_preferences),
            ("加载班级数据...",  self._init_classes),
        ]

        total = len(steps)
        for i, (desc, func) in enumerate(steps, start=1):
            try:
                func()
            except Exception as e:
                # 不阻断启动，继续下一步
                try:
                    from app.utils.logger import logger
                    logger.warning("init step failed: %s → %s", desc, e)
                except Exception:
                    pass
            if on_progress:
                on_progress(i, total, desc)

        self._init_done = True
        from app.utils.logger import logger
        logger.info("应用初始化完成 ✓")

    # ═══════════════════════════════════════════════════════════
    # 步骤 1 — 日志系统
    # ═══════════════════════════════════════════════════════════

    def _init_logging(self) -> None:
        from app.views.settings.log_page import setup_logging
        setup_logging()

    # ═══════════════════════════════════════════════════════════
    # 步骤 2 — 数据库
    # ═══════════════════════════════════════════════════════════

    def _init_database(self) -> None:
        from app.database.db_manager import db
        db.initialize()

    # ═══════════════════════════════════════════════════════════
    # 步骤 3 — API 配置（解密验证）
    # ═══════════════════════════════════════════════════════════

    def _init_api_configs(self) -> None:
        from app.database.db_manager import db
        from app.database.crypto import decrypt
        rows = db.fetch_all("SELECT * FROM api_configs")
        for row in rows:
            enc = row.get("api_key_encrypted", "")
            if enc:
                try:
                    decrypt(enc)
                except Exception:
                    pass  # 空或损坏，不阻塞

    # ═══════════════════════════════════════════════════════════
    # 步骤 4 — 用户偏好
    # ═══════════════════════════════════════════════════════════

    def _init_preferences(self) -> None:
        from app.utils.resource import resource_path
        config_path = Path(resource_path("data/app_config.json"))
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            _theme = data.get("Appearance", {}).get("ThemeMode", "light")

    # ═══════════════════════════════════════════════════════════
    # 步骤 5 — 班级/名单
    # ═══════════════════════════════════════════════════════════

    def _init_classes(self) -> None:
        from app.database.db_manager import db
        classes = db.fetch_all("SELECT * FROM classes")
        for cls in classes:
            db.fetch_all("SELECT * FROM students WHERE class_id=?", (cls["id"],))
