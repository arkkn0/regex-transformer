export type UploadResponse = {
  file_id: string
  columns: string[]
  preview_rows: Record<string, unknown>[]
  detected_text_columns: string[]
  warnings?: string[]
}
