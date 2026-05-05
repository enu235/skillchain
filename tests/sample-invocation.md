# Sample invocation and verification trace

This document is both a test harness and a hand-traced verification. Read it through once before running, then either run it (real web calls) or just walk through it (no web calls).

## Recommended low-stakes topic

> Research the history and adoption of the Oxford comma.

This topic has plenty of public web coverage, no time-sensitive numbers to chase, no contentious data, and no need for live financial sources. It exercises every phase of the pipeline cleanly while keeping web budget low.

## Expected execution trace

When you say the prompt above with this directory as the working directory, here is what should happen.

### Phase 1: Trigger and decomposition

Claude Code matches the `research` skill on its description. The skill body loads into the parent context. The orchestrator generates a run id, creates `./research-output/run-YYYYMMDD-HHMMSS-XXXX/{drilldown,charts}/`, writes `manifest.json`.

Then it proposes 5 subtopics. Plausible ones for the Oxford comma:

1. Origin of the Oxford comma (Oxford University Press, 19th century)
2. Style guide adoption (AP, Chicago, MLA, etc.)
3. Famous legal disputes hinging on the Oxford comma
4. Public attitudes and survey data
5. Arguments for and against

It calls AskUserQuestion to confirm. You accept or edit. It writes `subtopics.json`. Manifest gets `phase1_decomposition`.

### Phase 2: Drilldown fan-out

The orchestrator emits a single response containing 5 Agent calls (one per subtopic), all with `subagent_type: drilldown-agent`. Each call's prompt includes the subtopic, framing, original topic, and output path like `./research-output/<run-id>/drilldown/origin-of-oxford-comma.json`.

Each drilldown-agent loads `.claude/skills/drilldown/SKILL.md`, runs 3 to 5 WebSearch queries, fetches 3 to 5 sources, distills into the schema, writes the JSON, and ends with a fenced `// drilldown-result` block.

The orchestrator parses each return, validates the schema, and writes `drilldown-index.json`. Manifest gets `phase2_drilldown`.

If a drilldown returns malformed JSON, the orchestrator re-spawns just that one. If it fails twice, that subtopic is marked degraded and the pipeline continues.

### Phase 3: Outlier detection

The orchestrator spawns one Agent call with `subagent_type: outlier-agent`, passing `drilldown-index.json` and the output path `./research-output/<run-id>/outliers.json`.

For Oxford comma research, expect few or no high-severity outliers; this is a stable topic with broad agreement on the basics. The agent likely returns 1 or 2 low-severity items (perhaps a definitional disagreement about whether the AP has officially adopted it). Manifest gets `phase3_outliers`.

### Phase 4: Excel generation

In-context. The orchestrator reads all drilldown JSONs and the outliers JSON, then runs `.venv/bin/python` with an inline openpyxl script to build:

- `Summary` sheet: 5 rows, one per subtopic.
- 5 subtopic sheets: each with a Claims table and a Data Points table (Data Points tables may be sparse for the Oxford comma topic since there are not many quantitative facts).
- `Outliers` sheet: rows for each anomaly, or a single "None detected" row.
- `Sources` sheet: deduplicated URL list.

File at `./research-output/<run-id>/report.xlsx`. Manifest gets `phase4_xlsx`.

### Phase 5: Deck assembly

The orchestrator spawns one Agent call with `subagent_type: deck-builder`. Deck-builder reads inputs, plans 9 slides (title, exec summary, 5 subtopic slides, outliers, sources), identifies which subtopics have `recommended_charts`, and builds chart specs.

For Oxford comma, expect 2 to 4 charts at most (perhaps a bar chart of style guide stances, a timeline of adoption, etc.). Deck-builder spawns those many chart-agents in parallel. Each chart-agent runs `render_chart.py` via Bash and returns `CHART_OK <path>`.

Deck-builder assembles the pptx via python-pptx, applying the pptx skill's design guidance. Returns `DECK_OK <path>` plus a slide outline. Manifest gets `phase5_pptx`.

### Phase 6: Delivery

The orchestrator composes a one-paragraph executive summary by stitching the highest-signal sentences from each drilldown's `summary` field, plus a callout for the most severe outlier (if any). Prints the absolute paths to the .xlsx and .pptx along with the summary. Manifest gets `phase6_delivery`.

## Verification checklist

After a run completes, confirm:

- [ ] `./research-output/<run-id>/manifest.json` has all six phases populated.
- [ ] `./research-output/<run-id>/drilldown/` contains one JSON per confirmed subtopic.
- [ ] Each drilldown JSON validates against the `drilldown-result` schema (open it and eyeball the keys).
- [ ] `./research-output/<run-id>/outliers.json` exists and has both `anomalies` and `summary` fields.
- [ ] `./research-output/<run-id>/report.xlsx` opens, has the expected sheet count, and the Summary sheet's row count matches the subtopic count.
- [ ] `./research-output/<run-id>/charts/` has one PNG per recommended chart that succeeded.
- [ ] `./research-output/<run-id>/deck.pptx` opens, slide count matches the deck-builder's outline, no overlapping text or empty placeholders.
- [ ] The chat output prints both absolute paths and an executive summary under 120 words.

## Fault injection (optional)

To verify graceful degradation, edit `.claude/agents/drilldown-agent.md` and remove `WebFetch` from the `tools:` line. Re-run. Expect:

- Drilldowns will return JSONs with empty or low-confidence claims and populated `limitations`.
- The orchestrator continues; no abort.
- The deck and workbook still produce, just thinner.

Restore the tool list when done.

## Cost expectation

Most of the cost is in the drilldown subagents, which each run a handful of web searches and fetches. For a topic like the Oxford comma, expect total runtime of 2 to 5 minutes and a moderate token spend distributed across several isolated context windows. The orchestrator's window stays small because it never sees raw web content.
