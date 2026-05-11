# Regex Pattern Matching and Replacement

A Django + React take-home that lets a user upload a CSV or XLSX, describe a text pattern in natural language, generate a Python `re` pattern with an LLM, preview real matches from the uploaded data, apply a literal replacement to a single column, and download the transformed table as CSV.

The implementation keeps the scope small while still showing production-oriented habits: clean module boundaries, validated inputs, bounded resources, and an explicit safety posture around regex execution, LLM output, and CSV export. Sample matches are computed from the uploaded file, not invented by the model.

## Quick demo

1. Start the backend and frontend (see [Local development](#local-development)).
2. Open `http://localhost:5173`.
3. Upload [`examples/sample_emails.csv`](examples/sample_emails.csv).
4. Select the `Email` column.
5. Enter the natural language instruction: `Find email addresses`.
6. Enter the replacement value: `REDACTED`.
7. Click `Generate pattern` and review the generated regex, explanation, and sample email matches.
8. Click `Apply transformation` and download the resulting CSV. The `Email` column should now contain `REDACTED` for every matched row.

If you do not have an OpenAI-compatible API key, you can still evaluate upload, regex validation, apply, preview, and download by entering this regex manually after upload:

```text
\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b
```

## Take-home checklist

| Requirement | Implementation |
| --- | --- |
| Upload tabular data | CSV and XLSX upload with size, row, column, and duplicate-column validation |
| Generate regex from natural language | OpenAI-compatible chat call returns JSON containing regex, explanation, and warnings |
| Preview matches before applying | Backend computes sample matches from stored uploaded values |
| Apply replacement | Literal server-side replacement against one selected column |
| Download result | One-shot CSV download endpoint with formula-prefix escaping |
| Explain design choices | Architecture, trade-offs, limitations, setup, API, and deployment notes are documented below |

---

## 1. Project overview

The app supports a three-step workflow:

1. **Upload and preview** — the user uploads a `.csv` or `.xlsx` file. The backend parses it with pandas, validates shape and size, returns a 10-row preview, the column list, and the columns it detected as text-like.
2. **Define transformation** — the user picks a target column and types a plain-English instruction. The backend sends a short, structured prompt to an OpenAI-compatible chat model and gets back JSON containing only a regex, an explanation, and optional warnings. The backend validates the regex, then computes sample matches **locally** by scanning the stored column.
3. **Apply and download** — the user (optionally edits the regex, picks regex flags) and applies the transformation. Replacement runs server-side as a literal substitution against a copy of the stored DataFrame. A new CSV is generated and exposed as a one-shot download URL.

The model receives only capped prompt samples, is not given the full file, and is not involved in applying transformations or creating exports.

## 2. Features

- Upload `.csv` and `.xlsx` files; preview the first 10 rows.
- Auto-detect text-like columns; allow any column to be selected.
- Generate a Python `re` pattern from natural language using an OpenAI-compatible chat model.
- Validate generated and user-edited regex before any scanning or replacement.
- Compute sample matches server-side from real uploaded values, never from the model.
- Editable regex with optional flags: `IGNORECASE`, `MULTILINE`, `DOTALL`, `VERBOSE`.
- Apply literal replacements to a single selected column and download a transformed CSV.
- Preserve null cells and reject empty target columns for regex generation.
- Reject obviously dangerous patterns (nested quantifiers, empty alternations) and over-long patterns.
- Reject `apply` requests when the target column contains cells longer than `MAX_CELL_CHARS` rather than silently truncating user data.
- Escape spreadsheet formula prefixes (`=`, `+`, `-`, `@`) in exported CSVs to reduce formula-injection risk when reviewers open the file in Excel or Google Sheets.
- Bounded in-memory dataset and export stores with TTL and item-count limits.
- Side-by-side preview of original vs. transformed data after apply.

## 3. Tech stack

**Backend**
- Python 3.12+
- Django 6.0
- Django REST Framework 3.17
- pandas 3.0, openpyxl 3.1 (XLSX parsing)
- openai 2.36 (OpenAI-compatible chat completions client)
- python-dotenv (loads `.env` from the repo root)
- django-cors-headers
- SQLite (Django default, used for admin/sessions only — uploaded data lives in memory)

**Frontend**
- React 19 + TypeScript 6
- Vite 8 (dev server, proxy, and build)
- ESLint + `typescript-eslint`

**Storage**
- Bounded in-memory store for uploaded DataFrames and CSV exports, keyed by UUID, with TTL and maximum-item caps. No background worker or persistent file store is used.

## 4. Architecture and data flow

At a high level:

- Upload stores a validated DataFrame in a bounded in-memory store and returns preview metadata.
- Generate asks the model for a regex only, then validates and samples matches on the backend.
- Apply re-validates the regex, performs literal replacement on a copy, sanitizes the CSV export, and returns a one-shot download URL.

```text
Browser (React + Vite)
   │
   │  multipart/form-data (CSV/XLSX)
   ▼
POST /api/upload/
   ├─ parsing.validate_extension / read_uploaded_tabular / validate_shape
   ├─ in-memory store (file_id ─► DataFrame, TTL + LRU eviction)
   └─ response: { file_id, columns, preview_rows, detected_text_columns, warnings }

   │  natural language instruction + file_id + column_name
   ▼
POST /api/pattern/generate/
   ├─ collect_prompt_samples  (de-duped, length-capped)
   ├─ OpenAI-compatible chat call (JSON-only response, temperature 0.2)
   ├─ normalize_llm_regex_payload  (shape validation)
   ├─ validate_regex_pattern  (length, nested quantifiers, empty alternations)
   ├─ re.compile(pattern_str)
   ├─ collect_sample_matches  (local scan of stored column, distinct, capped)
   └─ response: { regex_pattern, explanation, warnings, sample_matches }

   │  (possibly edited) regex + flags + replacement
   ▼
POST /api/transform/apply/
   ├─ compile_regex (re-validates, applies allow-listed flags)
   ├─ apply_regex_to_column on a DataFrame copy
   │     ├─ skip null cells, reject cells > MAX_CELL_CHARS
   │     ├─ literal substitution (no backreference expansion)
   │     └─ count matched_cells and changed_rows
   ├─ sanitize_for_csv_export (formula prefix escaping)
   ├─ write CSV bytes to in-memory export store
   └─ response: { transformed_preview, matched_cells_count, changed_rows_count, downloadable_file_url }

   ▼
GET /api/download/<export_id>/  →  text/csv attachment "transformed.csv"
```

Module boundaries on the backend (`backend/api/`):

| File | Responsibility |
| --- | --- |
| `parsing.py` | Upload validation, DataFrame loading, preview/text-column helpers |
| `regex_llm.py` | Prompt construction, OpenAI call, JSON normalization, sample-match scanning |
| `transform_apply.py` | Regex validation, flag mapping, replacement loop, CSV sanitization |
| `storage.py` | In-memory stores for uploaded DataFrames and CSV exports |
| `serializers.py` | DRF request validation for generate/apply |
| `views.py` | HTTP request/response orchestration only |
| `tests.py` | End-to-end coverage of upload, generate, and apply paths |

Frontend layout (`frontend/src/`):

| File | Responsibility |
| --- | --- |
| `App.tsx`, `pages/HomePage.tsx`, `components/Layout.tsx` | Single-page shell |
| `components/UploadPreviewSection.tsx` | Step 1 — upload + preview |
| `components/TransformationPanel.tsx` | Steps 2 and 3 — generate, apply, download, side-by-side preview |
| `api/url.ts` | API base URL helper (uses Vite proxy in dev, `VITE_API_BASE_URL` in prod) |
| `types/upload.ts` | Shared response types |

## 5. Local development

### Prerequisites

- Python **3.12+**
- Node.js **20+** and npm
- An OpenAI-compatible API key (only required for the `pattern/generate` endpoint)

The project was developed on Windows; commands below show both Windows PowerShell and macOS/Linux variants where they differ.

### Configure environment

Copy the example env file and edit it:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Set `OPENAI_API_KEY` if you want to use LLM generation locally. Without it, the manual-regex path in [Quick demo](#quick-demo) still lets you evaluate upload, validation, apply, preview, and download. The full table is in [Environment variables](#6-environment-variables).

### Backend

```bash
cd backend
python -m venv .venv
```

Activate the virtualenv:

```bash
# Windows PowerShell
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install and run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

### Frontend (in a second terminal)

```bash
cd frontend
npm ci
npm run dev
```

Use `npm install` instead if you intentionally want npm to update the lockfile. Open `http://localhost:5173`. In dev, Vite proxies `/api` to `http://127.0.0.1:8000`, so no `VITE_API_BASE_URL` is needed.

### Tests and checks

Backend tests cover upload parsing, duplicate columns, row limits, long-text warnings, invalid and risky regex, literal-replacement behavior, empty target columns, LLM output validation, formula-safe CSV export, and the download path:

```bash
cd backend
python manage.py test
```

Frontend lint and production build:

```bash
cd frontend
npm run lint
npm run build
```

## 6. Environment variables

For local development, variables are loaded from a single `.env` file at the **repository root**. The Vite config sets `envDir: '..'`, so both Django (`backend/config/settings.py`) and Vite read from the same file. Every variable below is defined in [`.env.example`](.env.example), and production placeholders are provided in [`.env.production.example`](.env.production.example).

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | For deployment | dev fallback | Django secret key. The app refuses to start with the dev fallback when `DJANGO_DEBUG=false`. |
| `DJANGO_DEBUG` | No | `true` | Set to `false` for any non-local deployment. |
| `DJANGO_ALLOWED_HOSTS` | For deployment | `localhost,127.0.0.1` | Comma-separated backend hostnames. |
| `CORS_ALLOWED_ORIGINS` | For deployment | local Vite origins | Comma-separated frontend origins allowed to call the API. |
| `VITE_API_BASE_URL` | For prod frontend build | unset | Backend origin used by built frontend assets. Leave unset locally; Vite proxies `/api`. |
| `OPENAI_API_KEY` | For `/api/pattern/generate/` | empty | API key for the OpenAI-compatible chat completions client. |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Chat model used for regex generation. |
| `OPENAI_BASE_URL` | No | empty | Optional base URL for Azure OpenAI or another OpenAI-compatible proxy. |
| `MAX_UPLOAD_BYTES` | No | `5242880` (5 MB) | Maximum uploaded file size. |
| `MAX_UPLOAD_ROWS` | No | `10000` | Maximum parsed rows. |
| `MAX_UPLOAD_COLUMNS` | No | `100` | Maximum parsed columns. |
| `MAX_CELL_CHARS` | No | `2000` | Maximum cell length permitted in the apply target column. |
| `MAX_REGEX_PATTERN_LENGTH` | No | `500` | Maximum regex pattern length. |
| `MAX_REPLACEMENT_CHARS` | No | `10000` | Maximum replacement-string length. |
| `MAX_SAMPLE_SCAN_ROWS` | No | `250` | Maximum rows scanned for sample matches after generation. |
| `UPLOAD_STORE_TTL_SECONDS` | No | `3600` | Time before uploaded datasets are evicted from memory. |
| `UPLOAD_STORE_MAX_ITEMS` | No | `25` | Maximum stored uploads. |
| `EXPORT_STORE_MAX_ITEMS` | No | `25` | Maximum stored CSV exports. |

For production, set variables in the hosting provider dashboard rather than committing a `.env` file. The minimum production set is:

```text
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<deployed-backend-host>
CORS_ALLOWED_ORIGINS=https://<deployed-frontend-host>
VITE_API_BASE_URL=https://<deployed-backend-host>
OPENAI_API_KEY=<required-for-natural-language-generation>
```

## 7. API summary

All routes are JSON unless noted, mounted under `/api/`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/` | Liveness check. |
| `POST` | `/api/upload/` | Multipart upload; field name `file`. Returns `file_id`, columns, 10-row preview, detected text columns, warnings. |
| `POST` | `/api/pattern/generate/` | Generate a regex from a column and a natural-language prompt. Returns `regex_pattern`, `explanation`, `warnings`, server-computed `sample_matches`. Requires `OPENAI_API_KEY`. |
| `POST` | `/api/transform/apply/` | Apply a regex with optional flags to one column. Returns transformed preview, match/row counters, and a download URL. |
| `GET` | `/api/download/<export_id>/` | One-shot CSV attachment download. |

Example `pattern/generate` request:

```json
{
  "file_id": "uploaded-file-id",
  "column_name": "Email",
  "natural_language_prompt": "Find email addresses"
}
```

Example `transform/apply` request:

```json
{
  "file_id": "uploaded-file-id",
  "column_name": "Email",
  "regex_pattern": "\\b[\\w.%+-]+@[\\w.-]+\\.[A-Za-z]{2,}\\b",
  "replacement_value": "REDACTED",
  "flags": ["IGNORECASE"]
}
```

Allowed flag values: `IGNORECASE`, `MULTILINE`, `DOTALL`, `VERBOSE`.

## 8. Deployment

This repository is ready to run locally. Before final submission, replace the entries below with live URLs if the assignment requires a deployed demo.

| Resource | URL |
| --- | --- |
| Live frontend | _Local-only; see [Local development](#5-local-development)_ |
| Live backend (API base) | _Local-only; see [Local development](#5-local-development)_ |
| Hosting provider notes | _Add provider names before final submission if deployed_ |

### Backend deployment

Use a single backend process while uploads and exports live in memory. On a Linux host, a minimal backend deployment path is:

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
gunicorn config.wsgi:application --workers 1 --bind 0.0.0.0:$PORT
```

Set these backend environment variables in the host:

- Set `DJANGO_DEBUG=false` and a strong `DJANGO_SECRET_KEY`. The app refuses to start otherwise.
- Set `DJANGO_ALLOWED_HOSTS` to the deployed backend host.
- Set `CORS_ALLOWED_ORIGINS` to the deployed frontend origin.
- Set `OPENAI_API_KEY` if reviewers should test natural-language generation.
- Keep one worker/process for the demo, and avoid autosleep during live review so uploaded files and generated exports are not lost mid-flow.
- Deploy behind HTTPS. If Django is responsible for proxy-aware HTTPS behavior rather than the host, add the relevant Django security settings for that platform.

### Frontend deployment

For split frontend/backend hosting, `VITE_API_BASE_URL` is required at build time. If it is omitted, the built app will call `/api/...` on the frontend origin, which only works when the frontend and backend are served from the same host.

```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://your-backend-host.example npm run build
```

Deploy the generated `frontend/dist` directory. On Windows PowerShell, set the variable before the build command:

```powershell
$env:VITE_API_BASE_URL="https://your-backend-host.example"
npm run build
```

## 9. Demo video

Add a short walkthrough link here before final submission if the assignment requests a video. The walkthrough should run through the [Quick demo](#quick-demo) against either the live deployment or the local app.

| Resource | URL |
| --- | --- |
| Walkthrough video | _Not included unless requested by the assignment_ |

## 10. Trade-offs and design decisions

- **In-memory store over a database.** Uploaded data is held in a bounded `OrderedDict` keyed by UUID, with TTL eviction and a maximum item count. This keeps the take-home easy to run locally and cheap to deploy while making the production limitation explicit: it is single-process only, and shared object storage would be the next step before scaling out.
- **LLM produces regex only; data work happens server-side.** The model returns a JSON object with just `regex_pattern`, `explanation`, and `warnings`. Sample matches and replacements are computed locally against the stored DataFrame, so the model is not trusted to edit user data or produce exported content.
- **Python `re` for portability.** Standard-library regex keeps the deployment surface small. To compensate, dangerous patterns (nested quantifiers, empty alternations) are rejected up front, and pattern/replacement length and per-cell length are capped. A timeout-capable engine in an isolated worker would be the right next step for a production rollout.
- **Literal replacement, not `re.sub` template expansion.** Replacements run via `compiled.sub(lambda _: replacement, s)` so backreferences like `\1` and named groups are not expanded. This avoids surprising side effects when a user types a literal `\1`.
- **One column at a time.** Transformations apply to a single selected column. This keeps user intent explicit and prevents accidental dataset-wide edits.
- **Formula-prefix escaping on export.** CSV cells whose value starts with `=`, `+`, `-`, or `@` are prefixed with a leading apostrophe before export so opening the file in Excel or Google Sheets does not auto-execute as a formula.
- **Long cells preserved, not truncated.** If a target column contains a cell longer than `MAX_CELL_CHARS`, the apply request is rejected with a clear error rather than silently dropping content from a user-owned file.
- **Two-step generate / apply UX.** Users see, and can edit, the regex and review server-computed sample matches before committing to a full-table transformation. Applying again after an edit is cheap.
- **Same `.env` for backend and frontend.** Vite is configured with `envDir: '..'` so both processes read variables from the repository-root `.env`. This avoids two-source-of-truth configuration drift in a small project.

## 11. Limitations

- In-memory storage is **single-process only**. Datasets and exports are lost on restart and not shared between Django workers.
- No authentication, rate limiting, or per-user quotas. Anyone with access to the deployed origin can use the API up to the configured size and item caps.
- Regex execution uses the standard library and has no hard timeout. The static checks reduce the worst cases but cannot fully prevent slow patterns on adversarial inputs.
- Upload size is capped at 5 MB and 10,000 rows by default; larger files are rejected, not streamed.
- Only `.csv` and `.xlsx` are accepted. XLSX parsing uses openpyxl and reads only the active sheet.
- Sample matches are computed by scanning at most `MAX_SAMPLE_SCAN_ROWS` rows (default 250). For very sparse columns, no sample match may be shown even though `apply` will still find matches across the full file.
- The example dataset includes a single small CSV (`examples/sample_emails.csv`). No XLSX example is bundled.

## 12. Appendix

**Project structure**

```text
backend/
  manage.py
  requirements.txt
  config/        # Django project (settings, urls, wsgi/asgi)
  api/           # parsing, regex_llm, transform_apply, storage, views, serializers, tests
frontend/
  package.json
  vite.config.ts
  src/
    pages/
    components/
    api/
    types/
examples/
  sample_emails.csv
.env.example
README.md
AGENTS.md
```

**Repository conventions**

- All user-facing text (UI copy, README, error messages, exported content) is English.
- Commit hygiene: `.env`, `backend/.venv`, `backend/db.sqlite3`, `frontend/node_modules`, `frontend/dist`, and `__pycache__` are ignored via `.gitignore`.
- AI-agent rules for any future change live in [`AGENTS.md`](AGENTS.md): plan first, minimal changes, explain files / commands / verification, and produce a deployment checklist after user-visible changes.

**Pre-submission checklist**

- [ ] If required by the assignment, replace the deployment URLs in section 8 with real, publicly reachable values.
- [ ] If required by the assignment, replace the demo-video URL in section 9.
- [ ] Ensure the submitted repo/archive does not include `.env`, `backend/.venv`, `backend/db.sqlite3`, `frontend/node_modules`, `frontend/dist`, or `__pycache__`.
- [ ] In the deployed backend: `DJANGO_DEBUG=false`, strong `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`.
- [ ] Configure `OPENAI_API_KEY` on the live backend if the reviewer should test natural-language generation.
- [ ] Build the frontend with `VITE_API_BASE_URL` pointing to the deployed backend origin.
- [ ] HTTPS for both frontend and backend.
- [ ] Backend run as a single process, or in-memory store replaced with shared storage.
- [ ] `python manage.py test`, `npm run lint`, and `npm run build` pass on the submission commit.
