import { createError, getRequestURL, sendRedirect } from 'h3'
import { hasValidAdminSession } from '../utils/adminAuth'

const CONSOLE_PREFIX = '/console'
const CONSOLE_LOGIN_PREFIX = '/console/login'
const ADMIN_API_PREFIX = '/api/admin'
const ADMIN_API_AUTH_PREFIX = '/api/admin/auth'

export default defineEventHandler((event) => {
  const { pathname, search } = getRequestURL(event)
  const isConsoleRoute = pathname === CONSOLE_PREFIX || pathname.startsWith(`${CONSOLE_PREFIX}/`)
  const isConsoleLogin = pathname === CONSOLE_LOGIN_PREFIX || pathname.startsWith(`${CONSOLE_LOGIN_PREFIX}/`)
  const isAdminApi = pathname === ADMIN_API_PREFIX || pathname.startsWith(`${ADMIN_API_PREFIX}/`)
  const isAdminAuthApi = pathname === ADMIN_API_AUTH_PREFIX || pathname.startsWith(`${ADMIN_API_AUTH_PREFIX}/`)

  if (!isConsoleRoute && !isAdminApi)
    return

  if (isConsoleLogin || isAdminAuthApi)
    return

  if (hasValidAdminSession(event))
    return

  if (isAdminApi) {
    throw createError({
      statusCode: 401,
      statusMessage: 'Unauthorized',
      data: { detail: 'ADMIN_AUTH_REQUIRED' },
    })
  }

  const next = encodeURIComponent(`${pathname}${search}`)
  return sendRedirect(event, `/console/login?next=${next}`, 302)
})
