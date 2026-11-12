# Code host: GitLab

Use this when the repository's `origin` is on GitLab (gitlab.com or a
self-managed host) and the `glab` CLI is logged in. GitLab calls a pull request
a merge request (MR); this plugin keeps the words "PR" and "pull request". Run
the commands in the task worktree. Replace `<...>` placeholders. `<iid>` is the
MR number shown in the MR URL. In API paths `:fullpath` is filled by `glab`
from the repository of the current directory.

## Check access

```bash
git remote -v
glab auth status
```

For a self-managed host add `--hostname <host>` to `glab auth status`. No
remote, `glab` missing or not logged in: there is no usable code host. Follow
[host-none.md](host-none.md) instead and say why in your report.

## Find or open

Find an existing MR for the branch first and update it instead of creating a
duplicate:

```bash
glab mr list --source-branch <branch> -F json
```

Create the MR after the push. `glab mr create` has no body-file flag, so pass
the description file's text. Add no assignees, reviewers, labels, auto-merge or
branch deletion unless the repository's rules or the human say so:

```bash
git push -u origin <branch>
glab mr create --source-branch <branch> --target-branch <base> --title "<title>" --description "$(cat <file>)" --yes
```

Re-read it and check base, head, commits and the diff size:

```bash
glab mr view <iid> -F json
glab api projects/:fullpath/merge_requests/<iid>/commits
```

## Review threads

GitLab calls a thread a discussion. List them, all pages:

```bash
glab api --paginate "projects/:fullpath/merge_requests/<iid>/discussions?per_page=100"
```

A discussion is unresolved when one of its `notes` has `"resolvable": true`
and `"resolved": false`. Each note has `author.username`, `body` and, for a
diff comment, `position.new_path` and `position.new_line`. Find the human's
account with `glab api user`. A discussion is the human's when its first note
is by that account. If it is unclear, fix nothing and say so.

## Reply and resolve

Reply in a discussion only for an invalid or inapplicable comment, with the
reason:

```bash
glab api --method POST projects/:fullpath/merge_requests/<iid>/discussions/<discussionId>/notes -f body="<text>"
```

Resolve a fixed discussion after the push (`-F` sends the JSON boolean):

```bash
glab api --method PUT projects/:fullpath/merge_requests/<iid>/discussions/<discussionId> -F resolved=true
```

Leave invalid and unclear discussions open.

## Checks and approval

```bash
glab mr view <iid> -F json
glab api projects/:fullpath/merge_requests/<iid>/approvals
```

In the first output `detailed_merge_status` must be `mergeable`, and
`head_pipeline.status` must be `success` when the project has a pipeline. A
status such as `ci_must_pass`, `not_approved`, `discussions_not_resolved` or
`conflict` is a stop: report it. The second output shows `approved` and
`approvals_left`. For a branch pipeline run `glab ci status --branch <branch>`.

## Merge

Merge with the repository's usual method. Pass the flag the human or the
repository rules name (`--squash` or `--rebase`). The project's configured
merge method counts as the repository's rule: with no method named, pass no
method flag and do not stop. Add no flags of your own, except `--yes` to skip
the prompt and `--auto-merge=false` (glab schedules a merge by default while a
pipeline runs):

```bash
glab mr merge <iid> --yes --auto-merge=false
glab mr view <iid> -F json
```

Re-read the MR and confirm `state` is `merged`. If it is not merged, report it;
do not retry.
