# analyzer.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential

from paper_scout.core.config import configs
from paper_scout.core.constant import LLM_PERIOD, LLM_RATE_LIMIT
from paper_scout.database.model import Paper, Status


# 设置日志记录
logger = logging.getLogger(__name__)


class PaperAnalysisResult(BaseModel):
    """论文分析结果"""

    title_cn: str = ""
    abstract_cn: str = ""
    relevance_score: float = Field(ge=0.0, le=10.0, default=0.0)
    relevance_reason: str = ""
    keywords: List[str] = []


class LLMAnalyzer:
    """LLM分析器"""

    def __init__(self) -> None:
        # 创建instructor包装的OpenAI客户端
        self.client = instructor.from_openai(
            OpenAI(api_key=configs.llm_api_key, base_url=configs.llm_base_url),
            mode=instructor.Mode.JSON
        )
        # 获取LLM设置
        self.llm_settings = self._build_llm_settings()
        # 获取标签
        tags = configs.tags
        self.valid_tags = {tag for tag_list in configs.tags.values() for tag in tag_list}
        # 获取用户兴趣
        user_interests = configs.user_interests
        # 创建系统提示词
        self.system_prompt = (configs.system_prompt
                              .replace("{USER_INTERESTS}", user_interests)
                              .replace("{TAGS}", f"{tags}")
                              )

    def analyze_all(self, papers: List[Paper]) -> Dict[Status, List[Paper]]:
        """批量分析论文"""
        if not papers:
            logger.warning("Papers not provided to analyze")
            return {}
        logger.info(f"Analyzing {len(papers)} papers...")
        analyzed_papers = {
            Status.PENDING_FILTER: [],
            Status.ANALYZE_FAILED: []
        }
        # 分析论文
        papers_dict = {paper.doi: paper for paper in papers}
        analyzed, failed = self._analyze_papers(papers=papers_dict)
        analyzed_papers[Status.PENDING_FILTER].extend(analyzed.values())
        if failed:
            analyzed_papers[Status.ANALYZE_FAILED].extend(failed.values())
            logger.warning(f"Failed to analyze {len(failed)} papers")
        if not analyzed:
            logger.error("Failed to analyze any paper")
            return analyzed_papers
        logger.info(f"{len(analyzed)} papers analyzed successfully")
        return analyzed_papers

    def _analyze_papers(self,
                        papers: Dict[str, Paper]
                        ) -> Tuple[Dict[str, Paper], Dict[str, Paper]]:
        """并发分析论文"""
        logger.info(f"Analyzing {len(papers)} papers...")
        analyzed_papers = {}
        failed_papers = {}
        with ThreadPoolExecutor(max_workers=configs.max_concurrent_workers) as executor:
            # 提交任务
            future_analyze = {
                executor.submit(self._single_analyze, paper): doi
                for doi, paper in papers.items()
            }
            # 处理完成的任务
            for future in as_completed(future_analyze):
                doi = future_analyze[future]
                paper = papers[doi]
                try:
                    result = future.result()
                    if self._update_paper(paper=paper, data=result):
                        analyzed_papers[doi] = paper
                    else:
                        failed_papers[doi] = paper
                except Exception as e:
                    failed_papers[doi] = paper
                    logger.error(f"Failed to analyze paper with DOI: {doi}")
                    logger.debug(f"Exception: {e}")
        return analyzed_papers, failed_papers

    def _single_analyze(self, paper: Paper) -> PaperAnalysisResult:
        """分析单篇论文"""
        # 创建用户提示词
        user_prompt = f"Title: {paper.title}\nAbstract: {paper.abstract}"
        # 调用LLM
        response = self._call_llm_api(user_prompt=user_prompt)
        return response

    @retry(stop=stop_after_attempt(configs.max_retries),
           wait=wait_exponential(multiplier=2, min=2, max=configs.request_timeout))
    @sleep_and_retry
    @limits(calls=LLM_RATE_LIMIT, period=LLM_PERIOD)
    def _call_llm_api(self, user_prompt: str) -> PaperAnalysisResult:
        """调用LLM API分析论文"""
        response_generator = self.client.chat.completions.create_partial(
            response_model=PaperAnalysisResult,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_retries=0,
            model=configs.llm_model,
            timeout=configs.request_timeout,
            **self.llm_settings
        )
        final_result = None
        for partial_result in response_generator:
            final_result = partial_result
        return final_result

    def _update_paper(self, paper: Paper, data: PaperAnalysisResult) -> bool:
        """更新论文"""
        if not data:
            logger.warning(f"Empty data for paper with DOI: {paper.doi}")
            return False
        # 检查并过滤非法标签
        valid_keywords = [
            keyword for keyword in data.keywords if keyword in self.valid_tags
        ]
        # 更新论文
        paper.title_cn = data.title_cn
        paper.abstract_cn = data.abstract_cn
        paper.relevance_score = data.relevance_score
        paper.relevance_reason = data.relevance_reason
        paper.tags_json = json.dumps(valid_keywords, ensure_ascii=False)
        return True

    def _build_llm_settings(self) -> Dict[str, Any]:
        """构建不同OpenAI兼容供应商的额外请求参数"""
        provider = configs.llm_provider
        mode = configs.llm_thinking_mode
        effort = configs.llm_reasoning_effort
        budget = configs.llm_thinking_budget
        settings = {}
        extra_body = {}
        # 处理不同供应商
        if provider == "deepseek":
            # DeepSeek不支持思考模式设置为auto
            # auto对应默认模式, 默认启用思考
            if mode != "auto":
                extra_body["thinking"] = {"type": mode}
            # 思考模式启用, 设置思考强度
            if mode != "disabled":
                settings["reasoning_effort"] = effort
        elif provider == "qwen":
            # Qwen不支持思考模式设置为auto
            # auto对应默认模式, 默认启用思考
            if mode != "auto":
                extra_body["enable_thinking"] = (mode == "enabled")
            # 思考模式启用, 设置思考长度
            if mode != "disabled" and budget is not None:
                extra_body["thinking_budget"] = budget
        elif provider in {"kimi", "glm"}:
            # Kimi和GLM不支持思考模式设置为auto
            # auto对应默认模式, 默认启用思考
            # Kimi和GLM不支持思考强度和长度设置
            if mode != "auto":
                extra_body["thinking"] = {"type": mode}
        elif provider == "seed":
            # Seed支持思考模式设置为auto
            extra_body["thinking"] = {"type": mode}
            # 思考模式启用, 设置思考强度
            if mode != "disabled":
                settings["reasoning_effort"] = effort
        # 添加额外参数
        if extra_body:
            settings["extra_body"] = extra_body
        return settings
