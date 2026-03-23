# crud.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
from typing import Dict, Iterator, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from paper_scout.core.constant import DEFAULT_CHUNK_SIZE
from paper_scout.database.model import Paper, Status, VenueType


# 设置日志记录
logger = logging.getLogger(__name__)


def bulk_create_papers(
    session: Session,
    papers_data: List[Dict[str, int | Status | str | VenueType]],
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> int:
    """批量创建论文"""
    # 检查是否有论文需要创建
    if not papers_data:
        logger.debug("Papers not provided to create")
        return 0
    logger.debug(f"Received {len(papers_data)} papers to create")
    # 筛选包含DOI且不重复的论文数据
    unique_papers_dict = {}
    for paper_data in papers_data:
        doi = paper_data.get("doi")
        if doi:
            unique_papers_dict[str(doi).lower()] = paper_data
    unique_papers = list(unique_papers_dict.items())
    if not unique_papers:
        logger.debug("No unique papers with DOI provided to create")
        return 0
    logger.debug(f"Creating {len(unique_papers)} papers...")
    # 创建论文
    total_created = 0
    for i in range(0, len(unique_papers), chunk_size):
        chunk = unique_papers[i:i + chunk_size]
        # 获取小写DOI列表
        lower_dois = [data[0] for data in chunk]
        # 批量查询已存在的DOI
        existing_records = (
            session.query(func.lower(Paper.doi))
            .filter(func.lower(Paper.doi).in_(lower_dois)).all()
        )
        existing_dois = {row[0] for row in existing_records}
        # 筛选出需要创建的新论文
        new_papers = [
            Paper(**data[1]) for data in chunk if data[0] not in existing_dois
        ]
        # 批量创建新论文
        if new_papers:
            session.add_all(new_papers)
            session.flush()
            total_created += len(new_papers)
    logger.debug(f"{total_created} papers created successfully")
    return total_created


def yield_papers(
    session: Session,
    filters: Dict[str, int | List | Status | str | Tuple | VenueType],
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Tuple[int, Iterator[List[Paper]]]:
    """流式查询论文"""
    logger.debug("Received request to yield papers with filters")
    # 查询论文
    query = session.query(Paper)
    # 应用过滤条件
    if filters:
        # 遍历过滤条件
        for key, value in filters.items():
            # 跳过无效的过滤键
            if not hasattr(Paper, key) or value is None:
                logger.warning(f"Invalid filter key ignored: {key}")
                continue
            # 获取列对象
            column = getattr(Paper, key)
            if isinstance(value, list):
                # 列表解析为IN查询
                query = query.filter(column.in_(value))
                logger.debug(f"Filter added: {key} IN {value}")
            elif isinstance(value, tuple) and len(value) == 2:
                # 元组解析为范围查询[min, max]
                min_value, max_value = value
                if min_value is not None:
                    query = query.filter(column >= min_value)
                if max_value is not None:
                    query = query.filter(column <= max_value)
                logger.debug(f"Filter added: {key} BETWEEN {min_value} AND {max_value}")
            else:
                # 其他解析为精确匹配
                query = query.filter(column == value)
                logger.debug(f"Filter added: {key} == {value}")
    else:
        logger.debug("Filters not provided, querying all papers")
    # 统计数量
    total_count = query.count()
    if total_count == 0:
        logger.debug("No papers found with filters")
        return 0, iter([])
    logger.debug(f"Yielding {total_count} papers in chunks({chunk_size} per chunk)")

    # 生成器函数
    def _yield_papers() -> Iterator[List[Paper]]:
        # 论文分块
        chunk_list = []
        for paper in query.yield_per(chunk_size):
            chunk_list.append(paper)
            if len(chunk_list) == chunk_size:
                yield chunk_list
                chunk_list = []
        # 返回剩余论文
        if chunk_list:
            yield chunk_list
        logger.debug(f"{total_count} papers yielded successfully")
    return total_count, _yield_papers()


def bulk_update_papers(
    session: Session,
    papers: List[Paper],
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> int:
    """批量更新论文"""
    # 检查是否有论文需要更新
    if not papers:
        logger.debug("Papers not provided to update")
        return 0
    logger.debug(f"Received {len(papers)} papers to update")
    # 转换为字典列表
    paper_dict_list = []
    for paper in papers:
        paper_dict = {
            column.name: getattr(paper, column.name)
            for column in paper.__table__.columns
        }
        paper_dict_list.append(paper_dict)
    logger.debug(f"Updating {len(paper_dict_list)} papers...")
    # 更新论文
    total_updated = 0
    for i in range(0, len(paper_dict_list), chunk_size):
        chunk = paper_dict_list[i:i + chunk_size]
        session.bulk_update_mappings(Paper, chunk)
        session.flush()
        total_updated += len(chunk)
    logger.debug(f"{total_updated} papers updated successfully")
    return total_updated


def bulk_delete_papers(
    session: Session,
    papers: List[Paper],
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> int:
    """批量删除论文"""
    # 检查是否有论文需要删除
    if not papers:
        logger.debug("Papers not provided to delete")
        return 0
    logger.debug(f"Received {len(papers)} papers to delete")
    logger.debug(f"Deleting {len(papers)} papers...")
    # 删除论文
    total_deleted = 0
    for i in range(0, len(papers), chunk_size):
        chunk = papers[i:i + chunk_size]
        dois = [paper.doi for paper in chunk]
        deleted_count = (session.query(Paper).filter(Paper.doi.in_(dois))
                         .delete(synchronize_session=False))
        session.flush()
        total_deleted += deleted_count
    logger.debug(f"{total_deleted} papers deleted successfully")
    return total_deleted
