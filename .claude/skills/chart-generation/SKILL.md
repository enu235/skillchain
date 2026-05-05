---
name: chart-generation
description: "Use this skill when a single chart needs to be rendered to a PNG with a deterministic, professional look for inclusion in a slide deck or report. Trigger when invoked by another agent (typically deck-builder) that supplies a chart spec JSON and an output PNG path. Also trigger when a user asks for 'a quick chart of this data as a PNG' with explicit data values. Supports bar, line, pie, and scatter charts via the bundled scripts/render_chart.py renderer. Does NOT trigger for interactive charts, dashboards, full data visualizations, or chart libraries other than matplotlib."
---

# Chart Generation

This skill produces a single PNG chart from a JSON spec. It exists so the deck-builder can offload chart rendering to parallel subagents instead of generating charts serially in the deck assembly process.

The renderer lives at `.claude/skills/chart-generation/scripts/render_chart.py`. It reads a JSON spec on stdin and writes a PNG to a path supplied as the first argument. The script is the low-freedom path: prefer it over writing custom matplotlib code.

## Spec shape

```
{
  "title": "string",
  "chart_type": "bar | line | pie | scatter",
  "x_label": "string, ignored for pie",
  "y_label": "string, ignored for pie",
  "series": [
    {
      "name": "string, optional, used for legend",
      "x": ["string or number", ...],
      "y": [number, ...]
    }
  ]
}
```

For `pie`, supply a single series; the `x` array becomes labels and the `y` array becomes slice values. For `scatter`, both `x` and `y` are numeric. For `bar` and `line`, `x` may be string (categorical) or numeric (ordered).

## Workflow

The caller passes you a chart spec JSON and an output PNG path. Save the spec JSON to a temp file or pipe it on stdin to the renderer. Invoke:

```
.venv/bin/python .claude/skills/chart-generation/scripts/render_chart.py <output_path> < <spec_path>
```

If the venv is at a different path, use whichever Python has matplotlib. The renderer is self-contained; it does not import any project-local code.

If the renderer succeeds, the script exits 0 and writes the PNG. End your final message with exactly:

```
CHART_OK <absolute-path-to-png>
```

If the renderer fails (non-zero exit), inspect stderr. For unsupported chart types or malformed specs, fall back to writing a minimal custom matplotlib script via Bash and run it. If the fallback also fails, end your final message with:

```
CHART_SKIP <one-line-reason>
```

The deck-builder handles `CHART_SKIP` by inserting a textual placeholder slide.

## Look and feel

The bundled renderer enforces a neutral but professional look: a single accent color per chart, sans-serif font, light gridlines on bar and line charts only, no chart border. Do not override these in fallback scripts unless the caller explicitly asks; consistency across charts in the same deck matters more than per-chart styling.

## Performance

Each chart should render in well under a second. If the renderer hangs or takes more than 10 seconds, kill it and `CHART_SKIP`. Charts are not load-bearing; the deck still works without them.
