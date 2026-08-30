# Regex Pattern Matching and Replacement

A Django and React application for applying reviewed regex transformations to CSV and XLSX files. Users can describe a pattern in plain English, inspect the generated expression against values from their file, edit it if needed, and download the transformed data.

The model proposes a pattern; the backend remains responsible for validation, matching, replacement and export. Uploaded tables are kept in a bounded in-memory store and are not sent to the model in full.

## Try the workflow

1. Start the backend and frontend using the instructions below.
2. Open `http://localhost:5173`.
3. Upload [`examples/sample_emails.csv`](examples/sample_emails.csv).
4. Select the `Email` column.
5. Enter `Find email addresses` and use `REDACTED` as the replacement.
6. Review the expression and sample matches before applying it.
7. Download the transformed CSV.

The hosted demo is available at <https://regex-transformer.vercel.app/>. A short walkthrough is available [here](https://drive.google.com/file/d/1eDuAIg-FNdT93IVsdMKf_DC5QlUYhyFP/view?usp=sharing).

Without an API key, the rest of the workflow can be tested by entering this expression manually:

```text
\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b
```

## How it works

```text
CSV/XLSX upload
  -> validate size and shape
  -> store a bounded in-memory DataFrame
  -> request a regex from the model
  -> validate and compile the regex on the server
  -> preview matches from the uploaded column
  -> apply a literal replacement to a copy
  -> escape spreadsheet formula prefixes
  -> return a one-time CSV download
```

The backend is split into small modules:

| Module | Responsibility |
| --- | --- |
| `parsing.py` | File validation, table loading and preview data |
| `regex_llm.py` | Prompt construction, response parsing and sample matching |
| `transform_apply.py` | Regex checks, flag handling, replacement and CSV sanitisation |
| `storage.py` | TTL- and count-bounded upload and export stores |
| `serializers.py` | Request validation |
| `views.py` | HTTP orchestration |

The React frontend handles upload, column selection, expression review, transformation preview and download. It does not execute regex over the dataset or place model credentials in the browser.

## Safety and resource limits

- Uploads are restricted to CSV or XLSX and bounded by byte, row and column limits.
- Prompt samples are deduplicated, length-limited and capped; the full table is not sent to the model.
- Generated and edited expressions are checked for length, invalid syntax, nested quantifiers and empty alternations.
- Replacement strings are literal, so user input cannot invoke regex backreferences.
- Long target cells are rejected before applying a transformation instead of being silently truncated.
- CSV values beginning with `=`, `+`, `-` or `@` are escaped before export.
- Uploaded tables and generated exports expire from the in-memory stores; downloads are one-time.

Python's `re` engine cannot guarantee a time limit for every adversarial expression. The current checks reduce common risks but are not a complete defence against catastrophic backtracking. A service accepting arbitrary public traffic should use an engine with hard execution limits or isolate matching in a resource-constrained worker.

## Local development

Requirements:

- Python 3.12 or newer
- Node.js 20 or newer
- an OpenAI-compatible API key for natural-language pattern generation

Create the root environment file:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env`. Set `OPENAI_API_KEY` if you want to test pattern generation.

Start the backend:

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000` in development.

## Verification

Run the backend tests:

```bash
cd backend
python manage.py test
```

Run the frontend checks:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

The backend suite covers upload bounds, duplicate columns, risky and invalid expressions, model-response validation, literal replacement, formula-safe exports and one-time downloads. GitHub Actions runs both backend and frontend checks on each push and pull request.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/` | Liveness check |
| `POST` | `/api/upload/` | Upload a table and return preview metadata |
| `POST` | `/api/pattern/generate/` | Generate and validate a regex, then return local sample matches |
| `POST` | `/api/transform/apply/` | Apply a reviewed expression to one column |
| `GET` | `/api/download/<export_id>/` | Download the transformed CSV once |

## Configuration

The main environment variables are listed in [`.env.example`](.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Credential for pattern generation |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `OPENAI_BASE_URL` | empty | Optional compatible endpoint |
| `MAX_UPLOAD_BYTES` | `5242880` | Upload size limit |
| `MAX_UPLOAD_ROWS` | `10000` | Parsed row limit |
| `MAX_UPLOAD_COLUMNS` | `100` | Parsed column limit |
| `MAX_CELL_CHARS` | `2000` | Apply-path cell length limit |
| `MAX_REGEX_PATTERN_LENGTH` | `500` | Expression length limit |
| `UPLOAD_STORE_TTL_SECONDS` | `3600` | Upload retention in memory |

For a deployed backend, set a unique `DJANGO_SECRET_KEY`, disable debug mode, and configure `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`. Set `VITE_API_BASE_URL` when the built frontend and backend use different origins.

## Current boundaries

- Uploaded data is process-local and disappears on restart. Keep one backend worker unless storage is replaced.
- The application has no user accounts or durable job history.
- CSV and XLSX are the only accepted formats; the active XLSX sheet is read.
- Matching uses Python `re`, with the limitation described above.
- Model-generated expressions still require user review before application.

## License

MIT
