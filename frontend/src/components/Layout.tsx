import type { ReactNode } from 'react'

type LayoutProps = {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="layout">
      <header className="layout__header">
        <h1 className="layout__title">Pattern replace</h1>
        <p className="layout__subtitle">
          Upload a table, describe a match in plain language, then apply a
          replacement and export CSV.
        </p>
      </header>
      <main className="layout__main">{children}</main>
    </div>
  )
}
