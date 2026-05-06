# Profile Workflow

Use this reference to resolve, validate, create, or update the effective paper-analysis profile configuration.

## Local Files

Default local profile:

```text
.paper-analysis/profile.yaml
```

Default local history:

```text
.paper-analysis/analysis-history.jsonl
```

These files are project-local user data. They should not be committed by default.

## Profile Schema

```yaml
output_language: "zh"
output_format: "paperscout_json"
user_interests: |-
  [Core Research Area]
  <Describe the target research area.>

  [Must NOT Have] (Veto: if any match, score = 0.0)
  1. <Dealbreaker>

  [Must Have] (Base Score Components: sum should usually be 10.0)
  1. <Criterion 1> (Range: 0.0 - 4.0)
  2. <Criterion 2> (Range: 0.0 - 4.0)
  3. <Criterion 3> (Range: 0.0 - 2.0)

  [Penalty Points]
  1. <Weakness> (-1.0)

  [Bonus Points]
  1. <Strong signal> (+1.0)
tags:
  Domain:
    - Machine_Learning
    - Systems
  Contribution:
    - New_Algorithm
    - Benchmark
```

## Prompt Overrides

The current user request may provide any of these fields directly:

- `output_language`
- `output_format`
- `user_interests`
- `tags`

Resolve fields with this precedence:

```text
valid prompt field > local profile field > guided creation
```

Rules:

- If the prompt provides a complete valid config, use it for this request and do not require a local profile.
- If the prompt provides only some valid fields, merge them with `.paper-analysis/profile.yaml`.
- If a prompt field is invalid, do not use it silently. If a valid local profile value exists, fall back to it and mention the fallback when the output format allows explanatory text. If no valid local value exists, ask the user to correct the field.
- Prompt overrides affect only the current analysis unless the user explicitly asks to update the local profile.

## Validation

Valid `output_language`:

- `zh`
- `en`

Valid `output_format`:

- `paperscout_json`
- `markdown`
- `both`

Minimum valid `user_interests`:

- Contains `[Core Research Area]`.
- Contains `[Must NOT Have]`; it may be empty or say none, but the section should exist.
- Contains `[Must Have]` with point ranges.

Valid `tags`:

- YAML-like mapping of category names to lists of tag strings.
- Empty or missing tags are allowed; then return `tags: []`.

## Guided Profile Creation

When required configuration is missing and no usable local profile exists:

Do not merely tell the user to create a profile. Start an interactive creation and continue until a usable profile is ready.

### Creation Flow

Ask one focused question at a time unless the user asks for a compact creation form.

1. **Output preferences**
   - Ask for `output_language`: `zh` or `en`.
   - Ask for `output_format`: `paperscout_json`, `markdown`, or `both`.
   - Give short description and explanation for each option.
2. **Core research area**
   - Ask the user to describe the papers they want to find in 2-4 sentences.
   - If the answer is broad, ask one follow-up to narrow the target problem, method, domain, or evidence type.
3. **Veto rules**
   - Ask for absolute dealbreakers that should force `relevance_score=0.0`.
   - If the user has none, create an explicit empty section such as `None`.
   - Keep vetoes rare and verifiable from title and abstract.
4. **Must-have scoring**
   - Ask for 2-5 positive criteria and help assign point ranges that sum to `10.0`.
   - If the user is unsure, propose a default split:
     - Target problem fit: `0.0 - 4.0`
     - Method/system fit: `0.0 - 4.0`
     - Evidence/evaluation quality: `0.0 - 2.0`
   - Confirm that the point ranges sum to `10.0`.
5. **Penalties and bonuses**
   - Ask for non-fatal weaknesses as penalties.
   - Ask for valuable but non-required signals as bonuses.
   - If the user has none, create explicit `None` entries.
6. **Tags**
   - Ask whether the user has a controlled tag vocabulary.
   - If yes, collect categories and tag strings in format: `category1: tag1, tag2,...`
   - If no, use `tags: {}` and remind the user that analyses will return `tags: []`.
   - If there are any issues such as overlapping or ambiguous categories and tags, remind the user and ask one follow-up.
7. **Review and create**
   - Show the complete proposed `.paper-analysis/profile.yaml`.
   - Ask for confirmation or edits.
   - After confirmation, create `.paper-analysis/` if needed and write `.paper-analysis/profile.yaml`.
   - If the paper title and abstract were already provided, continue with analysis using the newly created profile.

Do not overwrite an existing profile unless the user explicitly asks for an update.

If the host environment cannot write files, provide the complete profile content and tell the user where it belongs. In writable agent environments, create the file rather than stopping with instructions.
