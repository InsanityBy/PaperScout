# constant.py
# This file is licensed under the MIT License
# See the LICENSE file in the project root for more information

from pathlib import Path

from paper_scout.database.model import VenueType


# 默认包名
DEFAULT_PACKAGE_NAME = "paper_scout"

# 默认日志级别
DEFAULT_LOG_LEVEL = "INFO"

# 默认路径
# 根目录
ROOT_DIRECTORY = Path(__file__).resolve().parent.parent.parent.parent
# 默认日志目录
DEFAULT_LOG_DIRECTORY = ROOT_DIRECTORY / "logs"
# 默认配置目录
DEFAULT_CONFIG_DIRECTORY = ROOT_DIRECTORY / "configs"
# 默认导出目录
DEFAULT_EXPORT_DIRECTORY = ROOT_DIRECTORY / "exports"

# 伪DOI前缀
PSEUDO_DOI_PREFIX = "pseudo_doi:"

# 默认数据库分块
DEFAULT_CHUNK_SIZE = 100

# 批量处理限制
ARXIV_MAX_BATCH_LIMIT = 200
S2_MAX_BATCH_LIMIT = 500
OA_MAX_BATCH_LIMIT = 50
ZOTERO_MAX_BATCH_LIMIT = 50

# HTTP相关
DEFAULT_MAX_CONCURRENT_WORKERS = 10
DEFAULT_MAX_RETRIES = 3
DEFAULT_REQUEST_TIMEOUT = 30
POOL_CONNECTIONS = 20
POOL_MAXSIZE = 20

# 速率限制周期(秒)
ARXIV_PERIOD = 3
DBLP_PERIOD = 10
CR_PERIOD = 1
S2_PERIOD = 1
OA_PERIOD = 1
LLM_PERIOD = 1
ZOTERO_PERIOD = 1

# 速率限制(每PERIOD秒请求数)
ARXIV_RATE_LIMIT = 1
DBLP_RATE_LIMIT = 1
CR_RATE_LIMIT = 2
S2_BATCH_RATE_LIMIT = 1
S2_SINGLE_RATE_LIMIT = 5
OA_BATCH_RATE_LIMIT = 1
OA_SINGLE_RATE_LIMIT = 5
LLM_RATE_LIMIT = 20
ZOTERO_RATE_LIMIT = 5

# arXiv 特殊限制
# 日期限制
ARXIV_MAX_LOOKBACK_DAYS = 100
# 数据量阈值
ARXIV_LARGE_FETCH_THRESHOLD = 1000

# DBLP解析模板
DBLP_VENUE_RULE = {
    VenueType.CONFERENCE: {
        "tag": "proceedings",
        "link_tag": "url",
        "year_tag": "year"
    },
    VenueType.JOURNAL: {
        "tag": "ref",
        "link_attr": "href"
    }
}
DBLP_PAPER_RULE = {
    VenueType.CONFERENCE: "inproceedings",
    VenueType.JOURNAL: "article"
}
