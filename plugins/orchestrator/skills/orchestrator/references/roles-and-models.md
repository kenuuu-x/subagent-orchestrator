# Roles and models

Pass `model` (alias: `opus`, `sonnet`, `haiku`) and `effort` (`low`, `medium`,
`high`, `xhigh`) explicitly on every `Agent` call. Write both to `state.md`.
That is the route check: the session cannot observe the actual model of a
subagent. The hook denies an implementer call without `model`.

## Table by complexity class

| Role | Light | Medium | Hard |
|---|---|---|---|
| Scout `orchestrator:scout` | sonnet / medium | sonnet / medium | sonnet / high |
| Planner `orchestrator:planner` | opus / high | opus / high | opus / xhigh |
| Implementation `orchestrator:implementer` | sonnet / medium | sonnet / high | opus / medium (high if stuck) |
| Review `orchestrator:reviewer` | opus / medium | opus / high | opus / high (mandatory) |
| Tester `orchestrator:tester` | sonnet / medium | sonnet / medium | sonnet / medium |
| Review fixes / PR comments (new implementer, goals `review fixes`, `PR comments`) | sonnet / medium | sonnet / medium | sonnet / high; hard part: opus / medium |
| Publish: commit, push, PR (new implementer, goal `publish`) | sonnet / low | sonnet / medium | sonnet / medium |
| Re-review of small fixes `orchestrator:reviewer` | sonnet / high | sonnet / high | opus / high |
| Screenshots `orchestrator:visual-checker` | haiku / low | haiku / low | sonnet / medium |
| Merge (new implementer, goal `merge`) | sonnet / low | sonnet / low | sonnet / low |
| Merge base into branch, no conflicts (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Mechanics: issue labels/comments, running a given script (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Orchestrator session itself | sonnet / medium (opus also fine) | | |

Rules:

- Small fixes = up to ~200 changed lines since the last review, no shared
  contract change, no finding above "minor". Otherwise use the "Review" row.
- Merge base with conflicts: new implementer, goal `merge base`, sonnet / medium.
- Screenshot comparison against a design reference: sonnet / medium in any class.
- Text a human reads (commit messages, PR description) is written by sonnet,
  never haiku.
- Mechanics are narrow and checkable. Anything that needs judgment is not
  mechanics.

## Complexity class

Chosen by signals in the code, not by diff size. The planner names the class
with the signal and the file; the human approves it with the plan.

| Hard (opus) | Not hard (sonnet) |
|---|---|
| Concurrency: several async sources, cancellation, races, shared mutable state | New screen, page or component from a design |
| Lifecycle and state restoration, process/request lifetime, caching keys | Styling, themes, copy, previews |
| Data migrations, changes to persisted formats | Tests for existing logic |
| Offline cache, sync with a server, websockets, retries | Lint rule or config following an existing example |
| Public API used by two or more consumers: signature or behaviour change | Internal component of one module, new parameter with a default |

Classes: `light` (all signals are in the right column and the change is small),
`medium` (right column, but wide or touching several modules), `hard` (any
signal in the left column covers most of the task).

If only part of the task is hard, the plan lists `Hard part: <files>`. The main
implementer runs on sonnet. A separate short implementer on `opus` handles only
those files. Only the opus implementer brief carries `Complexity: hard` or
`Hard part: <files>`; the hook blocks it otherwise. The main sonnet brief
carries `Skip (separate opus pass): <files>` and must not change those files.

Stuck on sonnet (two attempts at the same error, or edits going in circles):
repeat the step with a new `opus` implementer. Do not keep pushing sonnet.

## Subagent economy

Each subagent step re-reads its whole history. Long history and images cost the
most.

- New implementer per pass. Continue an old one with `SendMessage` only if its
  history is under 200k tokens and it has been idle under 60 minutes (the hook
  enforces this). A short note to a running implementer is fine.
- Among the plugin's roles only `orchestrator:visual-checker` opens images
  (hook-enforced). The
  implementer lists screenshot paths in `changes-N.md`; everyone else reads
  `visual-N.md`.
- Long command output goes to `logs/`; read the tail and the errors only.
- Bulk file reading goes to the scout, which returns short summaries with paths
  and line numbers.
- Max 3 implementers in parallel: one subscription feeds every subagent.
- One review per task state. In a stack each PR is its own task: it is reviewed
  before its `publish`, and the next branch starts only after that `publish`.
- Do not wake yourself in loops. A background subagent notifies you when it
  finishes.

## Calling rules

- Background: implementers, reviewers, visual-checker, test runs.
  Foreground only when you need the answer to continue.
- A subagent returns a short answer and writes details to its file. You pass
  paths, not file contents.
- Subagents do not see your context. Everything they need is in the brief
  ([briefs.md](briefs.md)).
- `SendMessage` to the same planner for plan remarks. For implementers, only the
  conditions above.
- Address an existing subagent with `SendMessage` by its agent id recorded in
  `state.md`, never by name.
- Record every `Agent` call in `state.md`: role, model, effort, agent id.
