"""
全局 Logger — 所有模块通过 `from app.utils.logger import logger` 使用

logger.info / warning / error 实时写入:
  - 控制台 (StreamHandler)
  - 日志文件 (RotatingFileHandler, 10MB 轮转)
  - 设置 → 日志管理页面 (QTextEditLogHandler)
"""
import logging

logger = logging.getLogger("OpenClass")
