# Code host: GitHub

Use this when `code_host` is `github` and the `gh` CLI is logged in. Then the
repository's `origin` is on GitHub: github.com or a GitHub Enterprise host.
Run the commands in the task worktree. Replace `<...>` placeholders; never
invent a value.

## Check access

```bash
git remote -v
gh auth status
```

No remote, `gh` missing or not logged in: there is no usable code host. Follow
[host-none.md](host-none.md) instead and say why in your report.

## Find or open

Find an existing PR for the branch first and update it instead of creating a
duplicate:

```bash
gh pr list --head <branch> --json number,url
```

Create the PR after the push. Write the description to a file first. Add no
assignees, reviewers, labels, auto-merge or branch deletion unless the
repository's rules or the human say so:

```bash
git push -u origin <branch>
gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>
```

Re-read it and check base, head, commits and the diff size:

```bash
gh pr view <number> --json url,baseRefName,headRefName,commits
```

Find the repository and the PR of the current branch for the comment loop:
`gh pr view --json number,url,headRepository`.

## Review threads

List threads with their state, one page of up to 100:

```bash
gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id isResolved path line comments(first:20){nodes{databaseId author{login} body}}}}}}}' -f o=<owner> -f r=<repo> -F n=<number>
```

A thread is the human's when its first comment's `author.login` is the human's
account (in a solo flow, the PR author). If the login is unclear, fix nothing
and say so.

## Reply and resolve

Reply in a thread only for an invalid or inapplicable comment, with the reason.
Use the `databaseId` of the thread's first comment:

```bash
gh api -X POST repos/<owner>/<repo>/pulls/<number>/comments/<commentId>/replies -f body="<text>"
```

Resolve a fixed thread after the push:

```bash
gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -f id=<threadId>
```

## Checks and approval

```bash
gh pr checks <number>
gh pr view <number> --json reviewDecision,mergeStateStatus
```

Green: every required check passes. Approval: `reviewDecision` is `APPROVED`,
or the repository requires none and the human said to merge.

## Merge

Merge with the repository's usual method. Use the flag the human or the
repository rules name (`--squash`, `--merge` or `--rebase`) and add no flags of
your own:

```bash
gh pr merge <number> --<squash|merge|rebase>
gh pr view <number> --json state,mergedAt,mergeCommit
```

No method named by the human or the repository rules: do not pick one; stop
and report.

Re-read the PR and confirm it is merged.
