---
name: drilldown
description: "Use this skill when a single subtopic needs deep, web-sourced research delivered as a strict JSON summary that another tool or agent will parse. Trigger when invoked by an orchestrator (such as the research skill) that supplies a subtopic name, a framing sentence, and an output JSON path. Also trigger when a user directly asks for 'a structured deep dive on X with sources' or 'research X and return JSON'. The deliverable is always a JSON file matching the drilldown-result schema, with key claims, numeric data points, source URLs, and recommended charts. Do NOT trigger for prose summaries, chat-style answers, or research that does not need to be machine-parseable."
---

# Drilldown

This skill is the per-subtopic research worker. It is designed to be invoked inside an isolated subagent context so that the heavy raw-page content from web fetches stays out of the parent orchestrator's window. Whoever invokes it supplies a subtopic, a framing sentence, and an output path. The deliverable is a JSON file at the output path plus the same JSON echoed in the agent's final assistant message inside a fenced block tagged `drilldown-result`.

The output schema is the source of truth. It lives at `.claude/skills/research/references/output-contracts.md` under the `drilldown-result` heading. Read it now if you have not already. The orchestrator will reject any return that does not match.

## Workflow

Start by running 3 to 5 web searches that triangulate the subtopic. Use diverse angles: the bare subtopic name, the subtopic plus "statistics" or "data" for quantitative coverage, the subtopic plus "criticism" or "counterpoint" for balance, and a recency-biased query like "2024" or "2025" or "current" depending on whether time-sensitive data is wanted. Keep search queries short and concrete; long natural-language queries underperform in WebSearch.

From the search results, pick the 3 to 5 most authoritative-looking sources. Prefer primary sources (research papers, official statistics, regulator publications, industry reports) over derivative ones (blog summaries of those primaries). When in doubt, prefer sources with clear publication dates and authors. Skip pages that look like SEO-driven content farms.

Fetch each chosen source with WebFetch. Use a focused extraction prompt: ask WebFetch to pull out the main claims, any numeric facts with units and dates, and the page's bottom-line conclusions. Do not ask for a full summary; you want the raw substance, not another layer of distillation.

After all fetches complete (or fail), distill what you have into the output schema. Each `key_claim` should be one sentence, attached to the URL it came from, with a confidence rating that reflects how well-supported the claim is by the source. A claim from a peer-reviewed study or government statistic gets `high`; a claim from an industry blog gets `medium`; a claim that you had to infer or that the source hedged on gets `low`.

For `data_points`, prefer numeric values with units. Strings are allowed where the data point is genuinely categorical (for example, "primary regulator: FERC"). Each data point must carry its source URL.

For `recommended_charts`, propose at most 2 charts per subtopic. Each chart references data points by their indices in the `data_points` array. Pick chart types that fit the data: bar for categorical comparisons, line for time series, pie only when the parts genuinely sum to a meaningful whole, scatter for two-variable relationships. If `data_points` is empty, leave `recommended_charts` empty.

Populate `sources` with the deduplicated URLs you actually used (not just searched). Populate `limitations` with a one-sentence note about anything missing or shaky. Examples: "No data found from after 2023." "Sources skew US-centric." "Two sources contradicted on the headline number; lower-confidence flag applied to claim 2." Leave `limitations` empty only if the research was clean.

## Output contract enforcement

Write the JSON to the output path supplied by the caller. Then end your final assistant message with a single fenced block:

````
```json
// drilldown-result
{ ...same JSON... }
```
````

Nothing else after the fenced block. The orchestrator parses the message tail-first.

If a web fetch fails, do not fabricate the source. Mark the affected claim's confidence as `low` or drop the claim entirely, and note the failure in `limitations`. Always return a schema-valid JSON object even when research is thin; the orchestrator handles thinness, but it cannot handle missing or malformed JSON.

If the subtopic genuinely yields no usable sources (rare; almost any topic has something), return an object with empty `key_claims` and `data_points` arrays, empty `recommended_charts`, an empty `sources` array, and a `limitations` field that explains why. Do not invent fake citations to pad the response.

## Tools required

This skill expects to be loaded by an agent with `WebSearch`, `WebFetch`, `Read`, and `Write` available. If any of those tools is missing, stop and report `WebSearch and WebFetch are required for drilldown; the calling agent's tool scope is incomplete.`

## A note on length

The orchestrator never reads the raw web pages. Keep the JSON tight: short summary, short claims, short limitations. Quality of distillation matters more than volume. If a single drilldown JSON exceeds about 8 KB, you are over-quoting; tighten.
