---
name: research
description: "Use this skill when the user asks for a research report, briefing, deck, or workbook on a topic and wants both an Excel file and a PowerPoint deck as deliverables. Trigger phrases include 'research X', 'produce a research report on X', 'build a research deck on X', 'I need a briefing on X', 'do a deep dive on X with slides', or 'put together findings on X with charts'. The skill orchestrates a multi-stage pipeline: it decomposes the topic into subtopics with the user, fans out parallel web research subagents, runs cross-subtopic anomaly detection, builds a multi-sheet xlsx, and assembles a chart-rich pptx. Do NOT trigger for narrow factual lookups, single-source summaries, or tasks where no spreadsheet/deck is wanted."
---

# Research Orchestrator

This skill drives a research-report pipeline end to end. It runs entirely in the parent context window and delegates heavy work (web research, anomaly detection, deck building) to subagents that have isolated context windows. The orchestrator never reads raw web pages or article text. It only handles structured JSON returns from subagents.

The skill assumes Anthropic's `xlsx` and `pptx` skills are vendored locally at `.claude/skills/xlsx/` and `.claude/skills/pptx/`, and that the project venv at `.venv/` has `openpyxl`, `python-pptx`, and `matplotlib` installed.

## Core principle: composability

Every handoff in this pipeline is a strict JSON contract documented in `references/output-contracts.md`. Read that file once at the start of every run. Treat each subagent's return as untrusted: validate the schema, retry on failure, and degrade gracefully when retries fail. The orchestrator is responsible for keeping the pipeline alive even when individual subtopics or charts fail.

When you delegate, give the subagent only what it needs. Pass file paths instead of file contents wherever possible. Subagents write artifacts to disk and echo a small confirmation block; the orchestrator can re-read from disk if needed.

## Run setup

At the top of every run, before doing any research, do all of the following.

First, parse the input brief. The skill may be invoked in two ways. Direct natural-language invocation supplies just a topic string. The `/research` slash command supplies a structured brief in this shape:

```
Topic: <topic>
Audience: <executive | technical | general reader>
Scope: <current state, broad survey | historical and current | forecast and forward-looking | deep on 2 to 3 angles>
Seed materials: <pasted links or notes, or "none">
```

If a structured brief is present, extract the four fields and remember them; they bias later decisions. If only a topic is present, use defaults: audience "executive", scope "current state, broad survey", seed materials "none". Persist the parsed brief into `manifest.json` under a `brief` key so subsequent phases (and resumes) see the same context.

Then generate a run identifier of the form `run-YYYYMMDD-HHMMSS-<4randhex>`, create the run directory at `./research-output/<run-id>/` with subdirectories `drilldown/` and `charts/`, and write `manifest.json` with the original topic, the timestamp, the parsed brief, and an empty `phases` object. The manifest is the resume key: every phase appends to it on completion. If the user re-invokes this skill with the same topic and asks to resume, look for the most recent matching manifest in `./research-output/` and re-enter at the first phase whose entry is missing.

Read `references/output-contracts.md` and `references/checkpoint-layout.md` now. They are short. They tell you exactly what every subagent expects to receive and return, and which file in the run directory marks each phase complete.

## Phase 1: Topic decomposition (in-context, interactive)

Decompose the topic into 3 to 7 subtopics that together cover the question. Aim for subtopics that are independently researchable, that do not heavily overlap, and that together produce a balanced view (history, current state, key players, controversies, future outlook is a reasonable default skeleton, but adapt to the topic).

Bias the decomposition by the scope answer in the brief. "Current state, broad survey" yields 5 to 7 subtopics across the topic with a recency tilt. "Historical and current" reserves 1 to 2 subtopics for origin and evolution and trims current-state coverage proportionally. "Forecast and forward-looking" emphasizes trend-projection and expert-outlook subtopics. "Deep on 2 to 3 angles" produces exactly 3 subtopics, each with a richer framing sentence so drilldowns spend more depth per topic.

Bias the framing sentences by the audience answer. Executive framing emphasizes business implications. Technical framing emphasizes methodology and primary sources. General-reader framing emphasizes plain language and broader context. The framing sentence is what each drilldown agent receives as its operating brief, so this is where audience targeting takes hold.

Use the AskUserQuestion tool to confirm the candidate subtopics. Present them along with a one-line reminder of the audience and scope so the user can sanity-check that the candidates match the intended angle. Allow the user to accept, edit, or replace. If after the round-trip the user has fewer than 3 confirmed subtopics, propose two more and re-confirm. If the user picks more than 7, ask them to drop down to 7 (the fan-out is parallel and 7 is a soft ceiling for clean handling; more than that and the orchestrator's parsing context starts to bloat).

Write `subtopics.json` to the run directory: an array of `{slug, name, framing}` objects where `slug` is a filesystem-safe lowercase id, `name` is the human-readable subtopic, and `framing` is a one-sentence framing of what the drilldown should focus on for that subtopic. Append `phase1_decomposition` to the manifest's `phases` map with the absolute path to `subtopics.json`.

## Phase 2: Drilldown fan-out (parallel subagents)

Spawn the drilldowns in parallel. This means: emit a single assistant turn that contains one Agent tool call per confirmed subtopic, all using `subagent_type: drilldown-agent`. Do not loop with one Agent call per turn; that serializes the work and defeats the point of parallelism.

Each Agent call's prompt must include the subtopic name, the framing sentence, the original topic for context, the absolute output path `./research-output/<run-id>/drilldown/<slug>.json`, the audience tag from the brief, and (if non-empty) the seed materials block. The audience tag tells the drilldown which kinds of sources to prioritize: "executive" prefers analyst reports and reputable summaries, "technical" prefers primary sources and methodology-rich documents, "general reader" prefers explanatory pieces from established outlets. Seed materials, if supplied, should be passed as a fenced block labeled "Seed materials provided by user; treat as authoritative starting points and verify with additional web sources."

Append a one-line reminder of the output contract: "Return your final message with a single fenced ```json block tagged drilldown-result that matches the schema in `.claude/skills/research/references/output-contracts.md`."

When all subagent returns come back, parse each one. Extract the `drilldown-result` JSON block from the agent's final message. Validate it against the schema. If validation fails, re-spawn that single drilldown once with the prompt prefixed: "Your prior return was malformed. Match the schema strictly. Schema reminder follows." If the second attempt also fails, mark that subtopic as `degraded: true` in the manifest and exclude it from outlier input, but keep the partial JSON file on disk for inspection.

After validation, write `drilldown-index.json` listing each subtopic slug, its file path, and a degraded flag. Append `phase2_drilldown` to the manifest with the path to `drilldown-index.json`.

## Phase 3: Outlier detection (subagent)

Spawn a single Agent call with `subagent_type: outlier-agent`. Pass the absolute path to `drilldown-index.json` and an output path `./research-output/<run-id>/outliers.json`. The outlier agent reads each non-degraded drilldown, runs the analysis described in `.claude/skills/outlier-detection/SKILL.md`, writes its result to disk, and echoes the JSON in its final message.

Validate against the `outlier-result` schema in `references/output-contracts.md`. Retry once on malformed return. If still malformed, fall back to writing an empty result (`{"anomalies": [], "summary": "Outlier detection failed; no anomalies recorded."}`) and continue. Append `phase3_outliers` to the manifest.

## Phase 4: Excel workbook (in-context)

This phase runs in the orchestrator's context. It is mechanical and cheap. Read all drilldown JSONs and the outliers JSON from disk. Use the vendored `xlsx` skill at `.claude/skills/xlsx/` for any guidance on formatting conventions, but generate the file with `openpyxl` from the project venv.

Run the workbook generation by calling `.venv/bin/python` with a small inline script. The workbook must contain, in this order:

1. A `Summary` sheet with columns: Subtopic, Summary, ClaimCount, DataPointCount, Limitations, Degraded.
2. One sheet per subtopic, named with the subtopic slug, containing two stacked tables: a Claims table (claim, source_url, confidence) and a Data Points table (label, value, unit, source_url).
3. An `Outliers` sheet with columns: Type, Severity, Description, InvolvedSubtopics. If no anomalies, write a single row "None detected".
4. A `Sources` sheet listing every unique source URL across all drilldowns with the subtopic slug it came from.

Write the workbook to `./research-output/<run-id>/report.xlsx`. Append `phase4_xlsx` to the manifest.

## Phase 5: Deck assembly (subagent with recursive fan-out)

Spawn a single Agent call with `subagent_type: deck-builder`. Pass the absolute paths to `drilldown-index.json`, `outliers.json`, the run's `charts/` directory, and the desired output path `./research-output/<run-id>/deck.pptx`. The deck-builder loads the pptx skill, plans slides, fans out chart subagents in parallel, and assembles the final pptx.

The deck-builder's final message must end with `DECK_OK <absolute-path>` followed by a slide outline. Parse the outline for inclusion in the executive summary. If the deck-builder returns `DECK_FAIL <reason>`, retry once. If it fails again, fall back to producing a minimal pptx in-context using `python-pptx` directly (one title slide and one bullet slide per subtopic, no charts), and note the degradation in the final report. Append `phase5_pptx` to the manifest.

## Phase 6: Final delivery (in-context)

Compose a one-paragraph executive summary by stitching the highest-signal sentence from each drilldown's `summary` field, plus a single sentence about the most severe outlier (if any). Keep the paragraph under 120 words.

Output to the user: the absolute path to the .xlsx, the absolute path to the .pptx, and the executive summary paragraph. Mention any degradations explicitly so the user knows which parts of the pipeline ran without full data.

Append `phase6_delivery` to the manifest with a timestamp. The run is now complete.

## Resuming a failed run

If invoked with a topic that already has a recent run directory, scan the manifest. The first phase key missing from `phases` is the resume point. Re-enter at that phase, reusing on-disk artifacts from earlier phases. Do not re-do completed phases unless the user explicitly asks for a fresh run.

## Failure modes worth handling explicitly

A drilldown returning a JSON object that parses but fails schema validation should be retried once with a strict reminder. A drilldown returning no JSON block at all should be retried once with a clear contract reminder. A subagent that errors out should be re-spawned once. After the second failure, mark degraded and continue. Never abort the pipeline because one subtopic failed; the user wants whatever can be produced.

If the topic decomposition itself fails (the user keeps rejecting suggestions), ask the user to provide the subtopics directly. Do not invent a workaround that bypasses the user's confirmation.

If the venv is missing or Python deps are absent, stop the pipeline and ask the user to run the setup steps in the project README before retrying. Do not silently fall back to a deck-less or sheet-less output.
