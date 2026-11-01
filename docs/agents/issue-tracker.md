# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations. The repository is `TomMcIver/Eco_Model`, inferred from the `origin` remote.

## Conventions

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state open --json number,title,body,labels,comments`
- Comment: `gh issue comment <number> --body "..."`
- Apply or remove labels: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- Close: `gh issue close <number> --comment "..."`

Use `gh` from this clone so it infers the repository.

## Pull requests as a triage surface

**PRs as a request surface: no.** Change this to `yes` only if external pull requests should enter the triage queue.

## When a skill says “publish to the issue tracker”

Create a GitHub issue.

## When a skill says “fetch the relevant ticket”

Run `gh issue view <number> --comments`.
