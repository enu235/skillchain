---
name: outlier-detection
description: "Use this skill when a caller has multiple drilldown JSON files (one per subtopic) and needs cross-subtopic anomalies surfaced as structured JSON. Trigger when invoked by the research orchestrator with a path to a drilldown-index.json and an output path. Also trigger when a user explicitly asks to 'find contradictions across these research summaries' or 'flag statistical outliers in this research data'. Detects three classes of anomaly: cross-subtopic claim contradictions, statistical outliers in numeric data points, and low-confidence claims that conflict with high-confidence claims elsewhere. Does NOT do web research; consumes only the JSON inputs."
---

# Outlier Detection

This skill takes a set of drilldown JSON files and surfaces inconsistencies that would not be visible from any single drilldown in isolation. It is the cross-cutting analytical pass between research and reporting.

The input is a `drilldown-index.json` file whose entries point to per-subtopic JSON files. Read every non-degraded drilldown. The output is a single JSON file matching the `outlier-result` schema in `.claude/skills/research/references/output-contracts.md`, plus the same JSON echoed in the agent's final message inside a fenced block tagged `outlier-result`.

This skill performs no web access. The caller's agent should not have web tools enabled.

## Three anomaly classes

### Contradictions

A contradiction is two claims from different subtopics that cannot both be true given a reasonable reading. Examples: subtopic A's drilldown says "the market grew 12% in 2024" with high confidence, subtopic B's drilldown says "the market shrank 4% in 2024" with high confidence; or subtopic A says "regulator X has authority" while subtopic B says "regulator Y has authority" over the same domain.

For each contradiction, record `type: "contradiction"`. Set `severity: high` when both claims are high-confidence and the conflict is direct. Set `severity: medium` when one claim is medium-confidence or the conflict is indirect (different time frames, different geographies). Severity goes to `low` only when the contradiction is mostly definitional. Populate `evidence_refs` with the involved subtopics and the indices of the conflicting claims.

### Statistical outliers

Across all `data_points` from all drilldowns, identify numeric values that are unusual within a comparable group. A "comparable group" is a set of data points whose `label` and `unit` suggest they are measuring the same thing across different subtopics or different time periods.

Use a simple heuristic: when 4 or more comparable numeric values are available, flag any value more than 2 standard deviations from the mean, or any value where the ratio of max to min in the group exceeds 10x. With fewer than 4 values, skip the statistical test for that group; not enough data.

Record `type: "stat_outlier"`. Set `severity: high` when the outlier exceeds 3 standard deviations or implies a major decision-relevant disagreement. Set `severity: medium` for the 2 to 3 sigma range. Most stat outliers are at most `medium` severity unless they directly contradict a high-confidence claim.

### Low-confidence conflicts

When a low-confidence claim in one subtopic disagrees with a high-confidence claim in another subtopic, record `type: "low_confidence_conflict"`. This is softer than a contradiction; it usually means one source is shaky and the other is solid, but it deserves a flag because if the user reads only the shaky source they would draw the wrong conclusion. Severity is typically `medium`.

## Workflow

Read the `drilldown-index.json` first. Skip any entry where `degraded: true`. For each remaining entry, read the per-subtopic JSON. Build two in-memory structures: a flat list of all claims (with their subtopic slug and index) and a flat list of all data points (with their subtopic slug, index, label, unit, and numeric value where parseable).

Scan claims pairwise for contradictions. Do not run a quadratic check across thousands of claims; in practice each subtopic has under 10 claims, so the total claim count is bounded. Use semantic judgment: do these two claims make assertions about the same entity that cannot both be true?

Group data points by normalized `(label, unit)` and run the statistical test on each group of 4 or more values. Normalize labels by lowercasing and stripping common suffixes; do not over-merge.

For each anomaly, write a one to three sentence description that names the involved subtopics and what the conflict is. The description goes into the deck and the workbook's outliers sheet, so it must be readable on its own without re-reading the source claims.

After the analysis, write the JSON to the output path supplied by the caller. End your final assistant message with the fenced `outlier-result` block. If you find no anomalies, return an empty `anomalies` array and a `summary` of `"No cross-subtopic anomalies detected."`. Do not omit `summary`.

## Edge cases

If only one or two non-degraded drilldowns exist, contradictions and stat outliers are mostly meaningless (you need multiple subtopics to compare). In that case, return `{"anomalies": [], "summary": "Insufficient cross-subtopic data for outlier detection (only N subtopics had usable data)."}`. Substitute the actual count.

If a drilldown JSON is malformed or unreadable, skip it and note the skip in `summary`. Do not abort.

If you suspect a contradiction but cannot verify because the underlying claims are themselves vague, prefer to flag it with `severity: low` rather than drop it. The orchestrator will surface it in the workbook for human review.
