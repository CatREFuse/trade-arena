import { getRequestURL, proxyRequest } from 'h3'

const BACKEND_ORIGIN = process.env.NUXT_BACKEND_URL || 'http://127.0.0.1:8000'

export default defineEventHandler((event) => {
  const url = getRequestURL(event)
  // In dev, Nuxt may hand this catch-all route a stripped pathname (e.g. "/health").
  // Normalize it back to backend API paths to avoid forwarding to non-existent endpoints.
  const normalizedPath = url.pathname.startsWith('/api')
    ? url.pathname
    : `/api${url.pathname.startsWith('/') ? url.pathname : `/${url.pathname}`}`

  return proxyRequest(event, `${BACKEND_ORIGIN}${normalizedPath}${url.search}`)
})
