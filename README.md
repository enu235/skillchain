# skillchain

A hierarchical research-report pipeline built from Claude Code skills and subagents. Demonstrates composability and context economy: a top-level orchestrator skill drives several child skills, several of those skills run inside isolated subagent contexts, and one of the subagents recursively spawns more subagents.

## What it does

Invoke the `research` skill with a topic, and the pipeline produces:

- An Excel workbook with one sheet per subtopic, a summary sheet, an outliers sheet, and a sources sheet.
- A PowerPoint deck with a title slide, an executive summary, one slide per subtopic with a chart, an outliers slide, and a sources slide.
- A one-paragraph executive summary printed to chat alongside absolute paths to both files.

The orchestrator never sees raw web page content. All web research happens inside drilldown subagents whose context windows are isolated from the parent.

## Architecture

```
research (orchestrator skill, runs in parent context)
├── Phase 1: Topic decomposition (interactive, AskUserQuestion)
├── Phase 2: drilldown-agent x N (parallel subagents, each loads drilldown skill)
├── Phase 3: outlier-agent (single subagent, loads outlier-detection skill)
├── Phase 4: Excel generation (in-context, uses vendored xlsx skill + openpyxl)
├── Phase 5: deck-builder (subagent)
│           └── chart-agent x M (parallel sub-subagents, loads chart-generation skill)
└── Phase 6: Final delivery (in-context)
```

Every handoff is governed by a strict JSON contract documented at `.claude/skills/research/references/output-contracts.md`. The orchestrator validates returns against the schemas and retries once on malformed output before degrading gracefully.

## File tree

```
skillchain/
├── README.md                                # this file
├── .venv/                                   # Python venv with openpyxl, python-pptx, matplotlib
├── .claude/
│   ├── skills/
│   │   ├── research/                        # top-level orchestrator
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       ├── output-contracts.md      # JSON schemas for every handoff
│   │   │       └── checkpoint-layout.md     # run directory layout, resume rules
│   │   ├── drilldown/SKILL.md               # per-subtopic web research
│   │   ├── outlier-detection/SKILL.md       # cross-subtopic anomaly detection
│   │   ├── chart-generation/                # single-chart PNG rendering
│   │   │   ├── SKILL.md
│   │   │   └── scripts/render_chart.py
│   │   ├── xlsx/                            # vendored from anthropics/skills
│   │   └── pptx/                            # vendored from anthropics/skills
│   └── agents/
│       ├── drilldown-agent.md               # web + write tools, loads drilldown skill
│       ├── outlier-agent.md                 # read + write only, loads outlier skill
│       ├── deck-builder.md                  # read/write/bash/agent, spawns chart-agents
│       └── chart-agent.md                   # read/write/bash, loads chart skill
├── tests/
│   └── sample-invocation.md                 # walkthrough you can re-run
└── research-output/                         # run artifacts land here
    └── run-YYYYMMDD-HHMMSS-<rand>/
        ├── manifest.json
        ├── subtopics.json
        ├── drilldown/<slug>.json
        ├── drilldown-index.json
        ├── outliers.json
        ├── charts/<slug>.png
        ├── report.xlsx
        └── deck.pptx
```

## Setup

This repo expects a Python 3.13 venv at `.venv/` with three packages installed:

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python openpyxl python-pptx matplotlib
```

The orchestrator and deck-builder reference `.venv/bin/python` directly. If you place the venv elsewhere, update the path in `.claude/skills/research/SKILL.md` and `.claude/agents/deck-builder.md`.

The xlsx and pptx skills under `.claude/skills/` are vendored copies of `https://github.com/anthropics/skills/tree/main/skills/xlsx` and `.../pptx`. Update them by re-cloning that repo and copying the latest versions.

## Invoking the pipeline

There are two entry points. Both end up in the same place; choose based on whether you want a quick prose start or guaranteed pre-flight.

**Recommended: the `/research` slash command.**

```
/research impact of remote work on commercial real estate
```

The command verifies the venv, the Python deps, and the presence of every skill and agent file before it does anything. Then it asks three quick scoping questions (audience, scope and time frame, seed materials) so the pipeline can target the right angle from the start. Then it hands off to the `research` skill with a structured brief.

**Alternate: natural language.**

> Research the impact of remote work on commercial real estate.

The `research` skill description matches that phrasing and triggers automatically. The orchestrator will propose 5 subtopics via AskUserQuestion, fan out drilldowns once you confirm, and produce the deliverables. The skill applies sensible defaults for audience and scope when invoked this way (executive audience, current-state broad survey, no seed materials). Use this path when you trust the defaults and want the lowest-friction start.

Expect the full pipeline to take a few minutes either way depending on web latency and the number of subtopics.

For a low-stakes test that does not consume much web budget, see `tests/sample-invocation.md`.

## Extending

The pipeline is built around the principle that any single skill should be replaceable without touching the orchestrator. The contracts in `output-contracts.md` are the only coupling.

To swap the drilldown skill for an improved version, edit `.claude/skills/drilldown/SKILL.md`. The orchestrator does not care how drilldown produces its JSON, only that the JSON matches the schema. Same for outlier-detection and chart-generation.

To add a new phase (say, a fact-checking pass between drilldown and outlier-detection), add a new skill, a new agent that loads it, a new schema in `output-contracts.md`, and a new phase block in the orchestrator's SKILL.md. The existing phases need no changes as long as the new phase consumes and produces files compatible with what flanks it.

To reuse the drilldown skill in a different pipeline, point a different orchestrator at `.claude/skills/drilldown/SKILL.md`. The drilldown skill has no dependencies on the research orchestrator; it just expects a subtopic, a framing sentence, and an output path.

## Design choices worth knowing about

- **Subagent tool scoping.** Every agent's `tools` frontmatter field whitelists exactly the tools that stage needs. Drilldown gets web; outlier gets none; deck-builder gets file plus Agent for recursion; chart-agent gets file plus Bash. This is the primary defense against context bloat and accidental drift.
- **Parallelism.** Drilldown subagents and chart subagents are spawned in a single response with multiple Agent calls. Sequential spawning would defeat the point. The orchestrator and deck-builder have explicit instructions to parallelize.
- **Checkpointing.** Every phase writes its artifact to disk before moving on, and the manifest tracks completed phases. If a run fails partway, re-invoking with the same topic resumes at the first missing artifact.
- **No raw content in parent context.** Drilldown subagents do all the WebFetch work; they distill before returning. The orchestrator only ever reads structured JSON.
- **Strict schemas with graceful degradation.** Returns are validated, retried once on failure, and marked degraded after the second failure. The pipeline never aborts because one subtopic or chart failed.

## Limitations and known caveats

- The pptx skill's "create from scratch" path uses pptxgenjs (Node.js), which is not installed here. Deck-builder uses python-pptx instead and applies the design guidance from the pptx skill body. Deck visual polish is therefore at the level python-pptx supports, which is solid but less rich than pptxgenjs.
- The drilldown agent uses `WebSearch` and `WebFetch`; if you are running in an environment where those tools are unavailable, drilldowns will fail. The orchestrator will mark all subtopics as degraded and produce empty deliverables. Consider that an early-warning signal rather than a normal mode.
- `subagent_type` values resolve to project-level agents under `.claude/agents/`. If your Claude Code build does not auto-register them, the orchestrator's spawning will fail with an unknown-agent error. In that case, replace `subagent_type: drilldown-agent` with `subagent_type: general-purpose` and prepend the skill-loading instruction explicitly to each Agent call's prompt.
