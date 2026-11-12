---
name: code-review
description: Use when an orchestrator reviewer subagent must review one task's uncommitted diff or re-review its fixes in the orchestrator plugin's flow.
disable-model-invocation: true
---

# Code review

Goal: prove that the change meets the requirements and fits the codebase. Do
not hunt for a number of findings. Work strictly read-only: never edit, format,
commit, push or comment on a PR. Do not review code you wrote.

## Context to read first

State the scope, then read:

- the task, acceptance criteria and the approved plan (`01-plan.md`);
- the change journal (`changes-N.md`) and, on a re-review, the previous report;
- the `custom-<name>-N.md` journals and instruction files of writing custom
  roles, when the brief has them: their changes are in scope of the same diff;
- the root and nearest `AGENTS.md` / `CLAUDE.md` and local conventions;
- base and head, `git status`, the full diff (`git diff`, plus new untracked
  files), call sites of every changed symbol;
- results of the checks the brief names.

A missing source or stale evidence is a gap. Name it. Do not fill it with a
guess and do not call the review complete.

Use Bash only for read-only git commands (`git diff`, `git status`, `git log`,
`git show`, `git grep`) and for read-only checks the brief asks for.

## What to check

For every row give a finding or write that the category was checked with no
findings.

| Category | Prove |
|---|---|
| Requirements and plan | Every scenario and acceptance criterion is implemented; the diff stays inside the plan; negative cases are handled |
| Single source of truth | Each value has one owner and a clear lifetime; derived state is not stored without a reason |
| Duplication | No second path next to an existing function, service or helper; search the codebase, not only the diff |
| Abstractions | A new abstraction has a reason, an owner and a contract; no wrapper without its own responsibility |
| Unused code | Every new symbol is used in this diff; no code "for later" and no dead code |
| Error handling | Errors are not swallowed; failure paths leave a consistent state; messages help |
| Concurrency and lifecycle | Races, cancellation, retries, ordering, resource cleanup, repeated runs |
| Data and contracts | Mapping, nullability, persisted formats, migrations, backward compatibility |
| Security | Input validation, injection, authorization, secrets, unsafe file or network use |
| Tests | Tests check behaviour and negative cases, not the implementation; they fail without the change |
| Conventions | Naming, structure, formatting and commands from `AGENTS.md` / `CLAUDE.md` and neighbouring code |
| Scope creep | No unrelated refactors, renames or drive-by edits |
| Route check | Only when the brief gives the settings path: the agent calls in `state.md` match `settings.json` (roles off, custom roles, model, effort); minor, major only when the wrongly run role changed the diff |

Do not trust the brief or the journal as proof. Check the real code and its
dependencies.

## Severity

- `blocker` — wrong behaviour, data loss, security hole, broken build or tests.
  Must be fixed.
- `major` — likely bug, race, missing error handling, contract break, missing
  test for a risky path. Must be fixed.
- `minor` — real but low-impact issue: duplication, naming, small cleanup. Does
  not block the PR; it goes into the PR description.
- `nit` — taste. Max a few; never blocks.

## Report format

The first line is the verdict with the finding count, in exactly this form:

`APPROVE (<n> findings)` · `REQUEST CHANGES (<n> findings)` ·
`BLOCKED (<n> findings): <reason>`

- `APPROVE` = no open blocker or major finding; the PR may be published. Minor
  findings and nits listed under an APPROVE are not fixed before publishing;
  the publish implementer lists them in the PR description under "Known minor
  findings".
- `REQUEST CHANGES` = at least one blocker or major.
- `BLOCKED`: the review cannot be done (missing diff, unreadable worktree,
  missing evidence). The reason says exactly what is missing.

Then findings, ordered by severity. Each finding has:

1. a short title and severity;
2. `path:line`;
3. the problem and its observable consequence;
4. a concrete fix in the layer that owns the behaviour.

Do not retell the diff. Do not add a finding without a consequence. After the
findings list the categories checked with no findings, the residual risks, the
scope, and the limits of the evidence. With no findings say so and still give
scope and limits.

Return the report as your answer. The orchestrator saves it as `review-N.md`.
Write no files.

## Re-review

Check only the fixes of the previous pass and the previous findings: is each one
fixed, rejected with a valid reason, or still open. Look at new code only where
the fixes touched it. A new problem outside the fixes is a finding only if it is
a blocker or major. First line is the verdict as usual.

## After the report

The development side fixes every confirmed blocker and major finding without
asking the human. It may reject a technically wrong finding with a reason. A
change of the approved plan goes to the human.
