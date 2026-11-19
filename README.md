# orchestrating-agents

An [Agent Skill](https://agentskills.io) for running work through other agents. The agent that loads it is the **orchestrator**: it plans and reviews. **Worker** agents (Codex, Claude Code, or any CLI agent) do the heavy work: research, evidence gathering, reports, coding, computer use, and DCC tool automation.

- Runs independent tasks in parallel; queues tasks that share a resource (`screen`, `maya`, ...)
- Keeps a live task roster and opens one log window per task (Windows)
- Wakes the orchestrator only on script-detected events (`DONE`, `BLOCKED`, `STALL`, ...), so waiting costs no tokens
- Checks deliverables automatically and supports a review → retry loop

## Install

Copy this folder into your agent's skills directory:

```bash
git clone https://github.com/RoyanZhou/orchestrating-agents ~/.claude/skills/orchestrating-agents   # Claude Code
git clone https://github.com/RoyanZhou/orchestrating-agents ~/.codex/skills/orchestrating-agents    # Codex
```

Requires Python 3.8+ and a worker CLI (`codex` or `claude`) on the machine.

## Use

Ask your agent to delegate a task with this skill. It first confirms the project, worker, model, and reasoning effort, then plans, dispatches, and reviews.

```bash
python scripts/orchestrate.py start  <project>   # launch supervisor, print roster
python scripts/orchestrate.py wait   <project>   # block until next events
python scripts/orchestrate.py status <project>   # roster
python scripts/orchestrate.py retry  <project> <task_id>
python scripts/orchestrate.py stop   <project>
```

See [SKILL.md](SKILL.md) for the workflow and [references/](references/) for brief templates and worker commands.
