---
name: paper-analysis
description: Use this skill to score an academic paper from a provided title and abstract against a user-defined research-interest rubric. Trigger for paper relevance screening, PaperScout-compatible JSON, Markdown paper analysis reports, profile-based rubric setup, controlled tagging, Chinese translation, and calibration feedback. Do not use for general literature search, citation retrieval, full-text review, or paper summarization without a relevance rubric/profile.
license: MIT
metadata:
  version: "0.1.0"
  author: "InsanityBy"
---

# Paper Analysis

Use this skill to score an academic paper against a user-defined research-interest rubric. The skill is model- and vendor-neutral: do not assume OpenAI, Codex, OpenClaw, PaperScout, or any specific API is available.

## When to Use This Skill

Use this skill when the user or calling workflow provides, or wants to create, a research-interest rubric for scoring academic papers.

Typical triggers include:

- scoring paper relevance from title and abstract;
- producing PaperScout-compatible JSON;
- producing a Markdown paper analysis report;
- translating title and abstract into professional Chinese as part of paper scoring;
- selecting tags from a controlled vocabulary;
- creating or updating a local paper-analysis profile;
- reviewing recent scoring behavior, strictness, calibration, or rubric quality.

Do not use this skill for:

- general literature search;
- citation retrieval;
- full-text paper review;
- bibliography generation;
- generic paper summarization without relevance scoring;
- extracting implementation details from a full paper unless the user explicitly extends the evidence base beyond title and abstract.

## Reference Loading

If operating as an Agent, use file-reading tools to read reference files selectively:

- Read `references/output-contracts.md` before producing any analysis result.
- Read `references/profile-workflow.md` only when resolving, creating, validating, or updating a profile.
- Read `references/rubric-guide.md` only during guided profile creation, rubric design, or rubric tuning.
- Read `references/feedback-guide.md` only in feedback, calibration, rubric review, strictness review, or recent-result diagnosis mode.

Do not eagerly load all files in `references/`.

## Workflow

1. **Resolve profile**: Determine the effective configuration before analyzing.
  - Use valid fields provided in the current user request first.
  - Fall back field-by-field to `.paper-analysis/profile.yaml`.
  - If required fields are still missing, enter guided setup. Ask the user step by step for the missing profile fields, draft the profile, confirm it, then create `.paper-analysis/profile.yaml` when file writes are available.
  - Do not stop at "you need to create a profile"; actively help the user complete it.
  - Follow `references/profile-workflow.md`.
2. **Validate inputs**:
  - Required paper input: `title` and `abstract`.
  - Required analysis config: `user_interests` with `[Core Research Area]`, `[Must NOT Have]` and `[Must Have]`
  - Optional analysis config: `[Penalty Points]` and `[Bonus Points]`.
  - Optional config: `output_language`, `output_format` and `tags`.
  - Reject invalid prompt overrides instead of silently using them. If a valid local value exists, fall back to it and mention the fallback when the output format allows explanatory text.
3. **Analyze paper**:
  - Read the title and abstract as the evidence base unless the user provides more paper content.
  - Apply the final `user_interests` rubric strictly.
  - Select tags only from the final allowed `tags` vocabulary.
  - Produce exactly the requested output format using `references/output-contracts.md`.
4. **Record result**:
  - If the host environment can write files, append one JSONL record to `.paper-analysis/analysis-history.jsonl` after each analysis.
  - Use the history schema in `references/feedback-guide.md`.
  - If the requested output is strict `paperscout_json`, do not add recording notes around the JSON; record silently.
  - If writing fails, do not change the requested analysis output. Mention the write failure only when the output format allows explanatory text.
  - If the environment cannot write history, do not alter the analysis output contract. In later feedback mode, ask the user to provide recent results manually.
5. **Feedback mode**:
  - Trigger when the user asks for feedback, calibration, rubric review, strictness review, or recent-result diagnosis.
  - Read recent `.paper-analysis/analysis-history.jsonl` records when available, defaulting to the last 30.
  - Give low-confidence suggestions only; never conclude that the rubric is wrong solely from a score distribution.
  - Follow `references/feedback-guide.md`.

## Scoring Rules

`user_interests` is the scoring standard. This skill does not provide a default research profile because the rubric must reflect the user's own research goals.

Apply the rubric as follows:

- Initial `relevance_score` is 0.0.
- If any `[Must NOT Have]` item matches, set `relevance_score` to `0.0`.
- Score each `[Must Have]` item proportionally within its declared range.
- Apply `[Penalty Points]` and `[Bonus Points]` after the base score.
- Clamp the final score to `0.0` through `10.0` and use one decimal place.

## Evidence Rules

- Use only evidence present in the title and abstract unless the user provides additional paper content.
- Do not infer unmentioned methods, datasets, hardware platforms, implementation details, evaluation results, or application targets.
- When evidence is insufficient, assign partial or zero credit for the affected rubric component and mention the uncertainty in `relevance_reason`.
- Do not compensate for missing evidence with assumptions from the paper venue, authors, citation count, model name, or nearby field knowledge unless that information is explicitly provided by the user.
- If the abstract is too vague to support confident scoring, keep the score conservative and explain which rubric components lacked evidence.

## Tags

- If `tags` is provided, choose only exact tag strings from the allowed vocabulary.
- If no tags are provided, return `tags: []`.
- Do not invent tags or normalize tags to new spellings.

## Language

- `output_language=zh`: translate the title and abstract into professional Chinese; write reasons and Markdown reports in Chinese.
- `output_language=en`: do not translate; keep `title_cn` and `abstract_cn` as empty strings for PaperScout-compatible JSON; write reasons and Markdown reports in English.

## Resources

- `references/output-contracts.md`: PaperScout-compatible JSON, Markdown, and combined output contracts.
- `references/profile-workflow.md`: local profile schema, prompt override precedence, validation, and profile creation guidance.
- `references/rubric-guide.md`: guidance for designing and tuning `user_interests`.
- `references/feedback-guide.md`: analysis-history schema and cautious calibration feedback.

## Safety and Scope

- This skill is an instruction and prompt package. It should not install dependencies, read credentials, call external services, or require a specific model provider.
- Only write `.paper-analysis/profile.yaml` or `.paper-analysis/analysis-history.jsonl` when the host environment allows normal project-local file writes.
- Never read credentials, API keys, private tokens, or unrelated project files.
- Do not call external services unless the host workflow explicitly provides and authorizes such tools outside this skill.
