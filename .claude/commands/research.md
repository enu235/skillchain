---
description: Run the hierarchical research pipeline with pre-flight env and scoping checks
argument-hint: <topic>
---

You are about to launch the research pipeline. Before invoking the `research` skill, verify the environment and gather scoping context from the user. Do not skip the checks; the pipeline will fail late and confusingly if any precondition is missing.

## Topic

The user supplied: `$ARGUMENTS`

If `$ARGUMENTS` is empty or only whitespace, stop and ask the user for a topic with a single AskUserQuestion call (one free-text question via "Other"). Do not proceed with an empty topic.

## Step 1: Environment pre-flight (run silently unless something fails)

Run these checks via Bash. Bundle the independent ones in a single tool call where possible.

1. Confirm `.venv/bin/python` exists and is executable. If not, stop and tell the user to run the setup commands from `README.md` ("uv venv .venv --python 3.13" and the uv pip install line). Do not try to create the venv yourself.
2. Confirm the three Python deps import cleanly: `.venv/bin/python -c "import openpyxl, pptx, matplotlib"`. If this exits non-zero, stop and tell the user to re-run the uv pip install line from the README.
3. Confirm the four custom skill files exist: `.claude/skills/research/SKILL.md`, `.claude/skills/drilldown/SKILL.md`, `.claude/skills/outlier-detection/SKILL.md`, `.claude/skills/chart-generation/SKILL.md`. If any are missing, stop and report which.
4. Confirm the two vendored skills exist: `.claude/skills/xlsx/SKILL.md` and `.claude/skills/pptx/SKILL.md`. If missing, point the user at the "Setup" section of README.md.
5. Confirm the four agent files exist: `.claude/agents/{drilldown-agent,outlier-agent,deck-builder,chart-agent}.md`. If any are missing, stop and report.
6. Confirm `.claude/skills/chart-generation/scripts/render_chart.py` is present and executable.

If all checks pass, do not narrate them. A single line like "Environment OK." is enough so the user knows the checks ran.

## Step 2: Scoping pre-flight (interactive)

Use a single AskUserQuestion call with three questions. Do not split into multiple rounds; users dislike multi-step pre-flights. The questions and options:

**Question 1: Audience**
- header: "Audience"
- question: "Who is the primary audience for the deliverables?"
- options:
  - "Executive (Recommended)" / "High-level findings, business implications, light on methodology. Default tone."
  - "Technical" / "Detailed claims, methodology notes, primary sources prioritized over secondary."
  - "General reader" / "Plain language, broader context, less assumed knowledge."

**Question 2: Scope and time frame**
- header: "Scope"
- question: "What scope and time frame should the research cover?"
- options:
  - "Current state, broad survey (Recommended)" / "5 to 7 subtopics across the topic, focused on the last 2 to 3 years."
  - "Historical and current" / "Include origin and evolution, fewer current-state subtopics."
  - "Forecast and forward-looking" / "Emphasize trends, projections, and expert outlooks."
  - "Deep on 2 to 3 angles" / "Fewer subtopics, each researched more thoroughly."

**Question 3: Seed materials**
- header: "Seed materials"
- question: "Do you have prior research, links, or a brief to seed the pipeline?"
- options:
  - "No, start fresh (Recommended)" / "Drilldowns will discover sources from scratch via web search."
  - "Yes, I will paste links or notes" / "After this question, you will paste the materials in chat; the orchestrator will pass them as framing context to drilldowns."

If the user picks "Yes" on question 3, after AskUserQuestion returns, ask in plain text: "Paste the links or brief now. One block, no formatting required." Wait for their response before proceeding. Capture the pasted content as a string variable named `seed_materials`. If they pick "No", `seed_materials` is the empty string.

Geographic scope is intentionally not asked. If the topic implies a geographic bound (for example "US small-scale solar adoption"), respect it; otherwise let the orchestrator and drilldowns decide.

## Step 3: Hand off to the research skill

Once the env is verified and scoping is gathered, invoke the `research` skill via the Skill tool. The Skill tool's `args` parameter should pass the topic plus the gathered context as a structured brief. Use this format for the args string:

```
Topic: <the topic from $ARGUMENTS>
Audience: <answer from question 1>
Scope: <answer from question 2>
Seed materials: <seed_materials, or "none">
```

The `research` skill will read this brief at the start of its run, use the audience and scope answers to bias subtopic decomposition (for example, "Forecast and forward-looking" should produce more future-oriented subtopic candidates), and pass the seed materials as additional framing to each drilldown subagent.

## Step 4: Let the pipeline run

After invoking the skill, do not narrate every phase as it happens; the skill's own instructions cover phase-by-phase behavior, including the user-confirmation step for subtopics. Stay out of the way until the skill's final delivery message, then echo that delivery to the user.

If the skill aborts (for example because the user keeps rejecting subtopic candidates), report the abort plainly and ask whether they want to retry with a different angle.
