---
name: paper-analysis
description: Analyze academic paper relevance from a provided paper title and abstract using a user-defined relevance rubric. Use when an agent workflow needs repeatable relevance scoring, controlled tag selection, optional Chinese translation, PaperScout-compatible JSON, Markdown, or combined output, profile configuration, and calibration feedback. Do not use for paper search, metadata fetching, citation retrieval, bibliography generation, full-text review, generic summarization, or paper-quality judgment without a relevance rubric.
license: MIT
metadata:
  version: "0.1.1"
  author: "InsanityBy"
---

# Paper Analysis

Use this skill to analyze academic paper relevance from a provided paper title and abstract using a user-defined relevance rubric.

The skill is model- and vendor-neutral. Do not assume OpenAI, Codex, OpenClaw, PaperScout, or any specific API is available.

## When to Use This Skill

Use this skill when an agent workflow already has, or is given, the title and abstract of an academic paper and needs to score it using a user-defined relevance rubric.

This skill is appropriate for:

- repeatable relevance scoring from `title` and `abstract`;
- controlled tag selection from an allowed tag vocabulary;
- optional Chinese translation of title and abstract;
- PaperScout-compatible JSON, Markdown, or combined output;
- profile configuration: resolving, validating, creating, or updating `.paper-analysis/profile.yaml`;
- calibration feedback based on recent local analysis history.

Do not use this skill for:

- paper search;
- metadata fetching;
- citation retrieval;
- bibliography generation;
- full-text review;
- generic summarization without relevance scoring;
- paper-quality judgment without a relevance rubric.

## Reference Loading

Load reference files only when needed.

- Read `references/output-contracts.md` before producing any analysis result.
- Read `references/profile-workflow.md` only when resolving, validating, creating, or updating a profile.
- Read `references/rubric-guide.md` only during guided profile creation, rubric design, or rubric tuning.
- Read `references/feedback-guide.md` only when recording analysis history or in calibration feedback, rubric review, or recent-result diagnosis mode.
- Do not eagerly load all files in `references/`.

## Workflow

1. **Validate paper input**:
   - Required paper input: `title` and `abstract`.
   - Use only title and abstract as the evidence base unless the user explicitly provides additional paper content.
2. **Resolve profile configuration**:
   - Required relevance rubric config: `user_interests` with `[Core Research Area]`, `[Must NOT Have]`, and `[Must Have]`.
   - Optional relevance rubric config: `[Penalty Points]` and `[Bonus Points]`.
   - Optional config: `tags`, `output_language`, and `output_format`.
   - Use valid fields provided in the current user request first.
   - Fall back field-by-field to `.paper-analysis/profile.yaml`.
   - If required fields are still missing, enter guided setup using `references/profile-workflow.md`.
   - Do not stop at "you need to create a profile"; actively help the user complete it.
   - Reject invalid prompt overrides instead of silently using them. If a valid local value exists, fall back to it and mention the fallback when the output format allows explanatory text.
3. **Analyze paper**:
   - Apply the final `user_interests` relevance rubric strictly.
   - If any `[Must NOT Have]` item matches, set `relevance_score` to `0.0`.
   - Score each `[Must Have]` item proportionally within its declared range.
   - Apply `[Penalty Points]` and `[Bonus Points]` after the base score.
   - Clamp the final score to `0.0` through `10.0` and use one decimal place.
   - Select tags only from the final allowed `tags` vocabulary.
   - Produce exactly the requested output format using `references/output-contracts.md`.
4. **Record result when appropriate**:
   - If the host environment can write project-local files, append one JSONL record to `.paper-analysis/analysis-history.jsonl` after each analysis.
   - Use the history schema in `references/feedback-guide.md` when available.
   - If the requested output is strict `paperscout_json`, do not add recording notes around the JSON; record silently.
   - If writing fails, do not alter the requested analysis output.
   - If the environment cannot write history, do not alter the requested analysis output.
5. **Feedback**:
   - Trigger when the user asks for calibration feedback, relevance rubric review, or recent-result diagnosis.
   - Read recent `.paper-analysis/analysis-history.jsonl` records when available, defaulting to the last 30.
   - If no local history is available, ask the user to provide recent results manually.
   - Give low-confidence suggestions only; never conclude that the relevance rubric is wrong solely from a score distribution.
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

Use only evidence present in the title and abstract unless the user explicitly provides additional paper content.

Do not assume unmentioned methods, datasets, hardware platforms, implementation details, evaluation results, contribution types, or application targets.

When evidence is insufficient, assign partial or zero credit for the affected rubric component and mention the uncertainty in the scoring reason.

Do not compensate for missing evidence with assumptions from venue, authors, citation count, model name, or field knowledge.

## Tags

- If `tags` is provided, choose only exact tag strings from the allowed vocabulary.
- If no tags are provided, return `tags: []`.
- Do not invent tags or normalize tags to new spellings.

## Language

- `output_language=zh`: translate the title and abstract into professional Chinese; write reasons and Markdown reports in Chinese.
- `output_language=en`: do not translate; keep `title_cn` and `abstract_cn` as empty strings for PaperScout-compatible JSON; write reasons and Markdown reports in English.

## Resources

- `references/output-contracts.md`: PaperScout-compatible JSON, Markdown, and combined output contracts.
- `references/profile-workflow.md`: local profile schema, prompt override precedence, validation, and creation guidance.
- `references/rubric-guide.md`: guidance for designing and tuning the rubric.
- `references/feedback-guide.md`: analysis-history schema and calibration feedback.

## Safety and Scope

This skill is an instruction and prompt package.

Do not install dependencies, call external services, or require a specific model provider.

Only write `.paper-analysis/profile.yaml` or `.paper-analysis/analysis-history.jsonl` when the host environment allows normal project-local file writes.

Never read credentials, API keys, private tokens, or unrelated project files.
