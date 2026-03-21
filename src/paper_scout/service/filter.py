# filter.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
from typing import Dict, List

from paper_scout.core.config import configs
from paper_scout.database.model import Paper, Status


# 设置日志记录
logger = logging.getLogger(__name__)


class PaperFilter:
    """论文筛选器"""

    def __init__(self, output_mode: str = "export") -> None:
        self.output_mode = output_mode

    def filter_all(self, papers: List[Paper]) -> Dict[Status, List[Paper]]:
        """批量筛选论文"""
        if not papers:
            logger.warning("Papers not provided to filter")
            return {}
        logger.info(
            f"Filtering {len(papers)} papers with threshold {configs.relevance_threshold}...")
        # 下一阶段状态映射
        status_mapping = {
            "none": Status.COMPLETED,
            "export": Status.PENDING_EXPORT,
            "upload": Status.PENDING_UPLOAD,
        }
        # 根据输出模式获取下一阶段状态
        next_status = status_mapping[self.output_mode]
        filtered_papers = {
            next_status: [],
            Status.IRRELEVANT: []
        }
        # 根据阈值筛选
        for paper in papers:
            if paper.relevance_score >= configs.relevance_threshold:
                filtered_papers[next_status].append(paper)
            else:
                filtered_papers[Status.IRRELEVANT].append(paper)
        logger.info(f"{len(papers)} papers filtered successfully: "
                    f"{len(filtered_papers[next_status])} relevant, "
                    f"{len(filtered_papers[Status.IRRELEVANT])} irrelevant")
        return filtered_papers
