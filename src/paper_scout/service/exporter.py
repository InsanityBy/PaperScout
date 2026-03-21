# exporter.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import json
import logging
import re
from typing import Dict, List

from paper_scout.core.config import configs
from paper_scout.database.model import Paper, Status


# 设置日志记录
logger = logging.getLogger(__name__)


class MarkdownExporter:
    """Markdown文件导出器"""

    def __init__(self) -> None:
        self.export_directory = configs.export_directory
        self.export_directory.mkdir(parents=True, exist_ok=True)

    def export_all(self, papers: List[Paper]) -> Dict[Status, List[Paper]]:
        """批量导出论文"""
        if not papers:
            logger.warning("Papers not provided to export")
            return {}
        logger.info(f"Exporting {len(papers)} papers to Markdown files...")
        all_papers = {
            Status.COMPLETED: [],
            Status.EXPORT_FAILED: []
        }
        # 批量导出
        for paper in papers:
            try:
                self._export_single(paper)
                all_papers[Status.COMPLETED].append(paper)
            except Exception as e:
                all_papers[Status.EXPORT_FAILED].append(paper)
                logger.error(f"Failed to export paper with DOI: {paper.doi}")
                logger.debug(f"Exception: {e}")
        if not all_papers[Status.COMPLETED]:
            logger.error("Failed to export any paper")
            return all_papers
        logger.info(f"{len(all_papers[Status.COMPLETED])} papers exported successfully")
        return all_papers

    def _export_single(self, paper: Paper) -> None:
        """导出单篇论文"""
        # 清理文件名中的非法字符
        safe_title = self._clean_filename(paper.title)
        file_path = self.export_directory / f"{safe_title}.md"
        # 反序列化标签
        try:
            tags_list = json.loads(paper.tags_json) if paper.tags_json else []
            tags_str = ", ".join(tags_list)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tags for paper with DOI: {paper.doi}")
            tags_str = ""
        # 构建Markdown内容
        content = (
            "---\n"
            f"title: {paper.title}\n"
            f"doi: {paper.doi}\n"
            f"year: {paper.year}\n"
            f"venue: {paper.venue_name} ({paper.venue_type.value})\n"
            f"tags: {tags_str}\n"
            f"relevance_score: {paper.relevance_score} / 10.0\n"
            "---\n\n"
            f"# {paper.title}\n\n"
            f"{paper.title_cn}\n\n"
            "# 基本信息\n\n"
            f"## 来源\n\n{paper.venue_name} ({paper.venue_type.value}, {paper.year})\n\n"
            f"## 摘要\n\n{paper.abstract}\n\n{paper.abstract_cn}\n\n"
            "## AI 分析结果\n\n"
            "### 相关性分析\n\n"
            f"1. **评分**: {paper.relevance_score} / 10.0\n"
            f"2. **理由**: {paper.relevance_reason}\n\n"
            f"### 标签\n\n{tags_str}\n\n"
            "## 阅读笔记\n\n"
        )
        # 写入Markdown文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _clean_filename(title: str) -> str:
        """清理并生成安全的文件名"""
        # 替换冒号为单个连字符
        safe_title = title.replace(": ", "-").replace(":", "-")
        # 替换文件系统非法字符(\, /, *, ?, ", <, >, |, 换行, 制表符)为单个下划线
        safe_title = re.sub(r'[\\/*?"<>|\n\r\t]', "_", safe_title)
        # 替换连续下划线和连续空格为单个下划线
        safe_title = re.sub(r"[_]+", "_", safe_title)
        safe_title = re.sub(r"\s+", "_", safe_title)
        # 去除首尾空格, 句号, 下划线和连字符
        safe_title = safe_title.strip(" ._-")
        # 长度截断
        safe_title = safe_title[:150].strip(" ._-")
        return safe_title
