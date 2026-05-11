/**
 * Build an API URL. In dev, leave VITE_API_BASE_URL unset so requests use the Vite proxy.
 * In production, set VITE_API_BASE_URL to the Django origin (e.g. https://api.example.com).
 */
export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${base}${normalized}`
}
