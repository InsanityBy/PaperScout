# parser.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Tuple
from urllib.parse import urljoin, quote

from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential

from paper_scout.core.config import configs
from paper_scout.core.constant import (
    CR_PERIOD,
    CR_RATE_LIMIT,
    OA_BATCH_RATE_LIMIT,
    OA_PERIOD,
    OA_SINGLE_RATE_LIMIT,
    S2_BATCH_RATE_LIMIT,
    S2_PERIOD,
    S2_SINGLE_RATE_LIMIT
)
from paper_scout.core.http_client import create_http_session
from paper_scout.database.model import Paper, Status


# 设置日志记录
logger = logging.getLogger(__name__)


class DOIParser:
    """DOI解析器"""

    def __init__(self) -> None:
        self.common_session = create_http_session()
        if configs.s2_api_key:
            self.s2_session = create_http_session(custom_headers={"x-api-key": configs.s2_api_key})
        else:
            self.s2_session = self.common_session

    def parse_all(self, papers: List[Paper]) -> Dict[Status, List[Paper]]:
        """批量解析获取论文详情"""
        if not papers:
            logger.warning("Papers not provided to parse details")
            return {}
        logger.info(f"Parsing details for {len(papers)} papers...")
        parsed_papers = {
            Status.PENDING_ANALYZE: [],
            Status.PARSE_FAILED: [],
            Status.DOI_INVALID: []
        }
        # 使用Crossref验证DOI
        papers_dict = {paper.doi: paper for paper in papers}
        cr_verified, cr_invalid, cr_failed = self._verify_by_cr(papers=papers_dict)
        if cr_invalid:
            parsed_papers[Status.DOI_INVALID].extend(cr_invalid.values())
            logger.warning(f"{len(cr_invalid)} papers not passed Crossref verification")
        if cr_failed:
            parsed_papers[Status.PARSE_FAILED].extend(cr_failed.values())
            logger.warning(f"Failed to verify {len(cr_failed)} papers using Crossref")
        if not cr_verified:
            logger.error(f"No papers passed Crossref verification")
            return parsed_papers
        logger.info(f"{len(cr_verified)} papers passed Crossref verification successfully")
        # 优先使用Semantic Scholar获取论文详情
        s2_parsed, s2_failed = self._parse_by_s2(papers=cr_verified)
        parsed_papers[Status.PENDING_ANALYZE].extend(s2_parsed.values())
        # 使用OpenAlex获取失败论文的详情
        if s2_failed:
            logger.warning(f"Failed to parse {len(s2_failed)} papers using Semantic Scholar")
            logger.info(f"Retrying to parse {len(s2_failed)} papers using OpenAlex...")
            oa_parsed, oa_failed = self._parse_by_oa(papers=s2_failed)
            parsed_papers[Status.PENDING_ANALYZE].extend(oa_parsed.values())
            if oa_failed:
                parsed_papers[Status.PARSE_FAILED].extend(oa_failed.values())
                logger.warning(f"Failed to parse {len(oa_failed)} papers using OpenAlex")
        if not parsed_papers[Status.PENDING_ANALYZE]:
            logger.error(f"Failed to parse any papers")
            return parsed_papers
        logger.info(f"{len(parsed_papers[Status.PENDING_ANALYZE])} papers parsed successfully")
        return parsed_papers

    def _verify_by_cr(self,
                      papers: Dict[str, Paper]
                      ) -> Tuple[Dict[str, Paper], Dict[str, Paper], Dict[str, Paper]]:
        """使用Crossref验证DOI"""
        logger.info(f"Verifying {len(papers)} papers using Crossref...")
        verified_papers = {}
        invalid_papers = {}
        failed_papers = {}
        # 并发处理
        with ThreadPoolExecutor(max_workers=configs.max_concurrent_workers) as executor:
            # 提交任务
            future_verify = {
                executor.submit(self._verify_doi, doi): doi
                for doi in papers.keys()
            }
            # 处理完成的任务
            for future in as_completed(future_verify):
                doi = future_verify[future]
                try:
                    if future.result():
                        verified_papers[doi] = papers[doi]
                    else:
                        invalid_papers[doi] = papers[doi]
                except Exception as e:
                    failed_papers[doi] = papers[doi]
                    logger.error(f"Failed to verify paper with DOI: {doi}")
                    logger.debug(f"Exception: {e}")
        return verified_papers, invalid_papers, failed_papers

    def _parse_by_s2(self, papers: Dict[str, Paper]) -> Tuple[Dict[str, Paper], Dict[str, Paper]]:
        """使用Semantic Scholar解析获取论文详情"""
        return self._parse_common(
            papers=papers,
            source_name="Semantic Scholar",
            has_api_key=bool(configs.s2_api_key),
            batch_limit=configs.s2_batch_limit,
            batch_func=self._batch_parse_by_s2,
            single_func=self._single_parse_by_s2
        )

    def _parse_by_oa(self, papers: Dict[str, Paper]) -> Tuple[Dict[str, Paper], Dict[str, Paper]]:
        """使用OpenAlex解析获取论文详情"""
        return self._parse_common(
            papers=papers,
            source_name="OpenAlex",
            has_api_key=bool(configs.oa_api_key),
            batch_limit=configs.oa_batch_limit,
            batch_func=self._batch_parse_by_oa,
            single_func=self._single_parse_by_oa
        )

    def _parse_common(self,
                      papers: Dict[str, Paper],
                      source_name: str,
                      has_api_key: bool,
                      batch_limit: int,
                      batch_func: Callable[[List[str]], Dict[str, Paper]],
                      single_func: Callable[[str], Paper]
                      ) -> Tuple[Dict[str, Paper], Dict[str, Paper]]:
        """通用解析方法: 批量请求 -> 降级单条并发"""
        logger.info(f"Parsing details for {len(papers)} papers using {source_name}...")
        parsed_papers = {}
        failed_papers = {}
        dois = list(papers.keys())
        # 配置API密钥尝试使用批量接口
        if has_api_key:
            logger.info(f"API key found, using batch fetch...")
            successful_dois = set()
            for i in range(0, len(dois), batch_limit):
                batch_dois = dois[i:i + batch_limit]
                try:
                    results_dict = batch_func(batch_dois)
                except Exception as e:
                    logger.error(f"Failed to parse details for {len(batch_dois)} papers")
                    logger.debug(f"Exception: {e}")
                    continue
                # 更新成功的论文
                for doi in batch_dois:
                    result = results_dict.get(doi)
                    paper = papers.get(doi)
                    if paper and result and self._update_paper(paper=paper, data=result):
                        parsed_papers[doi] = paper
                        successful_dois.add(doi)
            # 过滤失败论文的DOI
            dois = [doi for doi in dois if doi not in successful_dois]
            if dois:
                logger.warning(f"Failed to parse {len(dois)} papers using batch fetch")
        else:
            logger.warning(f"API key not found")
        # 未配置API密钥或未成功的论文使用单条查询接口并发处理
        if dois:
            logger.info(f"Downgrading to single fetch...")
            with ThreadPoolExecutor(max_workers=configs.max_concurrent_workers) as executor:
                future_fetch = {
                    executor.submit(single_func, doi): doi
                    for doi in dois
                }
                for future in as_completed(future_fetch):
                    doi = future_fetch[future]
                    paper = papers[doi]
                    try:
                        result = future.result()
                        if self._update_paper(paper=paper, data=result):
                            parsed_papers[doi] = paper
                        else:
                            failed_papers[doi] = paper
                    except Exception as e:
                        failed_papers[doi] = paper
                        logger.error(f"Failed to parse details for paper with DOI: {doi}")
                        logger.debug(f"Exception: {e}")
        return parsed_papers, failed_papers

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=CR_RATE_LIMIT, period=CR_PERIOD)
    def _verify_doi(self, doi: str) -> bool:
        """验证DOI是否有效"""
        base_url = configs.cr_base_url
        full_url = urljoin(base_url, f"works/doi/{doi}")
        response = self.common_session.get(full_url, timeout=configs.request_timeout)
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=S2_BATCH_RATE_LIMIT, period=S2_PERIOD)
    def _batch_parse_by_s2(self, dois: List[str]) -> Dict[str, Dict[str, str]]:
        """使用Semantic Scholar批量查询接口解析获取论文详情"""
        base_url = configs.s2_base_url
        full_url = urljoin(base_url, "graph/v1/paper/batch")
        response = self.s2_session.post(
            full_url,
            json={"ids": dois},
            params={"fields": "title,abstract"},
            timeout=configs.request_timeout
        )
        response.raise_for_status()
        # 提取数据
        data = {}
        results = response.json()
        for doi, result in zip(dois, results):
            if result:
                data[doi] = {
                    "title": result.get("title") or "",
                    "abstract": result.get("abstract") or ""
                }
            else:
                data[doi] = {
                    "title": "",
                    "abstract": ""
                }
        return data

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=S2_SINGLE_RATE_LIMIT, period=S2_PERIOD)
    def _single_parse_by_s2(self, doi: str) -> Dict[str, str]:
        """使用Semantic Scholar单条查询接口解析获取论文详情"""
        base_url = configs.s2_base_url
        full_url = urljoin(base_url, f"graph/v1/paper/{quote(doi)}")
        response = self.common_session.get(
            full_url,
            params={"fields": "title,abstract"},
            timeout=configs.request_timeout
        )
        response.raise_for_status()
        # 提取数据
        result = response.json()
        data = {
            "title": result.get("title") or "",
            "abstract": result.get("abstract") or ""
        }
        return data

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=OA_BATCH_RATE_LIMIT, period=OA_PERIOD)
    def _batch_parse_by_oa(self, dois: List[str]) -> Dict[str, Dict[str, str]]:
        """使用OpenAlex批量查询接口解析获取论文详情"""
        base_url = configs.oa_base_url
        full_url = urljoin(base_url, "works")
        doi_filter = "|".join(f"https://doi.org/{doi}" for doi in dois)
        response = self.common_session.get(
            full_url,
            params={
                "filter": f"doi:{doi_filter}",
                "per_page": f"{len(dois)}",
                "select": "doi,title,abstract_inverted_index",
                "api_key": f"{configs.oa_api_key}"
            },
            timeout=configs.request_timeout
        )
        response.raise_for_status()
        # 提取数据, 忽略DOI大小写
        data = {doi.lower(): {"title": "", "abstract": ""} for doi in dois}
        dois_mapping = {doi.lower(): doi for doi in dois}
        results = response.json().get("results", [])
        for result in results:
            doi = result.get("doi", "").replace("https://doi.org/", "").lower()
            data[dois_mapping.get(doi, doi)] = {
                "title": result.get("title") or "",
                "abstract": self._reconstruct_abstract(
                    text=result.get("abstract_inverted_index") or {})
            }
        return data

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=OA_SINGLE_RATE_LIMIT, period=OA_PERIOD)
    def _single_parse_by_oa(self, doi: str) -> Dict[str, str]:
        """使用OpenAlex单条查询接口解析获取论文详情"""
        base_url = configs.oa_base_url
        full_url = urljoin(base_url, "works")
        full_url = f"{full_url}/https://doi.org/{quote(doi)}"
        response = self.common_session.get(
            full_url,
            params={"select": "title,abstract_inverted_index"},
            timeout=configs.request_timeout
        )
        response.raise_for_status()
        # 提取数据
        result = response.json()
        data = {
            "title": result.get("title") or "",
            "abstract": self._reconstruct_abstract(
                text=result.get("abstract_inverted_index") or {})
        }
        return data

    def _update_paper(self, paper: Paper, data: Dict[str, str]) -> bool:
        """更新论文"""
        if not data:
            logger.warning(f"Empty data for paper with DOI: {paper.doi}")
            return False
        title = data.get("title", "")
        abstract = self._clean_abstract(text=data.get("abstract", ""))
        if title and abstract:
            paper.title = title
            paper.abstract = abstract
            return True
        else:
            logger.warning(f"Title or abstract missing for paper with DOI: {paper.doi}")
            return False

    @staticmethod
    def _clean_abstract(text: str) -> str:
        """清理摘要"""
        if not text:
            return ""
        return " ".join(re.sub(r"<[^>]+>", "", text).split())

    @staticmethod
    def _reconstruct_abstract(text: dict) -> str:
        """重构摘要"""
        if not text:
            return ""
        word_positions = []
        for word, positions in text.items():
            for position in positions:
                word_positions.append((position, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join([word for _, word in word_positions])

    def __del__(self) -> None:
        self.common_session.close()
        self.s2_session.close()
