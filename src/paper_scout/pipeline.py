# pipeline.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
import signal
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List

from tqdm import tqdm

from paper_scout.core.config import configs
from paper_scout.database.crud import yield_papers, bulk_update_papers, bulk_create_papers
from paper_scout.database.database import init_database, SessionLocal
from paper_scout.database.model import Paper, Status
from paper_scout.service.analyzer import LLMAnalyzer
from paper_scout.service.exporter import CSVExporter, MarkdownExporter
from paper_scout.service.fetcher import create_arxiv_fetcher, DBLPFetcher, merged_fetcher
from paper_scout.service.filter import PaperFilter
from paper_scout.service.parser import DOIParser
from paper_scout.service.uploader import ZoteroUploader


# 设置日志记录
logger = logging.getLogger(__name__)
# 设置全局退出事件
shutdown_event = threading.Event()


# 定义信号处理函数
def _signal_handler(signum, frame) -> None:
    """处理终止信号"""
    logger.info("Received termination signal, waiting for current tasks to complete...")
    shutdown_event.set()


# 注册信号处理函数
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


class Pipeline:
    """工作流程"""

    def __init__(self, start_year: int, end_year: int, output_mode: str = "export") -> None:
        self.start_year = start_year
        self.end_year = end_year
        self.output_mode = output_mode
        init_database()
        self.arxiv_fetcher = None  # 检测冲突后创建
        self.dblp_fetcher = DBLPFetcher(start_year=start_year, end_year=end_year)
        self.parser = DOIParser()
        self.analyzer = LLMAnalyzer()
        self.filter = PaperFilter(output_mode=output_mode)
        self.uploader = ZoteroUploader()
        self.exporter = MarkdownExporter()
        self.csv_exporter = CSVExporter()

    def query_papers(self, status: str) -> None:
        """查询论文"""
        logger.info("-" * 50)
        logger.info(f"Query papers with status: {status}")
        print("-" * 50)
        print(f"\nQuery papers with status: {status}")
        # 筛选条件
        filters = {"year": (self.start_year, self.end_year)}
        try:
            valid_status = getattr(Status, status)
            filters["status"] = valid_status
        except AttributeError:
            logger.error(f"Invalid status: {status}")
            print(f"Invalid status: {status}")
            return
        # 查询论文
        with SessionLocal() as session:
            count, paper_generator = yield_papers(
                session=session,
                filters=filters,
                chunk_size=configs.chunk_size
            )
            if count == 0:
                logger.info(f"[*] No papers with status {status}")
                print(f"[*] No papers with status {status}")
                return
            logger.info(f"[*] Found {count} papers with conditions "
                        f"(Year: {self.start_year} - {self.end_year}, Status: {status})")
            print(f"[*] Found {count} papers with conditions "
                  f"(Year: {self.start_year} - {self.end_year}, Status: {status})")
            # 用户交互确认
            logger.debug("User confirm to export papers")
            confirm = input("    Do you want to export these papers? [y/N]: ").strip().lower()
            logger.debug(f"User input: {confirm}")
            if confirm != "y":
                logger.info("Export cancelled")
                print("    Export cancelled")
                return
            # 获取文件名
            logger.debug("User input filename")
            filename = input(
                "    Enter filename (without extension, leave empty for default): ").strip()
            logger.debug(f"User input: {filename}")
            if not filename:
                filename = f"export_{status}_{self.start_year}_{self.end_year}"
            if not filename.lower().strip().endswith(".csv"):
                filename += ".csv"
            logger.info(f"[*] Exporting to {configs.export_directory / filename}...")
            print(f"[*] Exporting to {configs.export_directory / filename}...")
            # 写入CSV文件
            with tqdm(total=count, desc="    Exporting to CSV", unit=" paper", leave=False) as pbar:
                for paper_chunk in paper_generator:
                    # 检查是否收到终止信号
                    if shutdown_event.is_set():
                        logger.warning("Received termination signal, stopping export")
                        break
                    try:
                        self.csv_exporter.export_all(paper_chunk, filename)
                        logger.info(f"{len(paper_chunk)} papers exported successfully")
                        pbar.update(len(paper_chunk))
                    except Exception as e:
                        logger.error(f"Failed to export paper chunk")
                        logger.debug(f"Exception: {e}")
                        pbar.update(len(paper_chunk))
                        continue
            logger.info(f"Exported {count} papers successfully")
            print(f"[*] Exported {count} papers successfully")

    def run_all(self) -> None:
        """运行所有流程"""
        logger.info("-" * 50)
        logger.info("Start running all stages...")
        logger.info(f"Fetch -> Parse -> Analyze -> Filter -> Output")
        print("-" * 50)
        print("\nStart running all stages...")
        print(f"Fetch -> Parse -> Analyze -> Filter -> Output\n")
        # 获取论文
        self.run_fetch_stage()
        if shutdown_event.is_set():
            return
        # 解析论文
        self.run_parse_stage()
        if shutdown_event.is_set():
            return
        # 分析论文
        self.run_analyze_stage()
        if shutdown_event.is_set():
            return
        # 筛选论文
        self.run_filter_stage()
        if shutdown_event.is_set():
            return
        # 输出论文
        self.run_output_stage()
        if shutdown_event.is_set():
            return
        logger.info("=" * 50)
        logger.info("Finish processing")
        print("=" * 50)
        print("\nFinish processing")

    def run_fetch_stage(self) -> None:
        """获取论文"""
        logger.info("-" * 50)
        logger.info("[1/5] Start fetching papers...")
        print("-" * 50)
        print("\n[1/5] Start fetching papers...")
        # 创建ArxivFetcher
        self.arxiv_fetcher = create_arxiv_fetcher(
            start_year=self.start_year, end_year=self.end_year)
        saved_count = 0
        with SessionLocal() as session:
            # 合并DBLP和arXiv论文来源
            for venue_name, papers_data in tqdm(
                    merged_fetcher(self.dblp_fetcher, self.arxiv_fetcher),
                    desc="    Fetching papers", unit=" venue", leave=False):
                if shutdown_event.is_set():
                    break
                count = bulk_create_papers(session=session, papers_data=papers_data)
                saved_count += count
                logger.info(f"[*] Fetched {len(papers_data)} papers from {venue_name}")
                tqdm.write(f"[*] Fetched {len(papers_data)} papers from {venue_name}")
            session.commit()
        logger.info(f"[1/5] Finish fetching papers, saved {saved_count} new papers")
        print(f"[1/5] Finish fetching papers, saved {saved_count} new papers\n")

    def run_parse_stage(self) -> None:
        """解析论文"""
        logger.info("-" * 50)
        logger.info("[2/5] Start parsing papers...")
        print("-" * 50)
        print("\n[2/5] Start parsing papers...")
        for status in [Status.PENDING_PARSE, Status.PARSE_FAILED, Status.DOI_INVALID]:
            self.batch_process(current_status=status, process_function=self.parser.parse_all)
        logger.info("[2/5] Finish parsing papers")
        print("[2/5] Finish parsing papers\n")

    def run_analyze_stage(self) -> None:
        """分析论文"""
        logger.info("-" * 50)
        logger.info("[3/5] Start analyzing papers...")
        print("-" * 50)
        print("\n[3/5] Start analyzing papers...")
        for status in [Status.PENDING_ANALYZE, Status.ANALYZE_FAILED]:
            self.batch_process(current_status=status, process_function=self.analyzer.analyze_all)
        logger.info("[3/5] Finish analyzing papers")
        print("[3/5] Finish analyzing papers\n")

    def run_filter_stage(self, refilter: bool = False) -> None:
        """筛选论文"""
        logger.info("-" * 50)
        logger.info("[4/5] Start filtering papers...")
        print("-" * 50)
        print("\n[4/5] Start filtering papers\n")
        current_status_list = []
        if refilter:
            current_status_list.extend(
                [Status.PENDING_UPLOAD, Status.PENDING_EXPORT, Status.COMPLETED, Status.IRRELEVANT])
            logger.info(f"[*] Refiltering papers")
            print(f"[*] Refiltering papers")
        current_status_list.append(Status.PENDING_FILTER)
        for status in current_status_list:
            self.batch_process(current_status=status, process_function=self.filter.filter_all)
        logger.info("[4/5] Finish filtering papers")
        print("[4/5] Finish filtering papers\n")

    def run_output_stage(self) -> None:
        """输出论文"""
        logger.info("-" * 50)
        logger.info(f"[5/5] Start outputting papers (Mode: {self.output_mode})...")
        print("-" * 50)
        print(f"\n[5/5] Start outputting papers (Mode: {self.output_mode})...")
        if self.output_mode == "upload":
            current_status_list = [Status.PENDING_UPLOAD, Status.UPLOAD_FAILED]
            process_function = self.uploader.upload_all
        elif self.output_mode == "export":
            current_status_list = [Status.PENDING_EXPORT, Status.EXPORT_FAILED]
            process_function = self.exporter.export_all
        else:
            current_status_list = []
        for status in current_status_list:
            self.batch_process(current_status=status, process_function=process_function)
        logger.info("[5/5] Finish outputting papers")
        print("[5/5] Finish outputting papers\n")

    def batch_process(self,
                      current_status: Status,
                      process_function: Callable[[List[Paper]], Dict[Status, List[Paper]]]
                      ) -> None:
        """处理指定状态的论文"""
        with SessionLocal() as session:
            # 获取所有状态为current_status的论文
            count, paper_generator = yield_papers(
                session=session,
                filters={"status": current_status, "year": (self.start_year, self.end_year)},
                chunk_size=configs.chunk_size
            )
            if count == 0:
                logger.info(f"[*] No papers with status {current_status.name} to process")
                print(f"[*] No papers with status {current_status.name} to process")
                return
            logger.info(f"Received {count} papers with status {current_status.name} to process")
            # 遍历论文
            status_counter = Counter()
            with tqdm(total=count, desc=f"    Processing papers with status {current_status.name}",
                      unit=" paper", leave=False) as pbar:
                for paper_chunk in paper_generator:
                    # 检查是否收到终止信号
                    if shutdown_event.is_set():
                        logger.warning("Received termination signal, stopping batch process")
                        break
                    try:
                        # 处理论文
                        processed_papers = process_function(paper_chunk)
                        # 更新论文
                        for status, papers in processed_papers.items():
                            for paper in papers:
                                paper.status = status
                                if status < 300:  # 成功状态
                                    paper.retry_count = 0
                                elif paper.retry_count > configs.max_retries:
                                    paper.status = Status.PERMANENT_FAILED
                                else:
                                    paper.retry_count = paper.retry_count + 1
                                status_counter[status.name] += 1  # 状态计数
                            if papers:
                                updated = bulk_update_papers(
                                    session=session,
                                    papers=papers,
                                    chunk_size=len(papers)
                                )
                                logger.info(f"{updated} papers processed successfully")
                        # 提交事务
                        session.commit()
                        pbar.update(len(paper_chunk))
                    except Exception as e:
                        logger.error(f"Failed to process paper chunk")
                        logger.debug(f"Exception: {e}")
                        session.rollback()
                        pbar.update(len(paper_chunk))
            # 统计报告
            logger.info(f"Batch process report for {current_status.name}: {dict(status_counter)}")
            print(f"[*] Processed papers with status {current_status.name}")
            if not status_counter:
                print("    No papers processed")
            for status_name, cnt in status_counter.items():
                print(f"    {status_name}: {cnt}")
