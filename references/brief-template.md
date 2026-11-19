# Brief template

Copy into `briefs/<id>.md` and fill in. Keep it short and concrete.

```markdown
# <id>: <one-line task title>

## Context
<2-5 lines: the goal, what is already known, where inputs live (inputs/...)>

## Task
<numbered questions to answer or things to build>

## Standards
- Base claims on documented, industry-recognized, or open-source sources, each with a clickable link. Label your own inference as [inference].
- Visual evidence: every claim about a pose, motion, timing, UI step, or tutorial step comes with an image saved in outputs/<id>/evidence/ (timestamped frame grab, tutorial screenshot, or video frame with URL + timestamp) and embedded in the report next to the claim. Open tutorial images and sample tutorial videos; do not rely on page text alone.
- <task-specific standards: tool versions, code style, test commands>

## Deliverables (in outputs/<id>/)
- <file>: <what it must contain>
- STATUS: append one line per stage (PROGRESS <stage>); the last line is DONE, or BLOCKED <reason>.

## Acceptance check before writing DONE
- <measurable checks, e.g. "sources.md has at least 8 verified links", "tests pass with: <command>">
- <for visual topics: "at least N images in evidence/, each embedded in report.md with a caption saying what it shows">
```
