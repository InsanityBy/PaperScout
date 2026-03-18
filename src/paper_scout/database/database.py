# database.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import os
import sys
import traceback

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from paper_scout.core.config import configs
from paper_scout.core.constant import ROOT_DIRECTORY
from paper_scout.database.model import Base


# 创建数据库文件夹
if configs.db_url.startswith("sqlite:///"):
    # 提取数据库路径
    db_path = configs.db_url.replace("sqlite:///", "")
    if db_path:
        db_directory = os.path.dirname(db_path)
        os.makedirs(db_directory, exist_ok=True)
    else:
        db_path = ROOT_DIRECTORY / "db" / "papers.db"
        print("[WARNING] Database path not provided, using default path")
    print(f"[INFO] Database path: {db_path}")
else:
    print(f"[CRITICAL] Unsupported database URL: {configs.db_url}")
    print(f"[INFO] Supported database: SQLite")
    print(f"[INFO] Required prefix: 'sqlite:///'")
    sys.exit(1)

try:
    # 创建数据库引擎
    engine = create_engine(configs.db_url, connect_args={"check_same_thread": False})
    # 创建数据库会话工厂
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print(f"[INFO] Database created/connected successfully")
except Exception as e:
    print(f"[CRITICAL] Failed to create/connect database")
    print(f"Exception: {e}")
    traceback.print_exc()
    sys.exit(1)


def init_database() -> None:
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
