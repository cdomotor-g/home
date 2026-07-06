# Repo conventions for Claude

## Branching & commits
- `main` is the single source of truth. Do not leave long-lived feature branches behind.
- When a task is complete, land the work on `main` as a single squashed commit
  (or a small number of clean commits) — avoid merge commits.
- Claude Code on the web creates a temporary `claude/*` working branch per session.
  Fold that branch into `main` when done and delete it. If the sandbox blocks branch
  deletion, rely on the GitHub "Automatically delete head branches" setting to clean
  it up after the PR merges.
- Prefer squash-merges for any PR so each change is one commit on `main`.

## GitHub Pages
- The site is served from the repo root by `.github/workflows/pages.yml`
  (Settings → Pages → Source must be "GitHub Actions").
- Keep `index.html` and `.nojekyll` at the repo root.
