# importer.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from paper_scout.core.config import configs
from paper_scout.database.crud import bulk_update_papers
from paper_scout.database.database import SessionLocal
from paper_scout.database.model import Paper, Status, VenueType


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CSVRowUpdate:
    doi: str
    updates: Dict[str, object]
    row_num: int


class CSVImporter:
    """CSV文件导入器"""

    _CSV_HEADERS = [
        "DOI", "Year", "Venue Type", "Venue", "Title", "Abstract",
        "Title (CN)", "Abstract (CN)", "Relevance Score", "Relevance Reason",
        "Tags", "Status", "Retry Count", "Create Time", "Update Time"
    ]

    def import_from_csv(self, file_path: Path) -> Dict[str, int | List[str]]:
        summary = {
            "total_rows": 0,
            "updated": 0,
            "unchanged": 0,
            "duplicate_rows": 0,
            "skipped_unknown_doi": 0,
            "invalid_rows": 0,
            "errors": []
        }
        logger.info(f"Importing updates from CSV: {file_path}")
        updates_map = {}
        # 读取CSV文件
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # 检查文件头是否存在
            if not reader.fieldnames:
                error_info = "CSV header missing"
                logger.error(error_info)
                summary["errors"].append(error_info)
                summary["invalid_rows"] = 1
                return summary
            # 检查DOI列是否缺失
            if "DOI" not in reader.fieldnames:
                error_info = "CSV header missing required column: DOI"
                logger.error(error_info)
                summary["errors"].append(error_info)
                summary["invalid_rows"] = 1
                return summary
            missing_headers = [
                header for header in self._CSV_HEADERS if header not in reader.fieldnames
            ]
            if missing_headers:
                logger.warning(f"CSV missing expected columns: {','.join(missing_headers)}")
            # 逐行解析CSV文件
            for row_num, row in enumerate(reader, start=2):
                # 记录总行数
                summary["total_rows"] += 1
                # 解析行数据
                record, error_info = self._parse_row(row=row, row_num=row_num)
                # 处理错误行
                if record is None:
                    summary["errors"].append(error_info)
                    summary["invalid_rows"] += 1
                    continue
                # 处理重复行
                doi = record.doi.lower()
                if doi in updates_map:
                    logger.warning(f"Duplicate DOI at line {row_num}, overwriting previous update")
                    summary["duplicate_rows"] += 1
                updates_map[doi] = record
        # 处理无更新
        if not updates_map:
            logger.warning("No valid rows to import")
            return summary
        # 应用更新
        updated, unchanged, skipped = self._apply_updates(updates=list(updates_map.values()))
        summary["updated"] = updated
        summary["unchanged"] = unchanged
        summary["skipped_unknown_doi"] = skipped
        return summary

    def _parse_row(self, row: Dict, row_num: int) -> Tuple[CSVRowUpdate | None, str]:
        """解析单行数据"""
        updates = {}
        # 解析主键
        doi = self._clean_string(row.get("DOI"))
        if not doi:
            error_info = f"Line {row_num}: missing DOI"
            return None, error_info
        # 解析其他列
        error_info = []
        # 通用字段解析
        field_mappings: List[Tuple[str, str, Callable | None]] = [
            ("Year", "year", int),
            ("Venue", "venue_name", None),
            ("Title", "title", None),
            ("Abstract", "abstract", None),
            ("Title (CN)", "title_cn", None),
            ("Abstract (CN)", "abstract_cn", None),
            ("Relevance Score", "relevance_score", float),
            ("Relevance Reason", "relevance_reason", None),
            ("Retry Count", "retry_count", int)
        ]
        for column, update_key, converter in field_mappings:
            value = self._clean_string(value=row.get(column))
            # 未提供值, 跳过
            if value is None:
                continue
            # 转换值
            if converter:
                try:
                    updates[update_key] = converter(value)
                except ValueError:
                    error_info.append(f"invalid '{column}' = '{value}'")
            else:
                updates[update_key] = value
        # 特殊字段解析
        venue_type = self._clean_string(value=row.get("Venue Type"))
        if venue_type is not None:
            try:
                updates["venue_type"] = VenueType(venue_type.upper())
            except ValueError:
                error_info.append(f"invalid 'Venue Type' = '{venue_type}'")
        status = self._clean_string(value=row.get("Status"))
        if status is not None:
            try:
                updates["status"] = (Status(int(status)) if status.isdigit()
                                     else Status[status.upper()])
            except (KeyError, ValueError):
                error_info.append(f"invalid 'Status' = '{status}'")
        tags = self._clean_string(value=row.get("Tags"))
        if tags is not None:
            try:
                parsed_tags = json.loads(tags)
            except json.JSONDecodeError:
                parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            try:
                updates["tags_json"] = json.dumps(parsed_tags)
            except (TypeError, ValueError):
                error_info.append(f"invalid 'Tags' = '{tags}'")
        # 错误处理
        if error_info:
            return None, f"Line {row_num}: {'; '.join(error_info)}"
        if not updates:
            logger.debug(f"Line {row_num}: no updates")
        return CSVRowUpdate(doi=doi, updates=updates, row_num=row_num), ""

    def _apply_updates(self, updates: List[CSVRowUpdate]) -> Tuple[int, int, int]:
        """应用更新"""
        if not updates:
            logger.warning("Updates not provided to apply")
            return 0, 0, 0
        updated = 0
        unchanged = 0
        skipped = 0
        now = datetime.now(timezone.utc)
        # 分块应用跟新
        with SessionLocal() as session:
            # 切片处理
            for i in range(0, len(updates), configs.chunk_size):
                batch_updates = updates[i:i + configs.chunk_size]
                lower_dois = [row.doi.lower() for row in batch_updates]
                # 查询已存在的论文
                existing = self._fetch_existing(session=session, dois=lower_dois)
                # 更新论文
                updated_papers = []
                for row in batch_updates:
                    paper = existing.get(row.doi.lower())
                    # 跳过不存在的论文
                    if not paper:
                        skipped += 1
                        logger.warning(f"Line {row.row_num}: unknown DOI '{row.doi}', skipping")
                        continue
                    # 跳过无更新的论文
                    if not row.updates:
                        unchanged += 1
                        continue
                    # 更新值并跳过未改动
                    changed = False
                    for field, value in row.updates.items():
                        current = getattr(paper, field)
                        if current != value:
                            setattr(paper, field, value)
                            changed = True
                    if changed:
                        paper.updated_at = now
                        updated_papers.append(paper)
                    else:
                        unchanged += 1
                # 批量写入数据库
                if updated_papers:
                    updated += bulk_update_papers(
                        session=session,
                        papers=updated_papers,
                        chunk_size=configs.chunk_size
                    )
                    session.commit()
        return updated, unchanged, skipped

    @staticmethod
    def _clean_string(value: str | None) -> str | None:
        """清洗字符串"""
        return value.strip() if value and value.strip() else None

    @staticmethod
    def _fetch_existing(session: Session, dois: List[str]) -> Dict[str, Paper]:
        """查询已存在的论文"""
        existing = {}
        papers = (
            session.query(Paper)
            .filter(func.lower(Paper.doi).in_(dois)).all()
        )
        for paper in papers:
            existing[paper.doi.lower()] = paper
        return existing
