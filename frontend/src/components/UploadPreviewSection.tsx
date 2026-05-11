import { useId, useState } from 'react'
import { apiUrl } from '../api/url'
import type { UploadResponse } from '../types/upload'

type UploadPhase = 'idle' | 'loading' | 'success' | 'error'

type UploadPreviewSectionProps = {
  onDatasetChange?: (data: UploadResponse | null) => void
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as {
      error?: string
      detail?: string
    }
    let msg = body.error ?? `Something went wrong (HTTP ${res.status}).`
    if (body.detail) {
      msg = `${msg} ${body.detail}`
    }
    return msg.trim()
  } catch {
    return `Something went wrong (HTTP ${res.status}).`
  }
}

export function UploadPreviewSection({
  onDatasetChange,
}: UploadPreviewSectionProps) {
  const inputId = useId()
  const [phase, setPhase] = useState<UploadPhase>('idle')
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const replaceFile = () => {
    setResult(null)
    setPhase('idle')
    setErrorMessage(null)
    onDatasetChange?.(null)
  }

  const onFileChange = async (file: File | undefined) => {
    if (!file) {
      return
    }
    onDatasetChange?.(null)
    setPhase('loading')
    setErrorMessage(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(apiUrl('/api/upload/'), {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        setErrorMessage(await readErrorMessage(res))
        setPhase('error')
        return
      }
      const data = (await res.json()) as UploadResponse
      setResult(data)
      setPhase('success')
      onDatasetChange?.(data)
    } catch {
      setErrorMessage(
        'We could not reach the API. Check that the backend is running and the frontend API URL is configured correctly.',
      )
      setPhase('error')
    }
  }

  const showIdleEmpty = phase === 'idle' && !result
  const showPreview = phase === 'success' && result !== null
  const textColumnsEmpty =
    showPreview && result.detected_text_columns.length === 0
  const tableEmpty = showPreview && result.preview_rows.length === 0

  return (
    <section className="panel upload" aria-busy={phase === 'loading'}>
      <div className="panel__head">
        <span className="panel__step">1</span>
        <div>
          <h2 className="panel__title">Upload and preview</h2>
          <p className="panel__lede">
            CSV and Excel (.xlsx). A ten-row preview is shown for the workflow
            below; exports always include the full file.
          </p>
        </div>
      </div>

      <div className="panel__toolbar">
        <div className="panel__toolbar-main">
          <label className="field__label" htmlFor={inputId}>
            Data file
          </label>
          <input
            id={inputId}
            className="field__input field__input--file"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={phase === 'loading'}
            onChange={(event) => {
              const file = event.target.files?.[0]
              void onFileChange(file)
              event.target.value = ''
            }}
          />
        </div>
        {showPreview && (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={replaceFile}
          >
            Replace file
          </button>
        )}
      </div>

      {phase === 'loading' && (
        <p className="feedback feedback--loading" role="status">
          Reading and validating your file...
        </p>
      )}

      {phase === 'error' && errorMessage && (
        <div className="feedback feedback--error" role="alert">
          <span className="feedback__title">Upload failed</span>
          {errorMessage}
        </div>
      )}

      {showIdleEmpty && (
        <div className="feedback feedback--empty" role="status">
          <span className="feedback__title">No file yet</span>
          Choose a .csv or .xlsx file to unlock steps 2 and 3.
        </div>
      )}

      {showPreview && result && (
        <>
          <div className="feedback feedback--success" role="status">
            <span className="feedback__title">File loaded</span>
            Continue in step 2. Use &quot;Replace file&quot; to clear this upload
            and pick a different dataset.
          </div>

          <p className="upload__meta">
            Session ID:{' '}
            <code className="upload__code">{result.file_id}</code>
          </p>

          <h3 className="upload__subheading">Detected text columns</h3>
          {result.warnings && result.warnings.length > 0 && (
            <div className="feedback feedback--empty" role="status">
              <span className="feedback__title">Upload warnings</span>
              {result.warnings.join(' ')}
            </div>
          )}

          {textColumnsEmpty ? (
            <div className="feedback feedback--empty" role="status">
              No text-like columns were inferred (everything may be numeric or
              dates). You can still pick any column in step 2.
            </div>
          ) : (
            <ul className="upload__chips" aria-label="Detected text columns">
              {result.detected_text_columns.map((name) => (
                <li key={name} className="upload__chip">
                  {name}
                </li>
              ))}
            </ul>
          )}

          <h3 className="upload__subheading">Preview (first 10 rows)</h3>
          {tableEmpty ? (
            <div className="feedback feedback--empty" role="status">
              This file has no rows to preview.
            </div>
          ) : (
            <div className="upload__table-wrap">
              <table className="upload__table">
                <thead>
                  <tr>
                    {result.columns.map((col) => (
                      <th key={col} scope="col">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview_rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {result.columns.map((col) => (
                        <td key={col}>{formatCell(row[col])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
