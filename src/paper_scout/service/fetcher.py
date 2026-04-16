# fetcher.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Tuple
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from bs4.element import Tag
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential

from paper_scout.core.config import configs
from paper_scout.core.constant import (
    ARXIV_LARGE_FETCH_THRESHOLD,
    ARXIV_PERIOD,
    ARXIV_RATE_LIMIT,
    DBLP_PAPER_RULE,
    DBLP_PERIOD,
    DBLP_RATE_LIMIT,
    DBLP_VENUE_RULE,
    PSEUDO_DOI_PREFIX
)
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

    def __enter__(self) -> "DBLPFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """关闭HTTP会话资源"""
        self.session.close()

    def fetch_all(self) -> Iterator[Tuple[str, List[Dict[str, int | Status | str | VenueType]]]]:
        """获取所有出处的指定时间范围内的论文"""
        logger.info(f"Fetching papers from all venues: {self.start_year} to {self.end_year}...")
        total_fetched = 0
        # 每种出处类型
        for venue_type, urls in configs.venues.items():
            # 跳过arXiv
            if venue_type == VenueType.ARXIV:
                continue
            # 检查出处类型是否支持
            if venue_type not in self.venue_rules or venue_type not in self.paper_rules:
                logger.warning(f"Unsupported venue type: {venue_type}")
                continue
            # 检查出处类型是否提供URL
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


class ArxivFetcher:
    """arXiv论文获取器"""

    def __init__(self,
                 start_year: int = 2024,
                 end_year: int = 2025,
                 start_date: str | None = None,
                 end_date: str | None = None) -> None:
        self.start_year = start_year
        self.end_year = end_year
        self.start_date = start_date  # YYYYMMDDhhmm
        self.end_date = end_date      # YYYYMMDDhhmm
        self.mode = "date_range" if (start_date and end_date) else "recent"
        self.session = create_http_session()

    @property
    def cutoff_date(self) -> datetime:
        """截止日期"""
        return datetime.now(timezone.utc) - timedelta(
            days=configs.arxiv_max_lookback_days
        )

    def __enter__(self) -> "ArxivFetcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """关闭HTTP会话资源"""
        self.session.close()

    def fetch_all(self) -> Iterator[Tuple[str, List[Dict[str, int | Status | str | VenueType]]]]:
        """获取所有分类的指定时间范围内的论文"""
        logger.info(f"Fetching papers from arXiv: {self.start_year} to {self.end_year}...")
        total_fetched = 0
        # 每种出处类型
        for venue_type, categories in configs.venues.items():
            # 跳过其他出处类型, 只处理arXiv
            if venue_type != VenueType.ARXIV:
                continue
            # 检查arXiv是否提供分类
            if not categories:
                logger.warning(f"Categories for {venue_type} not provided to fetch")
                continue
            # arXiv的每种分类
            for category in categories:
                for papers in self._fetch_category(category=category):
                    if papers:
                        total_fetched += len(papers)
                        yield f"arXiv:{category}", papers
        if total_fetched == 0:
            logger.error("Failed to fetch papers from arXiv")
        else:
            logger.info(f"{total_fetched} papers from arXiv fetched successfully")

    def _fetch_category(self, category: str) -> Iterator[List[Dict[str, int | Status | str | VenueType]]]:
        """获取单个分类的论文"""
        logger.info(f"Fetching papers from arXiv:{category} (mode={self.mode})...")
        start = 0
        total_fetched_in_category = 0
        threshold_prompted = False
        # 构建查询
        if self.mode == "date_range":
            search_query = f"cat:{category} AND submittedDate:[{self.start_date} TO {self.end_date}]"
        else:
            search_query = f"cat:{category}"
        # 分页获取
        while True:
            # 构建查询参数
            params = {
                "search_query": search_query,
                "start": start,
                "max_results": configs.arxiv_batch_limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending"
            }
            full_url = urljoin(configs.arxiv_base_url, "api/query")
            query_url = f"{full_url}?{urlencode(params)}"
            # 尝试获取XML数据
            try:
                xml_data = self._fetch_xml(url=query_url)
                papers, should_continue = self._parse_arxiv_xml(
                    xml_data=xml_data, category=category)
                if papers:
                    total_fetched_in_category += len(papers)
                    yield papers
                else:  # 没有更多数据停止翻页
                    logger.info(f"No more papers for arXiv:{category} at index {start}")
                    break
                # 数据量检查, 仅提示一次
                if not threshold_prompted and total_fetched_in_category >= ARXIV_LARGE_FETCH_THRESHOLD:
                    threshold_prompted = True
                    logger.warning(f"Fetched {total_fetched_in_category} papers from arXiv:{category}, "
                                   f"exceeding threshold {ARXIV_LARGE_FETCH_THRESHOLD}")
                    confirm = input(f"\n[!] Already fetched {total_fetched_in_category} papers from "
                                    f"arXiv:{category}, continue? [y/N]: ").strip().lower()
                    if confirm != "y":
                        logger.info(f"User stopped fetching arXiv:{category}")
                        break
                # recent模式: 早于截止日期停止翻页
                if self.mode == "recent" and not should_continue:
                    logger.info(f"Reached cutoff date {self.cutoff_date} at index {start}")
                    break
                # date_range模式: API已无更多结果时停止
                if self.mode == "date_range" and not should_continue:
                    logger.info(f"No more papers in date range at index {start}")
                    break
                # 继续翻页
                start += configs.arxiv_batch_limit
            except Exception as e:
                logger.error(f"Failed to fetch arXiv:{category} at index {start}")
                logger.debug(f"Exception: {e}")
                break

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=ARXIV_RATE_LIMIT, period=ARXIV_PERIOD)
    def _fetch_xml(self, url: str) -> str:
        """获取XML内容"""
        if not url:
            raise ValueError(f"Empty URL string: {url}")
        # 发送GET请求
        response = self.session.get(url, timeout=configs.request_timeout)
        response.raise_for_status()
        return response.text

    def _parse_arxiv_xml(self,
                         xml_data: str,
                         category: str
                         ) -> Tuple[List[Dict[str, int | Status | str | VenueType]], bool]:
        """解析XML内容"""
        papers_data = []
        # 转换为可遍历的元素树
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML for arXiv:{category}")
            logger.debug(f"Exception: {e}")
            return [], False
        # 定义命名空间, arXiv XML使用Atom命名空间
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        # 提取所有条目
        entries = root.findall("atom:entry", ns)
        if not entries:
            return [], False
        should_continue = True
        for entry in entries:
            # 提取发布日期
            published_tag = entry.find("atom:published", ns)
            if published_tag is None or not published_tag.text:
                continue
            try:
                published_date = datetime.strptime(
                    published_tag.text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError as e:
                logger.warning(f"Invalid date format: {published_tag.text}, skipped")
                continue
            if self.mode == "recent" and published_date < self.cutoff_date:
                should_continue = False
                break
            # 提取年份
            year = published_date.year
            if self.mode == "date_range" and year < self.start_year:  # 当前论文年份小于起始年份, 跳过当前论文, 停止后续获取
                should_continue = False
                break
            if self.mode == "date_range" and year > self.end_year:  # 当前论文年份大于结束年份, 跳过当前论文, 继续向后获取
                continue
            # 提取arXiv ID作为DOI
            id_tag = entry.find("atom:id", ns)
            if id_tag is None:
                logger.warning(f"Empty ID, skipped")
                continue
            arxiv_id = id_tag.text.split("/abs/")[-1].split("v")[0]
            doi_key = f"arxiv:{arxiv_id}"
            # 提取标题
            title_tag = entry.find("atom:title", ns)
            if title_tag is None:
                logger.warning(f"Empty title, skipped")
                continue
            title = title_tag.text.replace("\n", " ").strip()
            # 提取摘要
            summary_tag = entry.find("atom:summary", ns)
            if summary_tag is None:
                logger.warning(f"Empty abstract, skipped")
                continue
            abstract = self._clean_abstract(summary_tag.text)
            papers_data.append({
                "doi": doi_key,
                "title": title,
                "abstract": abstract,
                "year": year,
                "venue_type": VenueType.ARXIV,
                "venue_name": f"arXiv:{category}",
                "status": Status.PENDING_ANALYZE,
                "retry_count": 0
            })
        return papers_data, should_continue

    @staticmethod
    def _clean_abstract(text: str) -> str:
        """清理摘要"""
        if not text:
            return ""
        return " ".join(re.sub(r"<[^>]+>", "", text).split())


def create_arxiv_fetcher(start_year: int, end_year: int) -> ArxivFetcher | None:
    """创建ArxivFetcher, 检测日期冲突并提示用户选择"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=configs.arxiv_max_lookback_days)
    start_of_year = datetime(start_year, 1, 1, tzinfo=timezone.utc)
    # 检测冲突: start_year早于cutoff_date
    if start_of_year < cutoff_date:
        logger.warning(f"Date conflict: start_year={start_year} is before "
                       f"cutoff_date={cutoff_date.strftime('%Y-%m-%d')} "
                       f"(lookback_days={configs.arxiv_max_lookback_days})")
        print(f"\n[!] arXiv date conflict detected:")
        print(f"    start_year={start_year}, but arXiv lookback is only "
              f"{configs.arxiv_max_lookback_days} days "
              f"(cutoff: {cutoff_date.strftime('%Y-%m-%d')})")
        print(f"    [1] Fetch recent {configs.arxiv_max_lookback_days} days only (default)")
        print(f"    [2] Enter precise date range (submittedDate query)")
        print(f"    [3] Skip arXiv fetching")
        choice = input("    Your choice [1/2/3]: ").strip()
        if choice == "2":
            start_input = input("    Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("    Enter end date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_input, "%Y-%m-%d").strftime("%Y%m%d0000")
                end_date = datetime.strptime(end_input, "%Y-%m-%d").strftime("%Y%m%d2359")
                logger.info(f"User chose date_range mode: {start_input} to {end_input}")
                return ArxivFetcher(start_year=start_year, end_year=end_year,
                                    start_date=start_date, end_date=end_date)
            except ValueError:
                logger.error(f"Invalid date format: {start_input} / {end_input}")
                print("    Invalid date format, falling back to recent mode.")
                return ArxivFetcher(start_year=start_year, end_year=end_year)
        elif choice == "3":
            logger.info("User chose to skip arXiv fetching")
            print("    arXiv fetching skipped.")
            return None
        else:
            logger.info("User chose recent mode (default)")
            return ArxivFetcher(start_year=start_year, end_year=end_year)
    # 无冲突, 直接创建
    return ArxivFetcher(start_year=start_year, end_year=end_year)


def merged_fetcher(
    dblp_fetcher: DBLPFetcher,
    arxiv_fetcher: ArxivFetcher | None
) -> Iterator[Tuple[str, List[Dict[str, int | Status | str | VenueType]]]]:
    """合并多个Fetcher的迭代器, 按顺序产生论文"""
    # DBLP论文
    for venue_name, papers in dblp_fetcher.fetch_all():
        yield venue_name, papers
    # arXiv论文
    if arxiv_fetcher is not None:
        for venue_name, papers in arxiv_fetcher.fetch_all():
            yield venue_name, papers
