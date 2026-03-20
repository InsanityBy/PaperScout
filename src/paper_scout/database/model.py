# model.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, func, Index, Integer, String, text, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """基础数据库模型"""

    pass


class VenueType(str, enum.Enum):
    """出处类型枚举"""

    # 会议
    CONFERENCE = "CONFERENCE"
    # 期刊
    JOURNAL = "JOURNAL"


class Status(enum.IntEnum):
    """处理状态枚举"""

    # 主流程
    # 获取待处理, 仅保留编号占位, 未使用
    PENDING_FETCH = 100
    # 解析待处理
    PENDING_PARSE = 110
    # 分析待处理
    PENDING_ANALYZE = 120
    # 筛选待处理
    PENDING_FILTER = 130
    # 上传待处理
    PENDING_UPLOAD = 140

    # 正常终止状态
    # 正常终止
    COMPLETED = 200
    # 不相关论文
    IRRELEVANT = 230

    # 异常中间状态
    # 获取失败, 仅保留编号占位, 未使用
    FETCH_FAILED = 300
    # 解析失败
    PARSE_FAILED = 310
    # DOI验证失败
    DOI_INVALID = 311
    # 分析失败
    ANALYZE_FAILED = 320
    # 上传失败
    UPLOAD_FAILED = 340

    # 异常终止状态
    # 永久失败, 需要手动处理
    PERMANENT_FAILED = 400
    # DOI缺失, 需要手动处理
    MISSING_DOI = 410


class StatusInteger(TypeDecorator):
    """Status对应的数据库类型, 存储枚举值的整数"""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """写入数据库时触发"""
        if value is None:
            return None
        return value.value if hasattr(value, "value") else int(value)

    def process_result_value(self, value, dialect):
        """读取数据库时触发"""
        if value is None:
            return None
        return Status(value)


class Paper(Base):
    """论文数据库模型"""

    # 表名
    __tablename__ = "papers"

    # 基本信息
    doi: Mapped[str] = mapped_column(String, primary_key=True)  # 支持伪DOI
    title: Mapped[str] = mapped_column(String)
    abstract: Mapped[str] = mapped_column(Text)
    year: Mapped[int] = mapped_column(Integer)
    venue_type: Mapped[VenueType] = mapped_column(SQLEnum(
        VenueType, values_callable=lambda obj: [e.value for e in obj]))
    venue_name: Mapped[str] = mapped_column(String)
    zotero_key: Mapped[str | None] = mapped_column(String, unique=True)  # 防止重复上传

    # 分析结果
    title_cn: Mapped[str] = mapped_column(String, default="", server_default=text("''"))
    abstract_cn: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    relevant_score: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    relevance_reason: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    tags_json: Mapped[str] = mapped_column(Text, default="[]", server_default=text("'[]'"))

    # 状态信息
    status: Mapped[Status] = mapped_column(StatusInteger, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    # 时间信息
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        server_onupdate=func.now()
    )

    # 索引, 实现DOI不区分大小写查询
    __table_args__ = (
        Index("idx_papers_doi_lower", func.lower(doi), unique=True),
    )
