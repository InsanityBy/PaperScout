# PaperScout

[English](#english-version) | [中文](#中文版)

---

## English Version

`PaperScout` is an automated pipeline tool for fetching, parsing, analyzing, and managing academic papers. It streamlines the literature review process by automating data retrieval from [DBLP](https://dblp.org), metadata enrichment via [Semantic Scholar](https://www.semanticscholar.org) / [OpenAlex](https://openalex.org), relevance evaluation using LLMs, and direct integration with [Zotero](https://www.zotero.org) or exporting basic reading-note templates in Markdown format.

### Features

- **Fetch**: Retrieve paper lists from multiple sources:
    - DBLP (Conferences / Journals)
    - arXiv (by category with date and year filtering)
- **Parse**: Verify DOIs using Crossref and fetch abstracts automatically via Semantic Scholar and OpenAlex APIs.
- **Analyze**: Utilize configurable OpenAI-compatible LLM providers ([DeepSeek](https://platform.deepseek.com), [Qwen](https://qwen.ai) provided by [Alibaba Cloud](https://bailian.aliyun.com), [Kimi](https://platform.kimi.com), [GLM](https://bigmodel.cn), [ByteDance Seed](https://seed.bytedance.com) provided by [Volcengine](https://www.volcengine.com), or a generic OpenAI-compatible endpoint) to evaluate and score paper relevance (0.0-10.0 float scale, 0.1 increments) based on customizable user interests, extract tags, and translate titles and abstracts to Chinese.
- **Filter**: Independently evaluate and filter successfully analyzed papers based on a customizable threshold. Supports re-evaluating previously filtered papers when run individually.
- **Output**: Flexible output options after filtering. Supports uploading directly to a specified Zotero collection, exporting as local Markdown files, or finishing without any output.
- **Resilience**: Track the status of each paper in a local SQLite database (`PENDING_FETCH`, `PENDING_PARSE`, etc.) to support safe batch processing and resuming from interruptions.
- **Query**: Interactively query papers by processing status and time range, then append or export the results to a structured CSV file.
- **Import**: Import updates from a previously exported and edited CSV file to batch modify paper metadata, tags, scores, and processing status in the database.

### Data Sources

PaperScout supports the following academic paper sources:

- **DBLP**
  - Source type: Conferences & Journals
  - Coverage: Computer Science venues worldwide
  - Configuration: URL-based (see `venues.yaml`)

- **arXiv**
  - Source type: Category-based (e.g., `cs.CV`, `cs.AI`, `cs.LG`)
  - Coverage: Computer Science preprints with date and year filtering
  - Configuration: Category list (see `venues.yaml`)
  - Status handling: Papers fetched from arXiv skip DOI validation, go directly to analysis stage (marked as `PENDING_ANALYZE`)

### Choosing a Usage Mode

PaperScout can be used at three levels:

- **Full PaperScout workflow**: Use this when you want PaperScout to fetch papers, enrich metadata, analyze relevance, filter results, and export or upload them. Continue with the installation, configuration, and CLI usage sections below.
- **Standalone paper-analysis skill**: Use [`skills/paper-analysis`](./skills/paper-analysis/) with a skill-aware agent when another agent, CLI, or automation tool already provides paper titles and abstracts, and you need relevance scoring, controlled tag selection, optional Chinese translation, PaperScout-compatible JSON/Markdown output, profile setup, or calibration feedback. The skill resolves `user_interests`, `tags`, `output_language`, and `output_format` from the current request first, then falls back field-by-field to `.paper-analysis/profile.yaml`. If no usable profile exists, it should guide you through output settings, research interests, rubric, and tags, then create `.paper-analysis/profile.yaml` when file writes are available. For OpenClaw, workspace skills can live under `<workspace>/skills/paper-analysis/`; see [OpenClaw Skills](https://docs.openclaw.ai/tools/skills), [ClawHub](https://docs.openclaw.ai/tools/clawhub), and the [ClawHub skill format](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md).
- **Prompt-only usage**: Use [`docs/paper-analysis-prompt.md`](./docs/paper-analysis-prompt.md) when you do not want a skill-aware agent or project tool. Choose the English or Chinese template, then choose chat mode or API mode. The default combinations are chat mode with Markdown output and API mode with JSON output; other combinations require editing the template's corresponding section. Fill the angle-bracket `<>` placeholders in the research rubric, optional tag vocabulary, and paper title/abstract sections. For batch processing, call the model once per paper.

> **Note**: The standalone skill has explicit `output_language: zh | en` and `output_format: paperscout_json | markdown | both` settings. In `output_language=en`, PaperScout-compatible JSON keeps `title_cn` and `abstract_cn` as empty strings. The prompt-only templates do not use those configuration fields directly; their language and format are determined by the selected template and its output instructions. Only the standalone skill records local analysis history in `.paper-analysis/analysis-history.jsonl` when the host environment can write files; prompt-only usage has no profile resolution or history-based feedback unless you add that workflow yourself.

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

Important environment variables:

- `LLM_API_KEY`: Required for the analyze stage.
- `S2_API_KEY` and `OA_API_KEY`: Used by Semantic Scholar and OpenAlex during the parse stage. Incorrect or missing keys may cause metadata enrichment to fail.
- `ZOTERO_USER_ID`, `ZOTERO_API_KEY`, `ZOTERO_INBOX_KEY`: Required only when using Zotero upload. `ZOTERO_TOREAD_KEY` is reserved in the example environment file but is not used by the current upload workflow.
- `EMAIL`: Used in request headers for external scholarly APIs.
- `DB_URL`: SQLite database URL. The default is `sqlite:///./db/papers.db`.

#### 2. YAML Configs (`configs/`)

In the `configs/` directory, copy the example files to create your actual configurations:

``` bash
cd configs
cp configs.example.yaml configs.yaml
cp tags.example.yaml tags.yaml
cp venues.example.yaml venues.yaml
```

- `configs.yaml`: Main runtime configuration. The most commonly adjusted fields are:
    - Processing and retry behavior: `chunk_size`, `max_concurrent_workers`, `max_retries`, and `request_timeout`.
    - LLM analysis: `llm_provider`, `llm_base_url`, `llm_model`, thinking-related options, `system_prompt`, and `user_interests`.
    - Filtering and output: `relevance_threshold` and `export_directory` for local Markdown and CSV files.
    - arXiv fetching: `arxiv_max_lookback_days` and arXiv batch/API settings.
    - External API endpoints and batch limits for DBLP, Crossref, Semantic Scholar, OpenAlex, and Zotero.
- `tags.yaml`: Controlled tag vocabulary for LLM classification. Tags are grouped by category, but only exact tag strings from the configured lists are retained in analysis results.
- `venues.yaml`: Target sources configuration:
    - DBLP venues: URL-based mapping for conferences and journals (e.g., `CONFERENCE: {url1: ..., url2: ...}`)
    - arXiv categories: Category list for arXiv preprints (e.g., `ARXIV: [cs.CV, cs.AI, cs.LG]`)

#### 3. LLM Provider Configuration

The analyzer will read a single `LLM_API_KEY` from `.env`. Select the provider and model in `configs.yaml`:

``` yaml
llm_provider: "deepseek"  # deepseek, qwen, kimi, glm, seed, openai_compatible
llm_base_url: "https://api.deepseek.com"
llm_model: "deepseek-v4-flash"
llm_thinking_mode: "disabled"  # disabled, enabled, auto
llm_reasoning_effort: "high"   # DeepSeek/Seed only: low, medium, high, max
llm_thinking_budget:           # Qwen only, optional token budget
```

Provider-specific thinking parameters are mapped internally according to each compatible API. `openai_compatible` sends only the basic OpenAI chat-completion parameters and ignores thinking options for maximum compatibility.

> **Tip**: DeepSeek supports `llm_reasoning_effort` values `high` and `max`; `low` and `medium` are mapped to `high`. Seed supports `llm_reasoning_effort` values `low`, `medium`, and `high`; `max` is mapped to `high`.

### Usage

After activating the virtual environment, you can use the `paper_scout` command directly. The CLI requires you to specify the timeframe and the execution stage.

> **Note**: If you prefer not to activate the environment, you can prepend `uv run` to all commands, e.g., `uv run paper_scout ...`

**Run the complete workflow**:
To run all stages sequentially (Fetch -> Parse -> Analyze -> Filter -> Output) for papers between 2024 and 2025:

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
# Query papers by status (e.g., COMPLETED) and export to a CSV file
paper_scout -s 2024 -e 2025 --query-status COMPLETED
# Or shorthand:
paper_scout -s 2024 -e 2025 -q COMPLETED
# Import updates from a CSV file
paper_scout -s 2024 -e 2025 --import-csv path/to/updates.csv
# Or shorthand:
paper_scout -s 2024 -e 2025 -i path/to/updates.csv
```

**Global Options**:

- **Required Arguments (Apply to all commands)**:
    - `--start-year, -s`: Start year for processing papers (applied to both DBLP and arXiv).
    - `--end-year, -e`: End year for processing papers (applied to both DBLP and arXiv).
    - **Note for arXiv**: In addition to year filtering (`start_year`-`end_year`), arXiv fetching also respects `arxiv_max_lookback_days` config. When `start_year` falls before the lookback cutoff date, an interactive prompt offers three options: (1) fetch only recent N days, (2) enter a precise date range using arXiv `submittedDate` query, or (3) skip arXiv fetching entirely.
- **Optional Arguments**:
    - `--output-mode, -o`: Output mode after filtering (Choices: `none`, `upload`, `export`. Default: `export`).
        - `none`: Finish process without uploading or exporting.
        - `upload`: Upload relevant papers directly into the configured Zotero inbox collection.
        - `export`: Export relevant papers as formatted local Markdown files.
    - `--log-directory`: Directory to store log files (Default: `logs`).
    - `--log-level`: Logging level (Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

### Output File Formats

Generated files are written to `export_directory` in `configs.yaml` (default: `exports/`) unless another path is configured.

- **Markdown paper notes**: Generated by the output stage when `--output-mode export` is used. PaperScout creates one `.md` file per relevant paper, using a sanitized and length-limited paper title as the filename. Each file contains YAML front matter (`title`, `doi`, `year`, `venue`, `tags`, `relevance_score`), the original and Chinese title/abstract, source information, AI relevance analysis, tags, and an empty reading-notes section.
- **Query CSV files**: Generated by `--query-status/-q` after interactive confirmation. The default filename is `export_<STATUS>_<START_YEAR>_<END_YEAR>.csv`; custom names get a `.csv` suffix automatically. Existing CSV files are appended to, and new files include a UTF-8 BOM for spreadsheet compatibility. Columns are `DOI`, `Year`, `Venue Type`, `Venue`, `Title`, `Abstract`, `Title (CN)`, `Abstract (CN)`, `Relevance Score`, `Relevance Reason`, `Tags`, `Status`, `Retry Count`, `Create Time`, and `Update Time`. The `Tags` column stores the database JSON string.
- **Zotero items**: Generated by the output stage when `--output-mode upload` is used. PaperScout creates Zotero `journalArticle` items, writes the original title and abstract to Zotero fields, omits pseudo-DOIs, stores Chinese translations and AI analysis in `Extra`, maps extracted tags to Zotero tags, and adds the item to `zotero_inbox_key`.
- **Logs**: Runtime logs are written to `--log-directory` (default: `logs`).

### CSV Import Guidelines

When using the `--import-csv` feature, **we strongly recommend modifying the CSV file exported via the `--query-status` command** rather than creating one from scratch. If you choose to create it manually, please observe the following rules:

- **Header Row**: The CSV must include a header row. The first row is always treated as column names. Headerless CSV files are not supported, even if their column order matches an exported CSV.
- **Required Column**: `DOI` must be present in the header. Rows with DOIs that do not exist in the database will be automatically ignored. Empty files or blank headers report `CSV header missing`; headers without `DOI` report `CSV header missing required column: DOI`.
- **Optional Columns**: You can omit any supported non-`DOI` column. Missing optional columns are skipped and do not block import. Supported column headers include: `Year`, `Venue Type`, `Venue`, `Title`, `Abstract`, `Title (CN)`, `Abstract (CN)`, `Relevance Score`, `Relevance Reason`, `Tags`, `Status`, and `Retry Count`.
- **Unsupported Columns**: Extra columns not listed above are ignored.
- **Empty Values**: Not providing a value in a cell (leaving it blank) means **no change** to that specific field. It will *not* overwrite the existing database value to null/empty.
- **Format Validation**: Any cell that does not meet the required format will cause that field's update to be skipped, and an error will be logged.
- **Unchanged Rows**: The tool compares the CSV data with the database. Rows with no supported non-empty update fields, or rows whose values match the existing record, are counted as unchanged.
- **Duplicate Rows**: If the same DOI appears multiple times in one CSV, the last row wins. Earlier rows for that DOI are counted as duplicates.

### Project Structure

``` text
.
├── configs/                  # Configuration directory
│   ├── configs.yaml          # System configs (from .example.yaml)
│   ├── tags.yaml             # LLM tags (from .example.yaml)
│   └── venues.yaml           # DBLP targets (from .example.yaml)
├── docs/
│   └── paper-analysis-prompt.md # Bilingual prompt-only template
├── skills/
│   └── paper-analysis/       # Paper analysis skill
├── db/                       # SQLite database storage (generated automatically)
├── exports/                  # Local CSV / Markdown files (generated automatically)
├── logs/                     # Log files (generated automatically)
├── src/
│   └── paper_scout/          # Main package directory
│       ├── core/             # Configuration, HTTP client, constants, logging
│       ├── database/         # SQLite models (SQLAlchemy) and CRUD operations
│       ├── service/          # Core business logic (fetcher, parser, analyzer, filter, exporter, importer, uploader)
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

> **Note on arXiv Papers**: Papers fetched from arXiv bypass the `PENDING_PARSE` stage (DOI validation) and enter the workflow with status `PENDING_ANALYZE` directly, since arXiv provides titles and abstracts without requiring DOI resolution.

> **Tip**: To re-analyze a paper, simply change its status to `120` and run `--stage analyze` again.

### License

This project is licensed under the [MIT License](https://mit-license.org). See the [LICENSE](./LICENSE) file for details.

[Back to Top](#paperscout) | [中文](#中文版)

---

## 中文版

`PaperScout` 是一个用于获取、解析、分析和管理学术论文的自动化流水线工具。它通过自动化从 [DBLP](https://dblp.org) 获取数据、利用 [Semantic Scholar](https://www.semanticscholar.org) / [OpenAlex](https://openalex.org) 补充元数据、使用大语言模型（LLM）评估相关性，并直接集成到 [Zotero](https://www.zotero.org) 或导出包含基本信息的 Markdown 格式阅读笔记模板，从而简化文献筛选流程。

### 功能特点

- **获取 (Fetch)**: 从多个数据源获取论文列表：
    - DBLP（会议/期刊）
    - arXiv（基于分类，支持年份和日期筛选）
- **解析 (Parse)**: 使用 Crossref 验证 DOI，并通过 Semantic Scholar 和 OpenAlex 提供的 API 自动获取摘要。
- **分析 (Analyze)**: 利用可配置的 OpenAI 兼容大语言模型供应商（[DeepSeek](https://platform.deepseek.com)、由 [阿里云](https://bailian.aliyun.com) 提供的 [Qwen](https://qwen.ai)、[Kimi](https://platform.kimi.com)、[GLM](https://bigmodel.cn)、由 [火山引擎](https://www.volcengine.com) 提供的 [字节跳动 Seed](https://seed.bytedance.com)，或通用 OpenAI 兼容端点）根据自定义用户兴趣对论文进行 10 分制相关性打分（浮点数，步长 0.1），提取标签，并将标题和摘要翻译为中文。
- **筛选 (Filter)**: 独立阶段，可随时根据配置文件中的阈值，对分析成功的论文进行评估和归类。单独运行该阶段时，支持对过往已筛选的论文重新根据新阈值进行评估。
- **输出 (Output)**: 提供灵活的输出选项。支持自动上传至指定 Zotero 集合、导出为本地 Markdown 文件，或在分析结束后直接标记完成不进行输出。
- **容错恢复 (Resilience)**: 在本地 SQLite 数据库中跟踪每篇论文的处理状态（如 `PENDING_FETCH`, `PENDING_PARSE` 等），支持安全的批量处理和断点续传。
- **查询 (Query)**: 支持按处理状态和时间范围交互式查询论文，并将结果追加或导出为结构化的 CSV 文件。
- **导入 (Import)**: 支持从导出并编辑后的 CSV 文件中导入更新，批量修改数据库中论文的元数据、标签、评分和处理状态等信息。

### 数据源

PaperScout 支持以下学术论文数据源：

- **DBLP**
  - 类型: 学术会议与期刊
  - 覆盖: 全球计算机科学领域顶会/顶刊
  - 配置: 基于 URL（参见 `venues.yaml`）

- **arXiv**
  - 类型: 基于分类的预印本（如 `cs.CV`, `cs.AI`, `cs.LG`）
  - 覆盖: 计算机科学领域预印本，支持日期和年份筛选
  - 配置: 分类列表（参见 `venues.yaml`）
  - 状态处理: 从 arXiv 获取的论文跳过 DOI 验证，直接进入分析阶段（标记为 `PENDING_ANALYZE`）

### 选择使用方式

PaperScout 可以按三种层级使用：

- **完整 PaperScout 工作流**: 当你希望 PaperScout 负责获取论文、补全元数据、分析相关性、筛选结果，并导出或上传论文时，选择此方式。继续阅读下方安装、配置和命令行使用说明即可。
- **独立论文分析 skill**: 当你使用支持 skill 的 agent，且其他 agent、CLI 或自动化工具已经提供论文标题和摘要时，使用 [`skills/paper-analysis`](./skills/paper-analysis/)。它适用于相关性评分、受控标签选择、可选中文翻译、PaperScout 兼容 JSON/Markdown 输出、profile 配置和校准反馈。skill 会优先使用当前请求中的 `user_interests`、`tags`、`output_language` 和 `output_format`，再逐字段回退到 `.paper-analysis/profile.yaml`。如果还没有可用 profile，skill 应逐步引导你填写输出设置、研究兴趣、评分标准和标签，并在可写环境中创建 `.paper-analysis/profile.yaml`。OpenClaw 的 workspace skill 可放在 `<workspace>/skills/paper-analysis/`；可参考 [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)、[ClawHub](https://docs.openclaw.ai/tools/clawhub) 与 [ClawHub skill format](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)。
- **只使用提示词**: 当你不使用支持 skill 的 agent，也不使用项目工具时，使用 [`docs/paper-analysis-prompt.md`](./docs/paper-analysis-prompt.md)。先选择英文或中文模板，再选择聊天模式或 API 模式。默认组合是聊天模式输出 Markdown、API 模式输出 JSON；如果需要其他组合，需要修改模板中的对应部分。使用时替换研究兴趣和评分标准、可选标签词表、论文标题和摘要中的尖括号 `<>` 占位内容。批量处理时，建议每篇论文调用一次模型。

> **注意**：独立 skill 明确支持 `output_language: zh | en` 与 `output_format: paperscout_json | markdown | both`。当 `output_language=en` 时，PaperScout 兼容 JSON 中的 `title_cn` 与 `abstract_cn` 会保留为空字符串。提示词模板本身不直接使用这些配置字段；它的语言和格式由所选模板及其中的输出要求决定。只有独立 skill 会在运行环境可写时把分析历史记录到 `.paper-analysis/analysis-history.jsonl`；只使用提示词时不会自动解析 profile，也不会自动提供基于历史记录的反馈，除非你自行补充这套流程。

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

重要环境变量：

- `LLM_API_KEY`: 分析阶段必需。
- `S2_API_KEY` 和 `OA_API_KEY`: 解析阶段调用 Semantic Scholar 和 OpenAlex 时使用。缺失或配置错误可能导致元数据补全失败。
- `ZOTERO_USER_ID`, `ZOTERO_API_KEY`, `ZOTERO_INBOX_KEY`: 仅在使用 Zotero 上传时必需。`ZOTERO_TOREAD_KEY` 保留在示例环境变量文件中，但当前上传流程不会使用。
- `EMAIL`: 用于外部学术 API 请求头。
- `DB_URL`: SQLite 数据库连接地址，默认值为 `sqlite:///./db/papers.db`。

#### 2. YAML 配置文件 (`configs/`)

进入 `configs/` 目录，将示例文件复制为实际运行的配置文件：

``` bash
cd configs
cp configs.example.yaml configs.yaml
cp tags.example.yaml tags.yaml
cp venues.example.yaml venues.yaml
```

- `configs.yaml`: 主运行配置。最常调整的字段包括：
    - 处理与重试行为：`chunk_size`, `max_concurrent_workers`, `max_retries`, `request_timeout`。
    - LLM 分析：`llm_provider`, `llm_base_url`, `llm_model`、思考相关选项、`system_prompt` 和 `user_interests`。
    - 筛选与输出：`relevance_threshold`，以及本地 Markdown/CSV 文件保存目录 `export_directory`。
    - arXiv 抓取：`arxiv_max_lookback_days` 以及 arXiv 批量/API 设置。
    - DBLP、Crossref、Semantic Scholar、OpenAlex、Zotero 等外部 API 的地址与批量限制。
- `tags.yaml`: 供 LLM 分类的受控标签表。标签按类别组织，但分析结果只会保留配置列表中完全匹配的标签字符串。
- `venues.yaml`: 目标数据源配置：
    - DBLP 出处: 会议和期刊的 URL 映射（如 `CONFERENCE: {url1: ..., url2: ...}`）
    - arXiv 分类: arXiv 预印本的分类列表（如 `ARXIV: [cs.CV, cs.AI, cs.LG]`）

#### 3. LLM 供应商配置

分析阶段将从 `.env` 读取统一的 `LLM_API_KEY`。请在 `configs.yaml` 中选择供应商与模型：

``` yaml
llm_provider: "deepseek"  # deepseek, qwen, kimi, glm, seed, openai_compatible
llm_base_url: "https://api.deepseek.com"
llm_model: "deepseek-v4-flash"
llm_thinking_mode: "disabled"  # disabled, enabled, auto
llm_reasoning_effort: "high"   # 仅DeepSeek/Seed使用: low, medium, high, max
llm_thinking_budget:           # 仅Qwen使用, 可选Token预算
```

不同供应商的思考参数会在内部按其兼容 API 要求映射。`openai_compatible` 只发送 OpenAI Chat Completions 基础参数，并忽略思考配置，以保证最大兼容性。

> **提示**：DeepSeek 支持设置 `llm_reasoning_effort` 为 `high` 和 `max`，`low` 和 `medium` 映射为 `high`。Seed 支持设置 `llm_reasoning_effort` 为 `low`、`medium` 和 `high`，`max` 映射为 `high`。

### 使用说明

激活虚拟环境后，你可以直接使用 `paper_scout` 命令运行工具。命令行需要指定时间范围和执行阶段。

> **注意**：如果你不想激活环境，可以在所有命令前加上 `uv run`，例如 `uv run paper_scout ...`

**运行完整工作流**：
按顺序执行 2024 至 2025 年的完整流程（获取 -> 解析 -> 分析 -> 筛选 -> 输出）：

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
# 按状态(如 COMPLETED)查询论文并导出为 CSV 文件
paper_scout -s 2024 -e 2025 --query-status COMPLETED
# 或使用简写参数:
paper_scout -s 2024 -e 2025 -q COMPLETED
# 从 CSV 文件中导入更新
paper_scout -s 2024 -e 2025 --import-csv path/to/updates.csv
# 或使用简写参数:
paper_scout -s 2024 -e 2025 -i path/to/updates.csv
```

**全局选项**：

- **必选参数（适用于所有命令）**：
    - `--start-year, -s`: 处理论文的起始年份（同时应用于 DBLP 和 arXiv）。
    - `--end-year, -e`: 处理论文的结束年份（同时应用于 DBLP 和 arXiv）。
    - **arXiv 特殊说明**: 除了年份筛选（`start_year`-`end_year`）外，arXiv 抓取还受 `arxiv_max_lookback_days` 配置限制。当 `start_year` 早于回溯截止日期时，工具将交互式提示三个选项：(1) 仅获取最近 N 天、(2) 输入精确日期范围（使用 arXiv `submittedDate` 查询）、(3) 跳过 arXiv 获取。
- **可选参数**：
    - `--output-mode, -o`: 筛选后的输出模式（可选：`none`, `upload`, `export`。默认：`export`）。
        - `none`: 仅完成分析和筛选，不进行任何导出或上传。
        - `upload`: 将筛选后的论文上传至配置的 Zotero inbox 集合。
        - `export`: 将筛选后的论文保存为格式化的本地 Markdown 文件。
    - `--log-directory`: 日志存储目录（默认：`logs`）。
    - `--log-level`: 日志记录级别（可选：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`）。

### 导出文件格式

除非另行配置，生成的文件会写入 `configs.yaml` 中的 `export_directory`（默认：`exports/`）。

- **Markdown 论文笔记**：在输出阶段使用 `--output-mode export` 时生成。PaperScout 会为每篇相关论文创建一个 `.md` 文件，文件名来自清理并限制长度后的论文标题。每个文件包含 YAML front matter（`title`, `doi`, `year`, `venue`, `tags`, `relevance_score`）、原始标题与中文标题、原始摘要与中文摘要、来源信息、AI 相关性分析、标签，以及空白阅读笔记区。
- **查询 CSV 文件**：通过 `--query-status/-q` 查询并交互确认后生成。默认文件名为 `export_<STATUS>_<START_YEAR>_<END_YEAR>.csv`；自定义文件名会自动补齐 `.csv` 后缀。已存在的 CSV 会继续追加，新文件会写入 UTF-8 BOM 以兼容表格软件。列包括 `DOI`, `Year`, `Venue Type`, `Venue`, `Title`, `Abstract`, `Title (CN)`, `Abstract (CN)`, `Relevance Score`, `Relevance Reason`, `Tags`, `Status`, `Retry Count`, `Create Time`, `Update Time`。其中 `Tags` 列保存数据库中的 JSON 字符串。
- **Zotero 条目**：在输出阶段使用 `--output-mode upload` 时生成。PaperScout 会创建 Zotero `journalArticle` 条目，把原始标题和摘要写入 Zotero 字段，跳过伪 DOI，将中文翻译和 AI 分析写入 `Extra`，把提取的标签映射为 Zotero 标签，并将条目加入 `zotero_inbox_key` 指定的集合。
- **日志文件**：运行日志会写入 `--log-directory`（默认：`logs`）。

### CSV 导入规范

在使用 `--import-csv` 功能时，**强烈建议修改通过 `--query-status` 状态查询功能导出的 CSV 文件**，尽量避免从头手动编写。如果必须自行编写，请遵守以下规则：

- **表头**：CSV 必须包含表头行。工具始终把第一行当作列名处理；不支持无表头 CSV，即使其列顺序与导出的 CSV 完全一致。
- **必填列**：表头中必须包含 `DOI` 列。数据库中不存在的 DOI 对应的整行数据会被直接忽略。空文件或空表头会报告 `CSV header missing`；有表头但缺少 `DOI` 列会报告 `CSV header missing required column: DOI`。
- **可选列**：除 `DOI` 列外，其他支持列均可省略。缺失的可选列会被跳过，不影响导入。系统支持的列包括 `Year`, `Venue Type`, `Venue`, `Title`, `Abstract`, `Title (CN)`, `Abstract (CN)`, `Relevance Score`, `Relevance Reason`, `Tags`, `Status`, `Retry Count`。
- **不支持列**：额外的不支持列会被忽略。
- **空值逻辑**：如果某列不提供值（即单元格留空），系统会认为**不修改**该字段，而*不是*将数据库中的该记录修改为空值。
- **格式校验**：每个单元格的值必须符合对应字段的数据类型格式。如果不符合格式要求，该字段的更新将被跳过并记录错误信息。
- **无变动跳过**：导入时会与数据库原始数据进行对比。没有任何受支持的非空更新字段，或字段值与数据库记录一致的行，会被统计为无变动。
- **重复行处理**：如果同一个 DOI 在一个 CSV 中出现多次，最后一行生效；该 DOI 前面的重复行会被统计为重复。

### 项目结构

``` text
.
├── configs/                  # 配置文件目录
│   ├── configs.yaml          # 系统配置 (由 .example.yaml 复制)
│   ├── tags.yaml             # LLM 标签 (由 .example.yaml 复制)
│   └── venues.yaml           # DBLP 目标链接 (由 .example.yaml 复制)
├── docs/
│   └── paper-analysis-prompt.md # 中英双语提示词模板
├── skills/
│   └── paper-analysis/       # 论文分析 skill
├── db/                       # SQLite 数据库存储目录 (自动生成)
├── exports/                  # 本地 CSV / Markdown 文件目录 (自动生成)
├── logs/                     # 日志文件目录 (自动生成)
├── src/
│   └── paper_scout/          # 主包目录
│       ├── core/             # 核心模块 (配置、HTTP客户端、常量、日志)
│       ├── database/         # SQLite 模型 (SQLAlchemy) 与增删改查逻辑
│       ├── service/          # 核心业务逻辑 (获取、解析、分析、筛选、导出、导入、上传)
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

> **关于 arXiv 论文的说明**: 从 arXiv 获取的论文跳过 `PENDING_PARSE` 阶段（DOI 验证），直接以状态 `PENDING_ANALYZE` 进入工作流，因为 arXiv 已提供完整的标题和摘要信息，无需进行 DOI 解析。

> **提示**：如果你想让某篇论文重新进行 LLM 分析，只需将其状态码改为 `120`，然后再次执行 `--stage analyze` 即可。

### 开源协议

本项目采用 [MIT](https://mit-license.org) 开源协议。详情请参阅 [LICENSE](./LICENSE) 文件。

[返回顶部](#paperscout) | [English](#english-version)
