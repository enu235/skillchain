# Checkpoint Layout

Every run lives in `./research-output/<run-id>/`. The directory layout is fixed so the orchestrator can resume without ambiguity.

```
research-output/
└── run-YYYYMMDD-HHMMSS-<rand>/
    ├── manifest.json          # phase index; the resume key
    ├── subtopics.json         # phase 1 output
    ├── drilldown/
    │   ├── <slug-1>.json      # phase 2 outputs, one per subtopic
    │   ├── <slug-2>.json
    │   └── ...
    ├── drilldown-index.json   # phase 2 summary index
    ├── outliers.json          # phase 3 output
    ├── report.xlsx            # phase 4 output
    ├── charts/
    │   ├── <chart-slug-1>.png # phase 5 intermediate outputs
    │   └── ...
    └── deck.pptx              # phase 5 output
```

## manifest.json

```
{
  "topic": "the original user topic",
  "run_id": "run-YYYYMMDD-HHMMSS-<rand>",
  "created_at": "ISO-8601 timestamp",
  "phases": {
    "phase1_decomposition": {"path": "subtopics.json", "completed_at": "ISO-8601"},
    "phase2_drilldown": {"path": "drilldown-index.json", "completed_at": "ISO-8601"},
    "phase3_outliers": {"path": "outliers.json", "completed_at": "ISO-8601"},
    "phase4_xlsx": {"path": "report.xlsx", "completed_at": "ISO-8601"},
    "phase5_pptx": {"path": "deck.pptx", "completed_at": "ISO-8601"},
    "phase6_delivery": {"completed_at": "ISO-8601"}
  },
  "degraded_subtopics": ["slug-of-failed-subtopic"]
}
```

The orchestrator appends to `phases` only after successfully completing the phase. The first missing key (in canonical order) is the resume point. Phases must be re-entered in order; do not skip ahead.

## Resume rules

When `research` is invoked and the user mentions an existing run id (or asks to "resume"), do this:

1. Read `manifest.json` from that run directory.
2. Identify the first missing phase key in canonical order.
3. Re-enter at that phase, reusing all earlier artifacts from disk.
4. If a phase entry exists but the file it points to is missing or corrupt, treat that phase as missing and re-do it.
5. Do not re-prompt the user for subtopic confirmation if `phase1_decomposition` is already complete.

## Cleanup

Old runs are not auto-deleted. The user can `rm -rf research-output/<run-id>/` to discard a run. The orchestrator does not garbage-collect.
