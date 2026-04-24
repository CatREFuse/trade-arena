import { createHash, timingSafeEqual } from 'node:crypto'
import { createError, deleteCookie, getCookie, setCookie } from 'h3'

const ADMIN_SESSION_COOKIE = 'ta_admin_session'

interface AdminCredentialConfig {
  username: string
  password: string
  sessionSalt: string
}

function getAdminCredentialConfig(): AdminCredentialConfig {
  const runtimeConfig = useRuntimeConfig()
  return {
    username: String(runtimeConfig.adminUsername || '').trim(),
    password: String(runtimeConfig.adminPassword || ''),
    sessionSalt: String(runtimeConfig.adminSessionSalt || ''),
  }
}

function hasCompleteAdminConfig(config: AdminCredentialConfig): boolean {
  return Boolean(config.username && config.password && config.sessionSalt)
}

function digest(input: string): string {
  return createHash('sha256').update(input).digest('hex')
}

function secureEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left)
  const rightBuffer = Buffer.from(right)
  if (leftBuffer.length !== rightBuffer.length)
    return false
  return timingSafeEqual(leftBuffer, rightBuffer)
}

export function buildAdminSessionToken(config: AdminCredentialConfig): string {
  return digest(`${config.username}:${config.password}:${config.sessionSalt}`)
}

export function validateAdminCredentials(username: string, password: string): boolean {
  const config = getAdminCredentialConfig()
  if (!hasCompleteAdminConfig(config))
    return false
  return secureEqual(username, config.username) && secureEqual(password, config.password)
}

export function hasValidAdminSession(event: Parameters<typeof getCookie>[0]): boolean {
  const token = getCookie(event, ADMIN_SESSION_COOKIE)
  if (!token)
    return false

  const config = getAdminCredentialConfig()
  if (!hasCompleteAdminConfig(config))
    return false

  const expectedToken = buildAdminSessionToken(config)
  return secureEqual(token, expectedToken)
}

export function setAdminSession(event: Parameters<typeof setCookie>[0]) {
  const runtimeConfig = useRuntimeConfig()
  const config = getAdminCredentialConfig()
  if (!hasCompleteAdminConfig(config)) {
    throw createError({
      statusCode: 503,
      statusMessage: 'Admin credentials are not configured',
    })
  }
  const token = buildAdminSessionToken(config)
  setCookie(event, ADMIN_SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: Boolean(runtimeConfig.adminCookieSecure),
    path: '/',
  })
}

export function clearAdminSession(event: Parameters<typeof deleteCookie>[0]) {
  deleteCookie(event, ADMIN_SESSION_COOKIE, { path: '/' })
}
