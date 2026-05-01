# Rubric Guide

Use this guide to design user interests that produce consistent paper scores during guided profile creation, rubric design, or rubric tuning.

## Core Research Area

Write 2-4 sentences that define the user's actual research target. Include positive scope and boundaries. Avoid vague interests such as "AI papers" or "systems papers"; those make most papers look partially relevant.

Good pattern:

```text
I am interested in <domain> papers that solve <problem> using <methods or systems>, especially when they evaluate <evidence type>. Papers are less relevant if they only discuss <nearby but out-of-scope area>.
```

## Veto Items

Use `[Must NOT Have]` for absolute dealbreakers. A veto should be rare and easy to verify from the title and abstract. If a condition is merely undesirable, put it in penalties instead.

Good veto:

```text
Pure survey papers without a new method, system, dataset, or evaluation.
```

Weak veto:

```text
Not very interesting.
```

## Must-Have Scoring

Make `[Must Have]` components add up to 10.0 before penalties and bonuses. Each component should describe how partial credit works.

Recommended pattern:

```text
1. Target problem fit (Range: 0.0 - 4.0): full credit for ..., partial credit for ..., zero for ...
2. Method or system fit (Range: 0.0 - 4.0): full credit for ..., partial credit for ..., zero for ...
3. Evidence quality (Range: 0.0 - 2.0): full credit for ..., partial credit for ..., zero for ...
```

If every paper receives a middle score, split the largest component into more specific criteria. If too many papers receive zero, move some exclusions from vetoes to penalties.

## Penalties and Bonuses

Use penalties for known weaknesses that should not fully disqualify a paper. Use bonuses for signals that are unusually valuable but not required.

Keep most penalty and bonus values between 0.5 and 2.0. Large values make the base rubric less meaningful.

## Language Choice

Use `output_language=zh` when the user wants Chinese translations and Chinese reasoning. Use `output_language=en` when the downstream workflow only needs English metadata; in that mode, PaperScout-compatible JSON keeps `title_cn` and `abstract_cn` as empty strings.
