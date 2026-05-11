# AGENTS.md

Unified rules for any AI coding agent (Cursor, Codex, Claude, etc.) working in this repository. These rules apply to **every task** unless the user explicitly overrides them in the prompt.

## Project context

- This repository is a take-home submission: a regex pattern matching and replacement web app.
- **Backend:** Django + Django REST Framework (in `backend/`).
- **Frontend:** React + TypeScript + Vite (in `frontend/`).
- **Deliverables target:** the submission must satisfy the take-home brief **exactly** — no extra scope, no missing items. If a change risks moving away from the brief, stop and confirm with the user first.

## Language and tone

- **All user-facing text must be in English.** This includes README, UI copy, error messages, API responses, comments shown in exports, commit messages, and PR descriptions.
- Internal agent ↔ user chat may use the user's language, but anything written into the codebase is English-only.
- README must stay **polished and recruiter-friendly**: clear structure, no TODO leaks at submission time, working links, and a quick-demo path that a reviewer can follow in under 5 minutes.

## Change philosophy

- Prefer **minimal, production-like changes**. No overengineering, no speculative abstractions, no new dependencies unless clearly justified.
- Match the existing style and module boundaries (see `backend/api/` separation: `parsing.py`, `regex_llm.py`, `transform_apply.py`, `storage.py`, `views.py`).
- Keep the security/safety posture already in place: bounded in-memory store, regex validation, formula-injection escaping, cell-length limits, literal replacements.
- Do not commit secrets, `.env`, `backend/.venv`, `backend/db.sqlite3`, `frontend/node_modules`, `frontend/dist`, or `__pycache__`.

## Workflow for every task

1. **Plan first.** Before editing code, post a short plan: what you'll change, which files, and why. Wait for approval on non-trivial work.
2. **Implement the smallest change that satisfies the requirement.**
3. **Report back with three sections:**
   - **Changed files** — bullet list with one-line purpose each.
   - **Commands run** — exact commands, copy-pasteable, with the working directory.
   - **How to verify** — concrete steps a reviewer can follow (URLs, inputs, expected outputs, test commands).
4. **Deployment checklist.** After any user-visible or config-affecting change, append an updated deployment checklist covering env vars, build steps, and anything the reviewer needs before the live demo works.

## Verification requirements

- Backend changes: run `python manage.py test` from `backend/` and report the result.
- Frontend changes: run `npm run lint` and `npm run build` from `frontend/` and report the result.
- If a change cannot be verified locally, say so explicitly instead of claiming success.

## When in doubt

- If the take-home brief, the README, and the code disagree, ask the user which one to treat as source of truth before changing code.
- If a request would add scope beyond the brief, flag it and propose the minimal alternative first.
