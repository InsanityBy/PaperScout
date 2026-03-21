# PaperScout

[English](#english-version) | [中文](#中文版)

---

## English Version

`PaperScout` is an automated pipeline tool for fetching, parsing, analyzing, and managing academic papers. It streamlines the literature review process by automating data retrieval from [DBLP](https://dblp.org), metadata enrichment via [Semantic Scholar](https://www.semanticscholar.org) / [OpenAlex](https://openalex.org), relevance evaluation using LLMs, and direct integration with [Zotero](https://www.zotero.org).

### Features

- **Fetch**: Retrieve paper lists from targeted venues (Conferences / Journals) via DBLP.
- **Parse**: Verify DOIs using Crossref and fetch abstracts automatically via Semantic Scholar and OpenAlex APIs.
- **Analyze**: Utilize LLMs (default supports [DeepSeek](https://www.deepseek.com)) to evaluate and score paper relevance (0.0-10.0 float scale, 0.1 increments) based on customizable user interests, extract tags, and translate titles and abstracts to Chinese.
- **Filter**: Independently evaluate and filter successfully analyzed papers based on a customizable threshold. Supports re-evaluating previously filtered papers when run individually.
- **Output**: Flexible output options after filtering. Support uploading directly to specified Zotero collections, exporting as local Markdown files, or finishing without any output.
- **Resilience**: Track the status of each paper in a local SQLite database (`PENDING_FETCH`, `PENDING_PARSE`, etc.) to support safe batch processing and resuming from interruptions.

### Prerequisites

- **Python**: 3.10+
- **Package Manager**: [uv](https://docs.astral.sh/uv/)

### Installation

This project uses `uv` for lightning-fast dependency management and follows an `src-based` layout.

1. Clone the repository:
    ``` bash
    git clone https://github.com/InsanityBy/PaperScout.git
    cd PaperScout
    ```
2. Sync dependencies using `uv`:
    ``` bash
    uv sync
    ```

### Configuration

The application relies on environment variables and YAML configuration files. Example files are provided in the repository.

#### 1. Environment Variables (`.env`)

Copy the provided `.env.example` to `.env` in the root directory and configure your API keys:

``` bash
cp .env.example .env
```

Edit `.env` to include your LLM, Semantic Scholar, OpenAlex, and Zotero API keys.

#### 2. YAML Configs (`configs/`)

In the `configs/` directory, copy the example files to create your actual configurations:

``` bash
cd configs
cp configs.example.yaml configs.yaml
cp tags.example.yaml tags.yaml
cp venues.example.yaml venues.yaml
```

- `configs.yaml`: System prompts, rate limits, chunk size settings, custom relevance threshold, and `export_directory` for saving markdown files (defaults to `exports/`).
- `tags.yaml`: Predefined tags for LLM classification.
- `venues.yaml`: Target DBLP URLs for conferences and journals.

### Usage

After activating the virtual environment, you can use the `paper_scout` command directly. The CLI requires you to specify the timeframe and the execution stage.

> **Note**: If you prefer not to activate the environment, you can prepend `uv run` to all commands, e.g., `uv run paper_scout ...`

**Run the complete workflow**:
To run all stages sequentially (Fetch -> Parse -> Analyze -> Filter -> Upload) for papers between 2024 and 2025:

``` bash
paper_scout --start-year 2024 --end-year 2025 --run-all
# Or using shorthand arguments:
paper_scout -s 2024 -e 2025 -a
```

**Run specific stages**:
If you want to run a specific pipeline stage separately:

``` bash
# Only fetch metadata from DBLP
paper_scout -s 2024 -e 2025 --stage fetch
# Only parse abstract details
paper_scout -s 2024 -e 2025 --stage parse
# Only analyze papers using LLM
paper_scout -s 2024 -e 2025 --stage analyze
# Only filter papers based on the configured threshold (re-evaluates previously filtered papers)
paper_scout -s 2024 -e 2025 --stage filter
# Only run the output stage (upload to Zotero, export to markdown, or do nothing based on output-mode)
paper_scout -s 2024 -e 2025 --stage output
```

**Global Options**:

- `--output-mode, -o`: Output mode after filtering (Choices: `none`, `upload`, `export`. Default: `export`).
    - `none`: Finish process without uploading or exporting.
    - `upload`: Upload relevant papers directly into specified Zotero collections.
    - `export`: Export relevant papers as formatted local Markdown files.
- `--log-directory`: Directory to store log files (Default: `logs`).
- `--log-level`: Logging level (Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

### Project Structure

``` text
.
├── configs/                  # Configuration directory
│   ├── configs.yaml          # System configs (from .example.yaml)
│   ├── tags.yaml             # LLM tags (from .example.yaml)
│   └── venues.yaml           # DBLP targets (from .example.yaml)
├── db/                       # SQLite database storage (generated automatically)
├── exports/                  # Local Markdown files (generated automatically)
├── logs/                     # Log files (generated automatically)
├── src/
│   └── paper_scout/          # Main package directory
│       ├── core/             # Configuration, HTTP client, constants, logging
│       ├── database/         # SQLite models (SQLAlchemy) and CRUD operations
│       ├── service/          # Core business logic (fetcher, parser, analyzer, uploader)
│       ├── __init__.py
│       ├── main.py           # CLI entry point
│       └── pipeline.py       # Workflow orchestration
├── .env                      # Environment variables (from .env.example)
├── pyproject.toml            # Project metadata and dependencies
├── uv.lock                   # uv lock file
└── README.md
```

### Database & State Management

PaperScout uses a local SQLite database (default path: `db/papers.db`) to track the processing state of each paper. You can use any SQLite management tool (e.g., [DBeaver](https://dbeaver.io), [DB Browser for SQLite](https://sqlitebrowser.org)) to connect and manage the data directly.

#### Table: `papers`

- **`doi`** (Primary Key): The DOI of the paper (or a pseudo-DOI starting with `pseudo_doi:` generated for missing ones).
- **`title` / `abstract`**: Original English title and abstract.
- **`title_cn` / `abstract_cn`**: Chinese translation generated by LLM.
- **`relevance_score`**: Float score (0.0 to 10.0, with a step of 0.1) indicating the paper's relevance based on LLM evaluation.
- **`relevance_reason`**: The LLM's explanation for its relevance evaluation and score.
- **`tags_json`**: Extracted tags stored as a JSON string.
- **`zotero_key`**: The item key after successful upload to Zotero (used to prevent duplicates).
- **`status`**: Integer representing the current processing state.
- **`retry_count`**: Number of retries attempted for failed states.

#### Status Codes

You can manually modify the `status` field in your database tool to force a paper to be re-processed in the next run.

- **Pending States (Normal flow)**
    - `110`: PENDING_PARSE (Waiting for abstract fetching)
    - `120`: PENDING_ANALYZE (Waiting for LLM analysis)
    - `130`: PENDING_FILTER (Waiting for custom relevance threshold evaluation)
    - `140`: PENDING_UPLOAD (Waiting to be uploaded to Zotero)
    - `150`: PENDING_EXPORT (Waiting to be exported as Markdown)
- **Completed States**
    - `200`: COMPLETED (Successfully completed the pipeline)
    - `230`: IRRELEVANT (Filtered out by custom relevance threshold)
- **Error/Failed States (Will be retried automatically up to `max_retries`)**
    - `310`: PARSE_FAILED
    - `311`: DOI_INVALID
    - `320`: ANALYZE_FAILED
    - `340`: UPLOAD_FAILED
    - `350`: EXPORT_FAILED
- **Terminal Failed States (Requires manual intervention)**
    - `400`: PERMANENT_FAILED (Exceeded max retries)
    - `410`: MISSING_DOI (Paper lacked a valid DOI during fetch)

> **Tip**: To re-analyze a paper, simply change its status to `120` and run `--stage analyze` again.

### License

This project is licensed under the [MIT License](https://mit-license.org). See the [LICENSE](./LICENSE) file for details.

[Back to Top](#paperscout) | [中文](#中文版)

---

## 中文版

`PaperScout` 是一个用于获取、解析、分析和管理学术论文的自动化流水线工具。它通过自动化从 [DBLP](https://dblp.org) 获取数据、利用 [Semantic Scholar](https://www.semanticscholar.org) / [OpenAlex](https://openalex.org) 补充元数据、使用大语言模型（LLM）评估相关性，并直接集成到 [Zotero](https://www.zotero.org)，从而简化文献筛选流程。

### 功能特点

- **获取 (Fetch)**: 通过 DBLP 获取目标会议/期刊的论文列表。
- **解析 (Parse)**: 使用 Crossref 验证 DOI，并通过 Semantic Scholar 和 OpenAlex 提供的 API 自动获取摘要。
- **分析 (Analyze)**: 利用大语言模型（默认支持 [DeepSeek](https://www.deepseek.com)）根据自定义用户兴趣对论文进行 10 分制相关性打分（浮点数，步长 0.1），提取标签，并将标题和摘要翻译为中文。
- **筛选 (Filter)**: 独立阶段，可随时根据配置文件中的阈值，对分析成功的论文进行评估和归类。单独运行该阶段时，支持对过往已筛选的论文重新根据新阈值进行评估。
- **输出 (Output)**: 提供灵活的输出选项。支持自动上传至 Zotero 库、导出为本地 Markdown 文件，或在分析结束后直接标记完成不进行输出。
- **容错恢复 (Resilience)**: 在本地 SQLite 数据库中跟踪每篇论文的处理状态（如 `PENDING_FETCH`, `PENDING_PARSE` 等），支持安全的批量处理和断点续传。

### 前置要求

- **Python**: 3.10+
- **包管理器**: [uv](https://docs.astral.sh/uv/)

### 安装

本项目使用 `uv` 进行极速依赖管理，并采用了标准的 `src` 目录结构。

1. 克隆仓库：
    ``` bash
    git clone https://github.com/InsanityBy/PaperScout.git
    cd PaperScout
    ```
2. 使用 `uv` 同步依赖：
    ``` bash
    uv sync
    ```

### 配置说明

应用程序依赖环境变量和 YAML 配置文件进行运行。项目中已经提供了示例文件。

#### 1. 环境变量 (`.env`)

将根目录下的 `.env.example` 复制为 `.env`，并配置你的 API 密钥：

``` bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 LLM、Semantic Scholar、OpenAlex 和 Zotero 的 API 密钥。

#### 2. YAML 配置文件 (`configs/`)

进入 `configs/` 目录，将示例文件复制为实际运行的配置文件：

``` bash
cd configs
cp configs.example.yaml configs.yaml
cp tags.example.yaml tags.yaml
cp venues.example.yaml venues.yaml
```

- `configs.yaml`: 系统提示词、速率限制、分块设置、相关性过滤阈值，以及 Markdown 文件的导出路径 `export_directory`（默认为 `exports/`）。
- `tags.yaml`: 供 LLM 分类的预设标签。
- `venues.yaml`: 目标会议和期刊的 DBLP 链接。

### 使用说明

激活虚拟环境后，你可以直接使用 `paper_scout` 命令运行工具。命令行需要指定时间范围和执行阶段。

> **注意**：如果你不想激活环境，可以在所有命令前加上 `uv run`，例如 `uv run paper_scout ...`

**运行完整工作流**：
按顺序执行 2024 至 2025 年的完整流程（获取 -> 解析 -> 分析 -> 筛选 -> 上传）：

``` bash
paper_scout --start-year 2024 --end-year 2025 --run-all
# 或使用简写参数:
paper_scout -s 2024 -e 2025 -a
```

**运行特定阶段**：
如果你希望单独运行某个流水线阶段：

``` bash
# 仅从 DBLP 获取元数据
paper_scout -s 2024 -e 2025 --stage fetch
# 仅解析摘要信息
paper_scout -s 2024 -e 2025 --stage parse
# 仅使用 LLM 分析论文
paper_scout -s 2024 -e 2025 --stage analyze
# 仅根据配置文件中的阈值对论文进行筛选(会重新评估历史已筛选的论文)
paper_scout -s 2024 -e 2025 --stage filter
# 仅执行输出阶段(根据 output-mode 上传至 Zotero, 导出 Markdown 或无动作)
paper_scout -s 2024 -e 2025 --stage output
```

**全局选项**：

- `--output-mode, -o`: 筛选后的输出模式（可选：`none`, `upload`, `export`。默认：`export`）。
    - `none`: 仅完成分析和筛选，不进行任何导出或上传。
    - `upload`: 将筛选后的论文上传至指定的 Zotero 库。
    - `export`: 将筛选后的论文保存为格式化的本地 Markdown 文件。
- `--log-directory`: 日志存储目录（默认：`logs`）。
- `--log-level`: 日志记录级别（可选：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`）。

### 项目结构

``` text
.
├── configs/                  # 配置文件目录
│   ├── configs.yaml          # 系统配置 (由 .example.yaml 复制)
│   ├── tags.yaml             # LLM 标签 (由 .example.yaml 复制)
│   └── venues.yaml           # DBLP 目标链接 (由 .example.yaml 复制)
├── db/                       # SQLite 数据库存储目录 (自动生成)
├── exports/                  # 本地 Markdown 文件目录 (自动生成)
├── logs/                     # 日志文件目录 (自动生成)
├── src/
│   └── paper_scout/          # 主包目录
│       ├── core/             # 核心模块 (配置、HTTP客户端、常量、日志)
│       ├── database/         # SQLite 模型 (SQLAlchemy) 与增删改查逻辑
│       ├── service/          # 核心业务逻辑 (获取、解析、分析、上传)
│       ├── __init__.py
│       ├── main.py           # 命令行入口
│       └── pipeline.py       # 工作流调度
├── .env                      # 环境变量 (由 .env.example 复制)
├── pyproject.toml            # 项目元数据和依赖配置
├── uv.lock                   # uv 锁文件
└── README.md
```

### 数据库与状态管理

PaperScout 使用本地 SQLite 数据库来跟踪每篇论文的处理状态（默认路径：`db/papers.db`）。你可以使用任何 SQLite 数据库管理软件（如 [DBeaver](https://dbeaver.io)、[DB Browser for SQLite](https://sqlitebrowser.org)）直接连接并管理数据。

#### 数据表：`papers`

- **`doi`** (主键): 论文的 DOI（缺失 DOI 的论文会生成以 `pseudo_doi:` 开头的伪 DOI）。
- **`title` / `abstract`**: 原始的英文标题和摘要。
- **`title_cn` / `abstract_cn`**: LLM 翻译的中文标题和摘要。
- **`relevance_score`**: 浮点数，LLM 评估出的论文相关性评分（范围 0.0 到 10.0，步长 0.1）。
- **`relevance_reason`**: LLM 给出的相关性判定及打分理由。
- **`tags_json`**: 提取的标签（JSON 格式字符串）。
- **`zotero_key`**: 成功上传至 Zotero 后返回的项目 Key（用于防重复上传）。
- **`status`**: 整数，表示论文当前所处的处理状态。
- **`retry_count`**: 针对失败状态记录的重试次数。

#### 状态码 (`status`) 说明

你可以在数据库管理软件中手动修改 `status` 字段，以强制流水线在下一次运行时重新处理某篇论文。

- **待处理状态（正常流程）**
    - `110`: PENDING_PARSE (等待解析摘要)
    - `120`: PENDING_ANALYZE (等待 LLM 分析)
    - `130`: PENDING_FILTER (等待自定义相关性阈值筛选)
    - `140`: PENDING_UPLOAD (等待上传至 Zotero)
    - `150`: PENDING_EXPORT (等待导出为 Markdown 文件)
- **已完成状态**
    - `200`: COMPLETED (成功完成全流程)
    - `230`: IRRELEVANT (未达到设定的相关性评分阈值，被过滤)
- **异常中间状态（系统会自动重试直到达到最大重试次数）**
    - `310`: PARSE_FAILED (解析失败)
    - `311`: DOI_INVALID (DOI 验证失败)
    - `320`: ANALYZE_FAILED (LLM 分析失败)
    - `340`: UPLOAD_FAILED (Zotero 上传失败)
    - `350`: EXPORT_FAILED (Markdown 导出失败)
- **异常终止状态（需要人工介入修改状态）**
    - `400`: PERMANENT_FAILED (超过最大重试次数，永久失败)
    - `410`: MISSING_DOI (获取阶段缺失 DOI)

> **提示**：如果你想让某篇论文重新进行 LLM 分析，只需将其状态码改为 `120`，然后再次执行 `--stage analyze` 即可。

### 开源协议

本项目采用 [MIT](https://mit-license.org) 开源协议。详情请参阅 [LICENSE](./LICENSE) 文件。

[返回顶部](#paperscout) | [English](#english-version)
