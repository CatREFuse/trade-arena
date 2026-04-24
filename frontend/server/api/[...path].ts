import { createError, getRequestURL, proxyRequest } from 'h3'

const BACKEND_ORIGIN = process.env.NUXT_BACKEND_URL || 'http://127.0.0.1:8000'
const ADMIN_API_PREFIX = '/api/admin'
const ADMIN_API_AUTH_PREFIX = '/api/admin/auth'

export default defineEventHandler((event) => {
  const url = getRequestURL(event)
  // In dev, Nuxt may hand this catch-all route a stripped pathname (e.g. "/health").
  // Normalize it back to backend API paths to avoid forwarding to non-existent endpoints.
  const normalizedPath = url.pathname.startsWith('/api')
    ? url.pathname
    : `/api${url.pathname.startsWith('/') ? url.pathname : `/${url.pathname}`}`

  const headers: Record<string, string> = {}
  const isAdminApi = normalizedPath === ADMIN_API_PREFIX || normalizedPath.startsWith(`${ADMIN_API_PREFIX}/`)
  const isAdminAuthApi = normalizedPath === ADMIN_API_AUTH_PREFIX || normalizedPath.startsWith(`${ADMIN_API_AUTH_PREFIX}/`)
  if (isAdminApi && !isAdminAuthApi) {
    const runtimeConfig = useRuntimeConfig()
    const adminBackendApiKey = String(runtimeConfig.adminBackendApiKey || '').trim()
    if (!adminBackendApiKey) {
      throw createError({
        statusCode: 503,
        statusMessage: 'Admin backend key is not configured',
      })
    }
    headers['X-Admin-API-Key'] = adminBackendApiKey
  }

  return proxyRequest(event, `${BACKEND_ORIGIN}${normalizedPath}${url.search}`, { headers })
})
