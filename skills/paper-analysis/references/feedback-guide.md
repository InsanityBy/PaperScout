# Feedback Guide

Use this reference when the user asks for calibration feedback, relevance rubric review, or recent-result diagnosis.

## History Schema

Each analysis should append one JSON object per line to:

```text
.paper-analysis/analysis-history.jsonl
```

Recommended fields:

```json
{
  "timestamp": "ISO-8601",
  "title": "<original paper title>",
  "profile_source": "prompt_override|local_profile|merged",
  "output_language": "zh",
  "relevance_score": 7.4,
  "tags": ["..."],
  "veto_hit": false,
  "relevance_reason": "..."
}
```

If some fields are unavailable, record the available subset. Do not change the requested user-facing output just to report recording details.

## Feedback Scope

Default to the most recent 30 records. If fewer than 10 records are available, clearly state that the sample is small and feedback confidence is limited.

If no local history is available, ask the user to paste recent JSON, Markdown, CSV, or score summaries.

## Report Structure

Feedback reports must contain these sections:

```markdown
## Observed Pattern

<Only describe score distribution, veto hits, repeated reasons, and tag usage.>

## Possible Explanations

<List multiple plausible interpretations, including both rubric/config issues and data/source explanations.>

## Suggested Checks

<Recommend manual checks before changing the profile.>

## Optional Rubric Adjustments

<Offer cautious changes only as options, not conclusions.>
```

Use the user's selected output language when known; otherwise use the language of the user's request.

## Diagnostic Caution

Do not overstate conclusions. Score patterns can reflect the paper batch, not only the rubric.

Required wording principles:

- Use "may", "might", "could", "suggests", "consider checking", "可能", "也可能", "建议检查".
- Avoid deterministic claims such as "the rubric is wrong", "must be too strict", "必然", "错误".
- Never infer rubric failure from score distribution alone.

## Possible Patterns and Alternative Explanations

Low scores or many veto hits may indicate:

- The rubric may be too strict or vetoes may be too broad.
- The batch may genuinely be unrelated.
- The search source, venue, or keywords may be far from the user's interest.
- Abstracts may not include enough evidence for fair scoring.

High scores may indicate:

- The rubric may be too broad.
- The search query may already be highly precise.
- The venue or source may be tightly aligned with the user's topic.
- The sampled papers may genuinely be highly relevant.

Scores concentrated in a narrow band may indicate:

- The rubric may not separate strong and weak matches well.
- The batch may cover a very similar topic cluster.
- The source may be a single themed venue or special issue.
- The abstracts may be similarly vague or similarly detailed.

Sparse or repetitive tags may indicate:

- The tag vocabulary may be too narrow.
- The batch may genuinely focus on a small set of topics.
- The tags may be too coarse-grained for the user's review goals.

## Suggested Checks Before Changing Profile

Recommend checking:

- A few highest-scored papers.
- A few lowest-scored papers.
- Several vetoed papers.
- Whether the retrieval source or search keywords are biased.
- Whether title and abstract provide enough evidence.

Only after these checks should you suggest profile changes such as softening vetoes, moving vetoes to penalties, redistributing must-have points, or adding/splitting tags.
