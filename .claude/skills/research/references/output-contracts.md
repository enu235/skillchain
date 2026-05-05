# Output Contracts

Every handoff in the research pipeline is governed by one of the schemas below. The orchestrator validates returns against these schemas and retries on mismatch. Subagents must produce exactly these shapes in their final assistant message, in addition to writing the same JSON to disk at the path supplied by the caller.

JSON blocks must be inside a single fenced code block tagged with the language and the contract name as a comment on the first line, like this:

```json
// drilldown-result
{ ... }
```

The orchestrator extracts the block by finding the first fenced json block whose first non-whitespace line begins with `// <contract-name>`.

## drilldown-result

Produced by `drilldown-agent`. One per subtopic.

```
{
  "subtopic": "string, must match the slug supplied by the orchestrator",
  "subtopic_name": "string, human-readable name",
  "summary": "string, 60 to 120 words, no markdown formatting",
  "key_claims": [
    {
      "claim": "string, one sentence",
      "source_url": "string, must be a fully-qualified http or https URL",
      "confidence": "high | medium | low"
    }
  ],
  "data_points": [
    {
      "label": "string",
      "value": "number or string; numeric where possible",
      "unit": "string, may be empty",
      "source_url": "string, http or https URL"
    }
  ],
  "recommended_charts": [
    {
      "title": "string",
      "chart_type": "bar | line | pie | scatter",
      "x_label": "string",
      "y_label": "string",
      "data_indices": [0, 1, 2]
    }
  ],
  "sources": ["string url, deduplicated"],
  "limitations": "string, may be empty"
}
```

Validation rules: `key_claims` and `data_points` arrays may be empty if the subtopic genuinely yields no quantitative claims, but `summary` must always be populated. `data_indices` in each recommended chart must be valid indices into `data_points`. If `data_points` is empty, `recommended_charts` must also be empty.

## outlier-result

Produced by `outlier-agent`. Exactly one per run.

```
{
  "anomalies": [
    {
      "type": "contradiction | stat_outlier | low_confidence_conflict",
      "description": "string, one to three sentences",
      "involved_subtopics": ["string, subtopic slug"],
      "severity": "high | medium | low",
      "evidence_refs": [
        {"subtopic": "string slug", "claim_or_data_index": 0}
      ]
    }
  ],
  "summary": "string, 40 to 80 words"
}
```

If no anomalies are detected, return `{"anomalies": [], "summary": "No cross-subtopic anomalies detected."}`. Do not omit the `summary` field even when empty.

## chart-result

Produced by `chart-agent`. One per chart.

The chart-agent's final assistant message must contain exactly one of these lines:

```
CHART_OK <absolute-path-to-png>
```

or

```
CHART_SKIP <one-line-reason>
```

No JSON block needed; the chart-agent writes a binary PNG, not structured data.

## deck-result

Produced by `deck-builder`. Exactly one per run.

The deck-builder's final assistant message must contain exactly one of:

```
DECK_OK <absolute-path-to-pptx>
slide_outline:
  1. <slide title>
  2. <slide title>
  ...
```

or

```
DECK_FAIL <one-line-reason>
```

The slide outline is a numbered list, one line per slide, used by the orchestrator to inform the executive summary. It is not a strict schema; treat it as informational.

## Fallback xlsx and pptx schemas

If the orchestrator must fall back from a vendored skill to a direct `openpyxl` or `python-pptx` invocation, it should still produce the workbook structure described in the orchestrator skill body (Summary, per-subtopic, Outliers, Sources sheets) and a minimal but valid pptx (title, exec summary, one slide per subtopic, outliers slide, sources slide).
