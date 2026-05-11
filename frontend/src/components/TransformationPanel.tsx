import { useEffect, useId, useState } from 'react'
import { apiUrl } from '../api/url'
import type { UploadResponse } from '../types/upload'

const REGEX_FLAG_OPTIONS = [
  'IGNORECASE',
  'MULTILINE',
  'DOTALL',
  'VERBOSE',
] as const

type SampleMatch = {
  row_index: number
  source_value: string
  matched_text: string
}

type GeneratePatternResponse = {
  regex_pattern: string
  explanation: string
  warnings: string[]
  sample_matches: SampleMatch[]
}

type ApplyTransformResponse = {
  transformed_preview: Record<string, unknown>[]
  matched_cells_count: number
  changed_rows_count: number
  downloadable_file_url: string
}

type TransformationPanelProps = {
  dataset: UploadResponse | null
  onResetWorkspace?: () => void
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

async function readApiError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as {
      error?: string
      detail?: string
      details?: unknown
    }
    let msg = body.error ?? `Request failed (HTTP ${res.status}).`
    if (body.detail) {
      msg = `${msg} ${body.detail}`
    }
    return msg.trim()
  } catch {
    return `Request failed (HTTP ${res.status}).`
  }
}

function clearGeneration(
  setters: {
    setRegexPattern: (v: string) => void
    setExplanation: (v: string | null) => void
    setWarnings: (v: string[]) => void
    setSampleMatches: (v: SampleMatch[]) => void
    setError: (v: string | null) => void
  },
) {
  setters.setRegexPattern('')
  setters.setExplanation(null)
  setters.setWarnings([])
  setters.setSampleMatches([])
  setters.setError(null)
}

function PreviewTable({
  title,
  columns,
  rows,
}: {
  title: string
  columns: string[]
  rows: Record<string, unknown>[]
}) {
  return (
    <div className="preview-compare__col">
      <h4 className="preview-compare__table-title">{title}</h4>
      <div className="upload__table-wrap">
        <table className="upload__table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} scope="col">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((col) => (
                  <td key={col}>{formatCell(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function TransformationPanel({
  dataset,
  onResetWorkspace,
}: TransformationPanelProps) {
  const columnId = useId()
  const instructionId = useId()
  const replacementId = useId()
  const regexId = useId()

  const [targetColumn, setTargetColumn] = useState('')
  const [instruction, setInstruction] = useState('')
  const [replacement, setReplacement] = useState('')
  const [regexFlags, setRegexFlags] = useState<string[]>([])

  const [regexPattern, setRegexPattern] = useState('')
  const [explanation, setExplanation] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [sampleMatches, setSampleMatches] = useState<SampleMatch[]>([])

  const [patternLoading, setPatternLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [applyLoading, setApplyLoading] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [applyResult, setApplyResult] = useState<ApplyTransformResponse | null>(
    null,
  )

  const [patternSuccess, setPatternSuccess] = useState(false)

  const resetOutput = () => {
    clearGeneration({
      setRegexPattern,
      setExplanation,
      setWarnings,
      setSampleMatches,
      setError,
    })
    setPatternSuccess(false)
  }

  const clearApply = () => {
    setApplyResult(null)
    setApplyError(null)
  }

  // This component owns a small multi-step workspace; reset all derived fields
  // whenever the uploaded dataset changes.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!dataset) {
      setTargetColumn('')
      setInstruction('')
      setReplacement('')
      setRegexFlags([])
      resetOutput()
      clearApply()
      setPatternLoading(false)
      setApplyLoading(false)
      return
    }
    const preferred =
      dataset.detected_text_columns[0] ?? dataset.columns[0] ?? ''
    setTargetColumn(preferred)
    setRegexFlags([])
    resetOutput()
    clearApply()
    setPatternLoading(false)
    setApplyLoading(false)
  }, [dataset])
  /* eslint-enable react-hooks/set-state-in-effect */

  const disabled = dataset === null
  const canGenerate =
    Boolean(dataset) &&
    Boolean(targetColumn) &&
    instruction.trim().length > 0 &&
    !patternLoading &&
    !applyLoading

  const canApply =
    Boolean(dataset) &&
    Boolean(targetColumn) &&
    regexPattern.trim().length > 0 &&
    !patternLoading &&
    !applyLoading

  const onGeneratePattern = async () => {
    if (!dataset || !targetColumn || !instruction.trim()) {
      return
    }
    setPatternLoading(true)
    setError(null)

    try {
      const res = await fetch(apiUrl('/api/pattern/generate/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: dataset.file_id,
          column_name: targetColumn,
          natural_language_prompt: instruction.trim(),
        }),
      })

      if (!res.ok) {
        setError(await readApiError(res))
        setRegexPattern('')
        setExplanation(null)
        setWarnings([])
        setSampleMatches([])
        setPatternSuccess(false)
        return
      }

      const data = (await res.json()) as GeneratePatternResponse
      setRegexPattern(data.regex_pattern ?? '')
      setExplanation(data.explanation ?? null)
      setWarnings(Array.isArray(data.warnings) ? data.warnings : [])
      setSampleMatches(
        Array.isArray(data.sample_matches) ? data.sample_matches : [],
      )
      setPatternSuccess(true)
      clearApply()
    } catch {
      setError(
        'We could not reach the API. Check that the backend is running, the frontend API URL is configured correctly, and OPENAI_API_KEY is set for pattern generation.',
      )
      setRegexPattern('')
      setExplanation(null)
      setWarnings([])
      setSampleMatches([])
      setPatternSuccess(false)
    } finally {
      setPatternLoading(false)
    }
  }

  const onApplyTransform = async () => {
    if (!dataset || !targetColumn || !regexPattern.trim()) {
      return
    }
    setApplyLoading(true)
    setApplyError(null)

    try {
      const res = await fetch(apiUrl('/api/transform/apply/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: dataset.file_id,
          column_name: targetColumn,
          regex_pattern: regexPattern.trim(),
          replacement_value: replacement,
          flags: regexFlags,
        }),
      })

      if (!res.ok) {
        setApplyError(await readApiError(res))
        setApplyResult(null)
        return
      }

      const data = (await res.json()) as ApplyTransformResponse
      setApplyResult({
        transformed_preview: Array.isArray(data.transformed_preview)
          ? data.transformed_preview
          : [],
        matched_cells_count: Number(data.matched_cells_count) || 0,
        changed_rows_count: Number(data.changed_rows_count) || 0,
        downloadable_file_url: data.downloadable_file_url ?? '',
      })
    } catch {
      setApplyError(
        'We could not reach the API. Check that the backend is running and the frontend API URL is configured correctly.',
      )
      setApplyResult(null)
    } finally {
      setApplyLoading(false)
    }
  }

  const hasOutput =
    explanation !== null ||
    warnings.length > 0 ||
    sampleMatches.length > 0 ||
    regexPattern.length > 0

  const toggleFlag = (name: string) => {
    setRegexFlags((prev) =>
      prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name],
    )
    clearApply()
  }

  return (
    <section
      className={`panel transformation ${disabled ? 'transformation--disabled' : ''}`}
      aria-disabled={disabled}
    >
      <div className="panel__head">
        <span className="panel__step">2</span>
        <div>
          <h2 className="panel__title">Define transformation</h2>
          <p className="panel__lede">
            Describe what to find in natural language, then generate a Python{' '}
            <code className="panel__inline-code">re</code> pattern. Apply it to
            the full dataset and download the result as CSV.
          </p>
        </div>
      </div>

      {disabled ? (
        <div className="transformation__placeholder" role="status">
          <span className="feedback__title">Waiting for a file</span>
          Complete step 1 to choose a column, describe a pattern, and apply
          replacements.
        </div>
      ) : (
        <>
          {onResetWorkspace && (
            <div className="transformation__panel-tools">
              <button
                type="button"
                className="btn btn--ghost"
                onClick={onResetWorkspace}
                disabled={patternLoading || applyLoading}
              >
                Start over
              </button>
            </div>
          )}
          <div className="transformation__form">
            <div className="field">
              <label className="field__label" htmlFor={columnId}>
                Target column
              </label>
              <select
                id={columnId}
                className="field__select"
                value={targetColumn}
                disabled={patternLoading || applyLoading}
                onChange={(e) => {
                  setTargetColumn(e.target.value)
                  resetOutput()
                  clearApply()
                  setPatternLoading(false)
                }}
              >
                {dataset.columns.map((name) => (
                  <option key={name} value={name}>
                    {name}
                    {dataset.detected_text_columns.includes(name)
                      ? ' - text'
                      : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="field__label" htmlFor={instructionId}>
                Natural language instruction
              </label>
              <textarea
                id={instructionId}
                className="field__textarea"
                rows={3}
                placeholder='e.g. "Find email addresses in this column"'
                value={instruction}
                disabled={patternLoading || applyLoading}
                onChange={(e) => {
                  setInstruction(e.target.value)
                  resetOutput()
                  clearApply()
                  setPatternLoading(false)
                }}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor={replacementId}>
                Replacement value
              </label>
              <input
                id={replacementId}
                className="field__input"
                type="text"
                placeholder="e.g. REDACTED"
                value={replacement}
                disabled={patternLoading || applyLoading}
                onChange={(e) => {
                  setReplacement(e.target.value)
                  clearApply()
                }}
              />
            </div>

            <div className="transformation__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => void onGeneratePattern()}
                disabled={!canGenerate}
              >
                {patternLoading ? 'Generating...' : 'Generate pattern'}
              </button>
              <span className="transformation__hint">
                Uses your session ID and column. The server must have{' '}
                <code className="panel__inline-code">OPENAI_API_KEY</code>{' '}
                configured.
              </span>
            </div>
          </div>

          {(patternLoading || applyLoading) && (
            <p className="feedback feedback--loading" role="status">
              {patternLoading
                ? 'Contacting the model and validating the pattern...'
                : 'Applying the pattern to the full dataset...'}
            </p>
          )}

          {error && (
            <div
              className="feedback feedback--error transformation__banner"
              role="alert"
            >
              <span className="feedback__title">Pattern generation failed</span>
              {error}
            </div>
          )}

          {patternSuccess && !patternLoading && !error && hasOutput && (
            <div className="feedback feedback--success" role="status">
              <span className="feedback__title">Pattern ready</span>
              Review the regex and sample matches, then continue to apply in
              step 3.
            </div>
          )}

          <div className="pattern-output" aria-live="polite">
            <div className="pattern-output__head">
              <h3 className="pattern-output__title">Pattern output</h3>
            </div>

            {!hasOutput && !patternLoading && !error && (
              <div className="feedback feedback--empty">
                <span className="feedback__title">Nothing generated yet</span>
                Add a natural language instruction, then choose &quot;Generate
                pattern&quot; to load the regex, explanation, warnings, and
                sample matches.
              </div>
            )}

            {(hasOutput || patternLoading) && (
              <>
                <div className="pattern-output__block">
                  <h4 className="pattern-output__label">Regular expression</h4>
                  <p className="pattern-output__subtext pattern-output__subtext--tight">
                    You can edit this before applying. Sample matches reflect the
                    last successful generation; run generate again to refresh
                    them from the server.
                  </p>
                  <textarea
                    id={regexId}
                    className="pattern-output__regex-edit"
                    value={regexPattern}
                    onChange={(e) => {
                      setRegexPattern(e.target.value)
                      clearApply()
                    }}
                    spellCheck={false}
                    disabled={patternLoading}
                    rows={3}
                    aria-label="Generated regular expression (editable)"
                  />
                </div>

                {explanation !== null && explanation !== '' && (
                  <div className="pattern-output__block">
                    <h4 className="pattern-output__label">Explanation</h4>
                    <p className="pattern-output__text">{explanation}</p>
                  </div>
                )}

                {warnings.length > 0 && (
                  <div className="pattern-output__block">
                    <h4 className="pattern-output__label">Warnings</h4>
                    <ul className="pattern-output__warnings" role="list">
                      {warnings.map((w, i) => (
                        <li key={`${i}-${w.slice(0, 24)}`}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="pattern-output__block">
                  <h4 className="pattern-output__label">Sample matches</h4>
                  {sampleMatches.length === 0 ? (
                    <div className="feedback feedback--empty">
                      <span className="feedback__title">No sample matches</span>
                      The pattern did not match any values in this column, or
                      the column had no text to scan. You can still try apply in
                      step 3.
                    </div>
                  ) : (
                    <>
                      <p className="pattern-output__subtext">
                        From column &quot;{targetColumn}&quot; (server-side scan,
                        up to 10 distinct matches).
                      </p>
                      <ul className="pattern-output__matches">
                        {sampleMatches.map((item) => (
                          <li
                            key={`${item.row_index}-${item.matched_text}`}
                            className="pattern-output__match"
                          >
                            <span className="pattern-output__match-label">
                              Row {item.row_index + 1}
                            </span>
                            <code className="pattern-output__match-value">
                              {item.matched_text}
                            </code>
                            <span className="pattern-output__match-source">
                              {item.source_value}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              </>
            )}
          </div>

          {hasOutput && (
            <div className="apply-block">
              <h3 className="apply-block__title">
                <span className="panel__step panel__step--inline">3</span>
                Apply and download
              </h3>
              <p className="apply-block__lede">
                Runs against the full table on the server. Your original upload
                stays unchanged; you receive a new CSV download.
              </p>

              <fieldset className="apply-block__flags">
                <legend className="field__label">Regex flags (optional)</legend>
                <div className="apply-block__flag-grid">
                  {REGEX_FLAG_OPTIONS.map((name) => (
                    <label key={name} className="apply-block__check">
                      <input
                        type="checkbox"
                        checked={regexFlags.includes(name)}
                        disabled={applyLoading || patternLoading}
                        onChange={() => {
                          toggleFlag(name)
                        }}
                      />
                      {name}
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="transformation__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => void onApplyTransform()}
                  disabled={!canApply}
                >
                  {applyLoading ? 'Applying...' : 'Apply transformation'}
                </button>
              </div>

              {applyError && (
                <div
                  className="feedback feedback--error transformation__banner"
                  role="alert"
                >
                  <span className="feedback__title">Apply failed</span>
                  {applyError}
                </div>
              )}

              {applyResult && (
                <>
                  {applyResult.matched_cells_count > 0 && (
                    <div className="feedback feedback--success" role="status">
                      <span className="feedback__title">
                        Transformation applied
                      </span>
                      Compare the previews, then download the full CSV. Adjust
                      the pattern and apply again if needed.
                    </div>
                  )}

                  <div className="apply-block__stats">
                    <p>
                      <strong>Matched cells:</strong>{' '}
                      {applyResult.matched_cells_count}
                    </p>
                    <p>
                      <strong>Changed rows:</strong>{' '}
                      {applyResult.changed_rows_count}
                    </p>
                  </div>

                  {applyResult.matched_cells_count === 0 && (
                    <div
                      className="apply-block__notice apply-block__notice--warn"
                      role="status"
                    >
                      <strong>No matches.</strong> No cells matched this
                      pattern, so nothing was replaced. Refine the regex or
                      flags, then apply again. You can still download a CSV
                      identical to the original for this column.
                    </div>
                  )}

                  <div className="preview-compare">
                    <PreviewTable
                      title="Original (first 10 rows)"
                      columns={dataset.columns}
                      rows={dataset.preview_rows}
                    />
                    <PreviewTable
                      title="Transformed (first 10 rows)"
                      columns={dataset.columns}
                      rows={applyResult.transformed_preview}
                    />
                  </div>

                  <div className="apply-block__download">
                    <a
                      className="btn btn--primary"
                      href={apiUrl(applyResult.downloadable_file_url)}
                      download="transformed.csv"
                    >
                      Download full CSV
                    </a>
                    <span className="transformation__hint">
                      Full row set with replacements in the target column only.
                    </span>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}
