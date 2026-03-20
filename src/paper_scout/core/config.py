# config.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

import os
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from pydantic import PositiveInt, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource
)

from paper_scout.core.constant import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONFIG_DIRECTORY,
    DEFAULT_MAX_CONCURRENT_WORKERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    OA_MAX_BATCH_LIMIT,
    S2_MAX_BATCH_LIMIT,
    ZOTERO_MAX_BATCH_LIMIT
)


# 配置目录
config_directory = Path(os.getenv("CONFIG_DIRECTORY", DEFAULT_CONFIG_DIRECTORY)).resolve()
print(f"[INFO] Config directory: {config_directory}")
# 配置文件路径
config_file_path = config_directory / "configs.yaml"
print(f"[INFO] Config file path: {config_file_path}")
# 检查配置文件是否存在
if not config_file_path.exists():
    print(f"[CRITICAL] File not found: {config_file_path}")
    sys.exit(1)


def _load_yaml(file_path: Path) -> Dict:
    """加载YAML文件"""
    # 检查文件是否存在
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    # 加载文件
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class AppConfig(BaseSettings):
    """应用配置"""

    # 凭证配置(.env)
    # LLM配置
    llm_api_key: str = ""
    # s2(Semantic Scholar)配置
    s2_api_key: str = ""
    # oa(OpenAlex)配置
    oa_api_key: str = ""
    # Zotero配置
    zotero_user_id: str = ""
    zotero_api_key: str = ""
    zotero_inbox_key: str = ""
    zotero_toread_key: str = ""
    # 其他配置
    email: str = "anonymous_researcher@research.com"
    db_url: str = "sqlite:///./db/papers.db"

    # 业务配置(configs.yaml)
    # 数据库配置
    chunk_size: PositiveInt = DEFAULT_CHUNK_SIZE
    # 网络请求配置
    max_concurrent_workers: PositiveInt = DEFAULT_MAX_CONCURRENT_WORKERS
    max_retries: PositiveInt = DEFAULT_MAX_RETRIES
    request_timeout: PositiveInt = DEFAULT_REQUEST_TIMEOUT
    # 请求链接配置
    dblp_base_url: str = "https://dblp.org"
    cr_base_url: str = "https://api.crossref.org"
    s2_base_url: str = "https://api.semanticscholar.org"
    s2_batch_limit: PositiveInt = Field(le=S2_MAX_BATCH_LIMIT, default=S2_MAX_BATCH_LIMIT)
    oa_base_url: str = "https://api.openalex.org"
    oa_batch_limit: PositiveInt = Field(le=OA_MAX_BATCH_LIMIT, default=OA_MAX_BATCH_LIMIT)
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    zotero_batch_limit: PositiveInt = Field(
        le=ZOTERO_MAX_BATCH_LIMIT, default=ZOTERO_MAX_BATCH_LIMIT)
    # 分析配置
    relevance_threshold: float = 7.0  # 相关性阈值, 用于筛选出相关性高的论文
    # 提示词配置
    system_prompt: str = ""
    user_interests: str = ""

    # 动态配置(tags.yaml和venues.yaml)
    tags: Dict[str, List[str]] = {}
    venues: Dict[str, Dict[str, str] | None] = {}

    # 加载凭证配置和业务配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        yaml_file=config_file_path,
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源, 先加载.env, 再加载configs.yaml"""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings
        )

    @model_validator(mode="before")
    @classmethod
    def _load_configs(cls, data: Dict) -> Dict:
        """加载动态配置"""
        # 加载tags.yaml
        try:
            data["tags"] = _load_yaml(file_path=config_directory / "tags.yaml")
        except Exception as e:
            print(f"Failed to load: {config_directory / 'tags.yaml'}")
            raise e
        # 加载venues.yaml
        try:
            data["venues"] = _load_yaml(file_path=config_directory / "venues.yaml")
        except Exception as e:
            print(f"Failed to load: {config_directory / 'venues.yaml'}")
            raise e
        return data

    @property
    def common_headers(self) -> Dict[str, str]:
        """公共请求头"""
        return {"User-Agent": f"Mozilla/5.0 (Scientific Research; mailto: {self.email})"}


# 初始化配置并校验配置
try:
    configs = AppConfig()
    print("[INFO] Configs initialized successfully")
except Exception as e:
    print("[CRITICAL] Failed to initialize configs")
    print(f"Exception: {e}")
    traceback.print_exc()
    sys.exit(1)
