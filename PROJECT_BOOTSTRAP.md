# Project Bootstrap Checklist

## 1. GitHub (server-side)
- [ ] main branch protection enabled
  - Require PR
  - Block direct push
  - CI required
- [ ] main is read-only by design

## 2. Local safety
- [ ] review worktree created (detached HEAD from origin/main)
- [ ] pre-push hook blocks push to main

## 3. Branching model
- [ ] working branch: devenv (or feature/*)
- [ ] main only via PR

## 4. CI sanity
- [ ] tests run on push
- [ ] tests run on PR
- [ ] CI green == merge allowed

## 5. AI init rules
- [ ] make sure ChatGPT remembers to always include in the 1st AI promt in any session instruction to read and follow the rules from the PROJECT_GUARDRAILS.md file
- [ ] run /init command in Claude code CLI to create and fill the file CLAUDE.md especially if the project is not empty
- [ ] if the project is new and empty make sure that Claude code CLI will create it and keep actualized through all the following project implementation cycles

## 6. AI workflow rules
- [ ] AI works only in non-main branches
- [ ] tests must be green before push
- [ ] AI output checked via diff (Devart)
