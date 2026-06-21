"""
数据库管理器 — SQLite 连接池、建表、CRUD 辅助
"""
import sqlite3
import os
from pathlib import Path
from typing import Optional


DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "openclass.db"


class DatabaseManager:
    """SQLite 数据库单例管理器"""

    _instance: Optional["DatabaseManager"] = None
    _conn: Optional[sqlite3.Connection] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(DB_PATH))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        """首次启动执行 init.sql"""
        conn = self.get_connection()
        from app.utils.resource import resource_path
        sql_path = Path(resource_path("app/database/init.sql"))
        with open(sql_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── 通用查询辅助 ──────────────────────────────────

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self.get_connection().execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        cur = self.get_connection().execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        conn = self.get_connection()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


# 全局单例
db = DatabaseManager()
