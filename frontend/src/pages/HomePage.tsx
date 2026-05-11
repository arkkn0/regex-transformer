import { useState } from 'react'
import { TransformationPanel } from '../components/TransformationPanel'
import { UploadPreviewSection } from '../components/UploadPreviewSection'
import type { UploadResponse } from '../types/upload'

export function HomePage() {
  const [dataset, setDataset] = useState<UploadResponse | null>(null)
  const [uploadKey, setUploadKey] = useState(0)

  const resetWorkspace = () => {
    setDataset(null)
    setUploadKey((k) => k + 1)
  }

  return (
    <div className="home">
      <div className="workspace">
        <UploadPreviewSection
          key={uploadKey}
          onDatasetChange={setDataset}
        />
        <TransformationPanel
          dataset={dataset}
          onResetWorkspace={resetWorkspace}
        />
      </div>
    </div>
  )
}
