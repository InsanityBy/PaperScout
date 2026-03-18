# logger.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
from datetime import datetime
from pathlib import Path

from paper_scout.core.constant import DEFAULT_LOG_DIRECTORY, DEFAULT_LOG_LEVEL, DEFAULT_PACKAGE_NAME


def set_global_logger(
    log_directory: Path = DEFAULT_LOG_DIRECTORY,
    log_level: str = DEFAULT_LOG_LEVEL,
    root_name: str = DEFAULT_PACKAGE_NAME
) -> None:
    """设置全局日志记录器"""
    # 创建日志目录
    log_directory.mkdir(parents=True, exist_ok=True)
    # 创建日志文件名
    log_name = f"{root_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    # 创建日志文件路径
    log_path = log_directory / log_name
    # 获取顶层日志记录器
    logger = logging.getLogger(root_name)
    # 清理旧的处理器
    if logger.hasHandlers():
        logger.handlers.clear()
    # 配置日志记录器
    logger.setLevel(log_level)
    # 设置日志格式
    format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-28s | %(funcName)s:%(lineno)d - %(message)s")
    # 添加文件处理器
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(format)
    handler.setLevel(log_level)
    logger.addHandler(handler)
    # 阻止日志消息传播, 避免打断终端输出
    logger.propagate = False
