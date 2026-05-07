# Output Contracts

Use these contracts when producing paper-analysis results for PaperScout, agent workflows, or other structured downstream consumers.

## Settings

- `output_language`: `zh` or `en`.
- `output_format`: `paperscout_json`, `markdown`, or `both`.
- Default settings: `output_language=zh`, `output_format=paperscout_json`.

## Input Cardinality

Default output contracts are single-paper contracts.

A single paper must include:

- `title`
- `abstract`

For multiple papers:

- `output_format=markdown`: produce one report section per paper using the selected-language report heading. Separate the results of different papers using an empty line, followed by `---`, and another empty line.
- `output_format=both`: for each paper, output one strict JSON object followed by its Markdown report. Keep each paper's JSON object independently parseable. Separate the results of different papers using an empty line, followed by `---`, and another empty line.
- `output_format=paperscout_json`: only one paper is allowed per invocation. Do not output a JSON array. If multiple papers are provided, ask the caller to submit one paper per invocation or switch to `markdown` or `both`.

Do not invent a new output format unless the user explicitly requests one.

## Evidence and Uncertainty

The analysis must be auditable from the provided evidence.

When title and abstract do not provide enough information for a rubric component:

- assign partial or zero credit for that component;
- mention the missing evidence in `relevance_reason`;
- avoid assuming methods, datasets, hardware platforms, implementation details, evaluation results, contribution types, or application targets;
- keep the score conservative.

The reason should distinguish between:

- evidence that is explicitly present;
- evidence that is absent;
- evidence that is ambiguous or only weakly suggested.

## PaperScout JSON

For `output_format=paperscout_json`, output only one valid JSON object. Do not wrap it in Markdown and do not add extra keys.

Required keys:

```json
{
  "title_cn": "",
  "abstract_cn": "",
  "relevance_score": 0.0,
  "relevance_reason": "",
  "tags": []
}
```

Rules:

- `title_cn`: Chinese title translation when `output_language=zh`; empty string when `output_language=en`.
- `abstract_cn`: Chinese abstract translation when `output_language=zh`; empty string when `output_language=en`.
- `relevance_reason`: single-line scoring explanation using the template for the selected `output_language`.
  - zh vetoed: `0.0 | 触发否决项: <理由>`
  - zh normal: `<分数> | 基础分X.X(标准1: X.X, <理由>; 标准2: X.X, <理由>...)。扣分项: -X.X(<理由>)。加分项: +X.X(<理由>)。`
  - en vetoed: `0.0 | Veto: <reason>`
  - en normal: `<score> | Base score X.X(Criterion 1: X.X, <reason>; Criterion 2: X.X, <reason>...). Penalty: -X.X(<reason>). Bonus: +X.X(<reason>).`
  - Omit the penalty sentence if no penalty applies.
  - Omit the bonus sentence if no bonus applies.
- `relevance_score`: number from `0.0` to `10.0`, rounded to one decimal place.
- `tags`: exact strings selected from the provided allowed tags. Use `[]` if no tags are provided or none apply.

The reason should make the score auditable and follow the selected language template.

## Markdown Report

For `output_format=markdown`, produce a human-readable report in the selected output language.

Recommended English structure:

```markdown
## Paper Analysis Report

**Title**: <original title>
**Translated Title**: <Chinese title; omit for output_language=en>
**Abstract**: <original abstract>
**Translated Abstract**: <Chinese abstract; omit for output_language=en>
**Score**: <score>/10.0
**Tags**: <comma-separated allowed tags, or empty>

### Reason

<Use the same relevance_reason scoring template as PaperScout JSON.>

### Rubric Breakdown

- Veto: <matched veto or none>
- Base Score: <component-level scoring>
- Penalty: <penalties or none>
- Bonus: <bonuses or none>
```

Recommended Chinese structure:

```markdown
## 论文分析报告

**标题**：<原始标题>
**中文标题**：<中文标题>
**摘要**：<原始摘要>
**中文摘要**：<中文摘要>
**评分**：<score>/10.0
**标签**：<从标签表中选择的标签；如果没有则保持空白>

### 相关性理由

<使用与 PaperScout JSON 相同的 relevance_reason 评分模板。>

### 评分拆解

- 否决项：<命中的否决项；如果没有则写 无>
- 基础分：<逐条件得分>
- 扣分项：<扣分项；如果没有则写 无>
- 加分项：<加分项；如果没有则写 无>
```

For `output_language=en`, omit Chinese translation content unless the user explicitly asks for translation.

## Both

For `output_format=both`, output the strict JSON object first, then a blank line, then the Markdown report. The JSON section must still be directly parseable if extracted from the first balanced JSON object.
