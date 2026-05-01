# Output Contracts

Use these contracts when producing any analysis results.

## Settings

- `output_language`: `zh` or `en`.
- `output_format`: `paperscout_json`, `markdown`, or `both`.
- Default settings: `output_language=zh`, `output_format=paperscout_json`.

## Single vs. Multiple Paper Output Contracts

Default output contracts are single-paper contracts.

A single paper must include:

- `title`
- `abstract`

For multiple papers:

- `output_format=markdown`: Produce a single unified document. For each paper, generate a sequential section headed `## Paper Analysis Report 1`, `## Paper Analysis Report 2`, etc. The content and structure within each section must strictly match the single-paper format.
- `output_format=both`: Do not apply section headers or numbering. Simply repeat the single-paper `both` pattern for each paper and concatenate the results using a clear separator (`---`). Ensure each paper's JSON object remains strictly independent and individually parseable.
- `output_format=paperscout_json`: only one paper is allowed per invocation. Do not output a JSON array. If multiple papers are provided, ask the caller to submit one paper per invocation or switch to `markdown` or `both`.

Do not invent a new output format unless the user explicitly requests one.

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

### Rules

- `title_cn`: Chinese title translation when `output_language=zh`; empty string when `output_language=en`.
- `abstract_cn`: Chinese abstract translation when `output_language=zh`; empty string when `output_language=en`.
- `relevance_score`: number from `0.0` to `10.0`, rounded to one decimal place.
- `relevance_reason`: concise scoring explanation in the selected output language following the selected language template provided by `### Relevance Reason Format`.
- `tags`: exact strings selected from the provided allowed tags. Use `[]` if no tags are provided or none apply.

The reason should make the score auditable and follow the selected language template provided by `## Relevance Reason Format`

### Relevance Reason Format

`relevance_reason` must be a single-line scoring explanation.

For `output_language=zh`:

- Vetoed: `0.0 | 触发否决项: <原因>`
- Normal: `分数 | 基础分X.X(条件1: X.X, <理由>; 条件2: X.X, <理由>...)。扣分项: -X.X(<理由>)。加分项: +X.X(<理由>)。`

For `output_language=en`:

- Vetoed: `0.0 | Veto: <reason>`
- Normal: `Score | Base score X.X(Criterion 1: X.X, <reason>; Criterion 2: X.X, <reason>...). Penalty: -X.X(<reason>). Bonus: +X.X(<reason>).`

Rules:

- Criteria follow the order of `[Must Have]`.
- Omit the penalty sentence if no penalty applies.
- Omit the bonus sentence if no bonus applies.
- `relevance_score` is the final score after penalties and bonuses.

## Markdown Report

For `output_format=markdown`, produce a human-readable report in the selected output language.

Recommended structure:

```markdown
# Paper Analysis Report

- **Title**: <original title>
- **Translated Title**: <Chinese title; omit for output_language=en>
- **Abstract**: <original abstract>
- **Translated Abstract**: <Chinese abstract; omit for output_language=en>
- **Score**: <score>/10.0
- **Tags**: <comma-separated allowed tags, or empty>

## Reason

<scoring explanation equals to `relevance_reason`>

## Rubric Breakdown

- Veto: <matched veto or none>
- Base Score: <component-level scoring>
- Penalty: <penalties or none>
- Bonus: <bonuses or none>
```

For `output_language=en`, omit Chinese translation content unless the user explicitly asks for translation.

## Both

For `output_format=both`, output the strict JSON object first, then a blank line, then the Markdown report. The JSON section must still be directly parseable if extracted from the first balanced JSON object.
