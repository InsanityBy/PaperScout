# pipeline.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
import signal
import threading
from collections import Counter
from typing import Callable, Dict, List

from tqdm import tqdm

from paper_scout.core.config import configs
from paper_scout.database.crud import yield_papers, bulk_update_papers, bulk_create_papers
from paper_scout.database.database import init_database, SessionLocal
from paper_scout.database.model import Paper, Status
from paper_scout.service.analyzer import LLMAnalyzer
from paper_scout.service.parser import DOIParser
from paper_scout.service.fetcher import DBLPFetcher
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

    def __init__(self, start_year: int, end_year: int) -> None:
        init_database()
        self.fetcher = DBLPFetcher(start_year=start_year, end_year=end_year)
        self.parser = DOIParser()
        self.analyzer = LLMAnalyzer()
        self.uploader = ZoteroUploader()

    def run_all(self) -> None:
        """运行所有流程"""
        logger.info("-" * 50)
        logger.info("Start running all stages...")
        logger.info("Fetch -> Parse -> Analyze -> Upload")
        print("-" * 50)
        print("\nStart running all stages...")
        print("Fetch -> Parse -> Analyze -> Upload\n")
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
        # 上传论文
        self.run_upload_stage()
        if shutdown_event.is_set():
            return
        logger.info("=" * 50)
        logger.info("Finish processing")
        print("=" * 50)
        print("\nFinish processing")

    def run_fetch_stage(self) -> None:
        """获取论文"""
        logger.info("-" * 50)
        logger.info("[1/4] Start fetching papers...")
        print("-" * 50)
        print("\n[1/4] Start fetching papers...")
        saved_count = 0
        with SessionLocal() as session:
            for venue_name, papers_data in tqdm(
                    self.fetcher.fetch_all(), desc="    Fetching papers", unit=" venue", leave=False):
                if shutdown_event.is_set():
                    break
                count = bulk_create_papers(session=session, papers_data=papers_data)
                saved_count += count
                logger.info(f"[*] Fetched {len(papers_data)} papers from {venue_name}")
                tqdm.write(f"[*] Fetched {len(papers_data)} papers from {venue_name}")
            session.commit()
        logger.info(f"[1/4] Finish fetching papers, saved {saved_count} new papers")
        print(f"[1/4] Finish fetching papers, saved {saved_count} new papers\n")

    def run_parse_stage(self) -> None:
        """解析论文"""
        logger.info("-" * 50)
        logger.info("[2/4] Start parsing papers...")
        print("-" * 50)
        print("\n[2/4] Start parsing papers...")
        for status in [Status.PENDING_PARSE, Status.PARSE_FAILED, Status.DOI_INVALID]:
            self.batch_process(current_status=status, process_function=self.parser.parse_all)
        logger.info("[2/4] Finish parsing papers")
        print("[2/4] Finish parsing papers\n")

    def run_analyze_stage(self) -> None:
        """分析论文"""
        logger.info("-" * 50)
        logger.info("[3/4] Start analyzing papers...")
        print("-" * 50)
        print("\n[3/4] Start analyzing papers...")
        for status in [Status.PENDING_ANALYZE, Status.ANALYZE_FAILED]:
            self.batch_process(current_status=status, process_function=self.analyzer.analyze_all)
        logger.info("[3/4] Finish analyzing papers")
        print("[3/4] Finish analyzing papers\n")

    def run_upload_stage(self) -> None:
        """上传论文"""
        logger.info("-" * 50)
        logger.info("[4/4] Start uploading papers...")
        print("-" * 50)
        print("\n[4/4] Start uploading papers...")
        for status in [Status.PENDING_UPLOAD, Status.UPLOAD_FAILED]:
            self.batch_process(current_status=status, process_function=self.uploader.upload_all)
        logger.info("[4/4] Finish uploading papers")
        print("[4/4] Finish uploading papers\n")

    def batch_process(self,
                      current_status: Status,
                      process_function: Callable[[List[Paper]], Dict[Status, List[Paper]]]
                      ) -> None:
        """处理指定状态的论文"""
        with SessionLocal() as session:
            # 获取所有状态为current_status的论文
            chunk_size = configs.chunk_size
            count, paper_generator = yield_papers(
                session=session,
                filters={"status": current_status},
                chunk_size=chunk_size
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
                                if paper.retry_count > configs.max_retries:
                                    paper.status = Status.PERMANENT_FAILED
                                paper.status = status
                                if status < 300:  # 成功状态
                                    paper.retry_count = 0
                                else:   # 失败状态
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
