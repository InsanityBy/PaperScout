# fetcher.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import hashlib
import logging
import re
from typing import Dict, Iterator, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from bs4.element import Tag
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential

from paper_scout.core.config import configs
from paper_scout.core.constant import (
    DBLP_PAPER_RULE, DBLP_PERIOD, DBLP_RATE_LIMIT, DBLP_VENUE_RULE, PSEUDO_DOI_PREFIX)
from paper_scout.core.http_client import create_http_session
from paper_scout.database.model import Status, VenueType


# 设置日志记录
logger = logging.getLogger(__name__)

# 预编译DOI正则表达式
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+")


class DBLPFetcher:
    """DBLP论文获取器"""

    def __init__(self, start_year: int = 2024, end_year: int = 2025) -> None:
        self.start_year = start_year
        self.end_year = end_year
        self.session = create_http_session()
        self.venue_rules = DBLP_VENUE_RULE
        self.paper_rules = DBLP_PAPER_RULE

    def fetch_all(self) -> Iterator[Tuple[str, List[Dict[str, int | Status | str | VenueType]]]]:
        """获取所有出处的指定时间范围内的论文"""
        logger.info(f"Fetching papers from all venues: {self.start_year} to {self.end_year}...")
        # 每种出处类型
        total_fetched = 0
        for venue_type, urls in configs.venues.items():
            if venue_type not in self.venue_rules or venue_type not in self.paper_rules:
                logger.warning(f"Unsupported venue type: {venue_type}")
                continue
            if not urls:
                logger.warning(f"URLs for {venue_type} not provided to fetch")
                continue
            # 每种出处类型下的每个出处
            for venue_name, url in urls.items():
                for papers in self._fetch_single_venue(
                    venue_type=venue_type,
                    venue_name=venue_name,
                    venue_url=url
                ):
                    if papers:
                        total_fetched += len(papers)
                        yield venue_name, papers
        if total_fetched == 0:
            logger.error("Failed to fetch papers from all venues")
        else:
            logger.info(f"{total_fetched} papers from all venues fetched successfully")

    def _fetch_single_venue(self,
                            venue_type: str,
                            venue_name: str,
                            venue_url: str
                            ) -> Iterator[List[Dict[str, int | Status | str | VenueType]]]:
        """获取单个出处的论文"""
        logger.info(f"Fetching papers from {venue_name}...")
        try:
            # 获取并解析XML
            soup = BeautifulSoup(self._fetch_xml(url=venue_url), "xml")
            # 获取解析规则
            rule = self.venue_rules.get(venue_type)
            if not rule.get("tag"):
                logger.error(f"Tag not found in venue rule for {venue_type}")
                yield []
            # 遍历XML中的每个条目
            total_fetched = 0
            for item in soup.find_all(rule["tag"]):
                papers = self._fetch_venue_item(
                    item=item,
                    rule=rule,
                    venue_type=venue_type,
                    venue_name=venue_name
                )
                if papers:
                    total_fetched += len(papers)
                    yield papers
            if total_fetched == 0:
                logger.error(f"Failed to fetch papers from {venue_name}")
                yield []
            else:
                logger.info(f"{total_fetched} papers from {venue_name} fetched successfully")
        except Exception as e:
            logger.error(f"Failed to fetch papers from {venue_name}")
            logger.debug(f"Exception: {e}")
            yield []

    def _fetch_venue_item(self,
                          item: Tag,
                          rule: Dict[str, str],
                          venue_type: str,
                          venue_name: str
                          ) -> List[Dict[str, int | Status | str | VenueType]]:
        """获取单个出处单个年份的论文"""
        # 提取年份
        year_string = self._extract_year_string(item=item, rule=rule)
        if not year_string:
            logger.info(f"Year not found for item of {venue_name}")
            return []
        year = int(year_string)
        if not (self.start_year <= year <= self.end_year):
            logger.info(
                f"{year} of {venue_name} out of range [{self.start_year}, {self.end_year}]")
            return []
        # 提取链接
        link = self._extract_link(item=item, rule=rule)
        if not link:
            logger.info(f"Link not found for {year} of {venue_name}")
            return []
        logger.info(f"Fetching papers from {year} of {venue_name}...")
        # 获取链接对应的论文
        try:
            papers = self._fetch_papers(
                link=link,
                venue_type=venue_type,
                venue_name=venue_name,
                year=year
            )
            if not papers:
                logger.error(f"Failed to fetch papers from {year} of {venue_name}")
                return []
            else:
                logger.info(
                    f"{len(papers)} papers from {year} of {venue_name} fetched successfully")
                return papers
        except Exception as e:
            logger.error(f"Failed to fetch papers from {year} of {venue_name}")
            logger.debug(f"Exception: {e}")
            return []

    def _fetch_papers(self,
                      link: str,
                      venue_type: str,
                      venue_name: str,
                      year: int
                      ) -> List[Dict[str, int | Status | str | VenueType]]:
        """获取具体论文"""
        # 获取并解析XML
        soup = BeautifulSoup(self._fetch_xml(url=link), "xml")
        # 获取解析规则
        rule = self.paper_rules.get(venue_type)
        # 遍历XML中的每个条目
        papers_data = []
        for paper in soup.find_all(rule):
            # 提取标题
            title_tag = paper.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            else:
                title = "Unknown Title"
                logger.warning(f"Empty title: {paper}, using default title: {title}")
            # 提取DOI
            doi_tag = paper.find("ee")
            doi = ""
            if doi_tag:
                doi_text = doi_tag.get_text(strip=True)
                doi_matched = DOI_PATTERN.search(doi_text)
                if doi_matched:
                    doi = doi_matched.group(0)
            # 处理DOI
            if doi:
                status = Status.PENDING_PARSE
            elif title != "Unknown Title":  # 没有DOI, 有标题
                doi = self._generate_pseudo_doi(title=title)
                status = Status.PENDING_PARSE
                logger.warning(f"Empty DOI: {paper}, using pseudo DOI: {doi}")
            else:
                logger.warning(f"Empty title and DOI: {paper}, skipped")
                continue
            # 保存新论文
            papers_data.append({
                "doi": doi,
                "title": title,
                "abstract": "",
                "year": year,
                "venue_type": VenueType(venue_type),
                "venue_name": venue_name,
                "status": status,
                "retry_count": 0
            })
        return papers_data

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=DBLP_RATE_LIMIT, period=DBLP_PERIOD)
    def _fetch_xml(self, url: str) -> str:
        """获取XML内容"""
        if not url:
            raise ValueError(f"Empty URL string: {url}")
        # 构建完整URL
        full_url = urljoin(configs.dblp_base_url, url)
        # 解析URL
        parsed_url = urlparse(full_url)
        # 转换.html为.xml
        path = parsed_url.path
        if path.endswith(".html"):
            new_path = path[:-5] + ".xml"
            full_url = urlunparse(parsed_url._replace(path=new_path))
        # 发送GET请求
        response = self.session.get(full_url, timeout=configs.request_timeout)
        response.raise_for_status()
        # 关闭session
        self.session.close()
        return response.text

    @staticmethod
    def _extract_year_string(item: Tag, rule: Dict[str, str]) -> str:
        """提取年份"""
        # 提取可能包含年份的文本
        year_text = ""
        if rule.get("year_attr"):
            attr_value = item.get(rule["year_attr"], "")
            if attr_value and isinstance(attr_value, str):
                year_text = attr_value.strip()
            else:
                year_text = item.get_text(strip=True)
        elif rule.get("year_tag"):
            year_tag = item.find(rule["year_tag"])
            if year_tag:
                year_text = year_tag.get_text(strip=True)
        else:
            year_text = item.get_text(strip=True)
        # 提取年份
        match = re.search(r"(\d{4})", year_text)
        if not match:
            return ""
        return match.group(1)

    @staticmethod
    def _extract_link(item: Tag, rule: Dict[str, str]) -> str:
        """提取链接"""
        if rule.get("link_attr"):
            attr_value = item.get(rule["link_attr"])
            if attr_value and isinstance(attr_value, str):
                return attr_value.strip()
        if rule.get("link_tag"):
            link_tag = item.find(rule["link_tag"])
            if link_tag:
                return link_tag.get_text(strip=True)
        return ""

    @staticmethod
    def _generate_pseudo_doi(title: str) -> str:
        """生成伪DOI, 使用标题的SHA256哈希值"""
        hash_str = hashlib.sha256(title.lower().encode("utf-8")).hexdigest()
        return f"{PSEUDO_DOI_PREFIX}{hash_str}"
