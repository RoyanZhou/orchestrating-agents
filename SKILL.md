---
name: orchestrating-agents
description: Plans work and reviews results while separate worker agents (Codex, Claude Code, or any CLI agent) do the heavy lifting - research, evidence gathering, reports, coding, computer use, and DCC tool automation. Runs independent tasks in parallel, queues tasks that share a resource, keeps a live task roster, and wakes the orchestrator only on script-detected events. Use when the user asks to delegate, outsource, or parallelize work to another agent, or names this skill.
---

# Orchestrating Agents

You are the orchestrator. You do two light jobs: **plan** and **review**. Worker agents do all heavy work.

## 1. Confirm the setup

Collect these four items from the user before dispatching anything:

1. **Project**: the existing project to use, or approval to create a new one (propose a short kebab-case name).
2. **Worker**: `codex`, `claude`, or a custom CLI.
3. **Model** for the worker.
4. **Reasoning effort** for the worker.

Ask for every missing item in one message and wait for explicit answers. Start step 2 once all four are confirmed.

A project is one folder. Every task of this kind, including parallel threads, runs with that folder as its working directory, so the worker's app groups them together.

## 2. Plan

1. Read the user's context briefly (files, chat, constraints) and state the goal in a few lines.
2. Split the heavy work into tasks. Give each task one clear question or deliverable.
3. Mark exclusive resources per task: `screen` for computer use, an app instance such as `maya` or `unreal`, or a shared file set. Tasks with the same resource run one after another; all others run in parallel.
4. Write one brief per task from [references/brief-template.md](references/brief-template.md). Include the **visual evidence rule** below in every brief whose subject is visual (animation, video, UI, DCC tools, tutorials).
4a. Look at visual inputs yourself before writing briefs or asking the user questions. For a video, extract timestamped frames (for example `ffmpeg -vf "fps=2,drawtext=text='%{pts\:hms}'"` then `tile` into contact sheets) and read them. A question that one look at the input would answer must not reach the user.
5. Write `plan.json`:

```json
{
  "project": "mocap-weapon-research",
  "worker": "codex",
  "model": "<confirmed model>",
  "effort": "<confirmed effort>",
  "max_parallel": 4,
  "stall_minutes": 20,
  "show_windows": true,
  "tasks": [
    {"id": "T1_research", "brief": "briefs/T1_research.md",
     "deliverables": ["report.md", "sources.md"], "min_links": 8, "min_images": 4},
    {"id": "T2_maya_fix", "brief": "briefs/T2_maya_fix.md",
     "deliverables": ["result.fbx", "notes.md"], "resources": ["screen", "maya"],
     "depends_on": ["T1_research"]}
  ]
}
```

Project layout:

```
<project>/
  plan.json
  briefs/<id>.md
  inputs/          shared read-only material
  outputs/<id>/    each worker writes only here, including its STATUS file
  logs/<id>.log
  .orch/           roster, events, state (managed by the script)
```

### Visual evidence rule

Text alone is not evidence for visual claims.

- **Input media**: a claim about what happens in a video, animation, or screenshot (a pose, a grip change, a penetration, a timing phase) needs a timestamped frame grab, saved under `outputs/<id>/evidence/` and embedded in the report next to the claim.
- **Tutorials and docs**: many tutorials carry the key step only in a screenshot, diagram, or video. Workers must open those images and watch the video (sample frames at the step), not only read page text. When a step is shown visually, include a screenshot of the menu, node graph, or setting, with the source URL and the video timestamp.
- **Reports**: every visual claim pairs with an image; set `min_images` in `plan.json` so the supervisor rejects a DONE without them.
- **Cross-check**: when data and footage disagree, or the data looks ambiguous, show both side by side before calling anything "drift" or "error".

## 3. Dispatch

```bash
python scripts/orchestrate.py start <project>
```

This starts a background supervisor, opens one live log window per task plus a roster window (Windows), and prints the roster. Show the roster to the user as a table: task, state, worker, resources, output folder.

## 4. Wait for events

```bash
python scripts/orchestrate.py wait <project>
```

`wait` blocks at zero token cost until the supervisor records new events, prints them, and exits.

- If your harness notifies you when a background command exits, run `wait` in the background.
- Otherwise run it in the foreground.

After handling each event, run `wait` again. Event types: `STARTED`, `PROGRESS ...`, `DONE`, `CHECK_FAILED`, `BLOCKED`, `FAILED`, `STALL`, `REQUEUED`, `ALL_DONE`.

## 5. Review

On `DONE`, review that task right away:

- Read the deliverables and check them against the brief's acceptance criteria.
- Verify evidence: open a sample of the links, confirm key claims trace to a source, run code or tests, inspect produced files.
- Open the evidence images and confirm each one actually shows what its caption claims. Reject visual claims that have no image.
- Accept the task, or write `outputs/<id>/REVIEW.md` with specific fixes and run `python scripts/orchestrate.py retry <project> <id>`.

On `BLOCKED`, `FAILED`, `CHECK_FAILED`, or `STALL`: read the tail of `logs/<id>.log`, fix the brief or environment, then `retry`.

After each review, give the user the updated roster in one short table.

## 6. Report

When `ALL_DONE` arrives and every task is accepted, merge the accepted results into one answer for the user, citing the task outputs and the evidence behind each conclusion.

## Commands

| Command | Purpose |
|---|---|
| `start <project>` | launch supervisor and print roster |
| `wait <project> [--timeout SEC]` | block until new events |
| `status <project> [--watch]` | print the roster |
| `retry <project> <id>` | re-run a task with its REVIEW.md |
| `stop <project>` | stop the supervisor and all workers |

To add work mid-run, append tasks to `plan.json`; the supervisor picks them up on its next loop.

Worker commands, custom workers, and platform notes: [references/workers.md](references/workers.md).
