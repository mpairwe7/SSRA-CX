---
name: pr-ci-coderabbit-workflow
description: Mandatory Git branching, Pull Request, CI resolution, and CodeRabbit review workflow for all changes. Trigger before any git push, commit, or PR operation: always push changes via a feature/fix branch, open a PR against main, watch and fix any CI failures, inspect and resolve all CodeRabbit/reviewer comments, and merge only when CI is 100% green.
---

# pr-ci-coderabbit-workflow — Feature Branch -> PR -> Green CI + CodeRabbit -> Merge

Never push commits directly to `main`. Every code, configuration, knowledge-base, or documentation change must land via a reviewed Pull Request with 100% green CI and resolved CodeRabbit/review comments.

## Non-Negotiable Workflow Steps

1. **Authenticate as `mpairwe7` (`gh-mpairwe7` skill):**
   ```bash
   ~/bin/gh auth switch --user mpairwe7
   ~/bin/gh api user --jq .login   # must output: mpairwe7
   ```
   Always invoke `~/bin/gh` (never bare `gh`).

2. **Branch from latest `main`:**
   ```bash
   git checkout main && git pull --ff-only origin main
   git checkout -b <feat|fix|chore>/<descriptive-slug>
   ```

3. **Run local quality gates before pushing:**
   ```bash
   task gen && task lint && task test && task eval
   ```

4. **Commit & push the feature branch (no auto-closing issue keywords per `no-issue-autoclose`):**
   - Use Conventional Commits with bare issue references `(#N)` only — never `fixes #N`, `closes #N`, or `resolves #N`.
   - Re-authenticate immediately before `git push`:
   ```bash
   ~/bin/gh auth switch --user mpairwe7
   ~/bin/gh api user --jq .login
   git push -u origin <branch-name>
   ```

5. **Open a Pull Request against `main`:**
   ```bash
   ~/bin/gh auth switch --user mpairwe7
   ~/bin/gh api user --jq .login
   ~/bin/gh pr create --base main --head <branch-name> --title "<type>(<scope>): <summary> (#N)" --body "<detailed summary & test plan>"
   ```

6. **Watch CI & Resolve Any Failures Immediately:**
   ```bash
   ~/bin/gh pr checks <PR_NUMBER> --watch
   ```
   - If any check fails, inspect logs with `~/bin/gh run view <RUN_ID> --log-failed`, fix the root cause on the feature branch, re-authenticate as `mpairwe7`, push the fix commit, and re-run `~/bin/gh pr checks <PR_NUMBER> --watch` until every check is green.

7. **Inspect & Resolve All CodeRabbit (`coderabbitai[bot]`) and Reviewer Comments:**
   ```bash
   ~/bin/gh auth switch --user mpairwe7
   ~/bin/gh api user --jq .login
   ~/bin/gh api repos/mpairwe7/SSRA-CX/pulls/<PR_NUMBER>/comments
   ~/bin/gh api repos/mpairwe7/SSRA-CX/pulls/<PR_NUMBER>/reviews
   ~/bin/gh api repos/mpairwe7/SSRA-CX/issues/<PR_NUMBER>/comments
   ```
   - Address every actionable CodeRabbit or human review comment in a follow-up commit on the feature branch, re-authenticate (`~/bin/gh auth switch --user mpairwe7 && ~/bin/gh api user --jq .login`) immediately before pushing or replying to review threads, and wait for CI + CodeRabbit re-verification.

8. **Merge Only When CI is 100% Green & Sync `main`:**
   ```bash
   ~/bin/gh auth switch --user mpairwe7
   ~/bin/gh api user --jq .login
   ~/bin/gh pr merge <PR_NUMBER> --squash --delete-branch
   git checkout main && git pull --ff-only origin main
   ```
