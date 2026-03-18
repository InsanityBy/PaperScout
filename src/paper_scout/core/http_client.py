# http_client.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
import requests
from requests.adapters import HTTPAdapter
from typing import Dict

from paper_scout.core.config import configs
from paper_scout.core.constant import POOL_CONNECTIONS, POOL_MAXSIZE


# 设置日志记录
logger = logging.getLogger(__name__)


def create_http_session(
    custom_headers: Dict[str, str] = {},
    pool_connections: int = POOL_CONNECTIONS,
    pool_maxsize: int = POOL_MAXSIZE
) -> requests.Session:
    """创建预配置的HTTP会话"""
    logger.debug("Creating HTTP session...")
    # 创建会话
    session = requests.Session()
    # 合并请求头
    headers = configs.common_headers.copy()
    if custom_headers:
        headers.update(custom_headers)
        logger.debug(f"Custom headers: {custom_headers}")
    else:
        logger.debug("Custom headers not provided to create HTTP session")
    session.headers.update(headers)
    # 配置连接池
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    logger.debug(f"Pool connections: {pool_connections}")
    logger.debug(f"Pool maxsize: {pool_maxsize}")
    logger.debug("HTTP session created successfully")
    return session
