import { createError, readBody } from 'h3'
import { setAdminSession, validateAdminCredentials } from '~/server/utils/adminAuth'
import {
  clearAdminLoginGuard,
  getAdminDeviceBanStatus,
  registerAdminLoginFailure,
} from '~/server/utils/adminLoginGuard'

interface LoginBody {
  username?: string
  password?: string
}

export default defineEventHandler(async (event) => {
  const guardStatus = await getAdminDeviceBanStatus(event)
  if (guardStatus.banned) {
    throw createError({
      statusCode: 429,
      statusMessage: 'Too Many Requests',
      data: {
        detail: 'ADMIN_LOGIN_DEVICE_BANNED',
        retry_after_seconds: guardStatus.retryAfterSeconds,
      },
    })
  }

  const body = await readBody<LoginBody>(event)
  const username = String(body?.username || '').trim()
  const password = String(body?.password || '')

  if (!username || !password) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Bad Request',
      data: { detail: 'MISSING_ADMIN_CREDENTIALS' },
    })
  }

  if (!validateAdminCredentials(username, password)) {
    const failure = await registerAdminLoginFailure(event, username)
    throw createError({
      statusCode: failure.banned ? 429 : 401,
      statusMessage: failure.banned ? 'Too Many Requests' : 'Unauthorized',
      data: failure.banned
        ? {
            detail: 'ADMIN_LOGIN_DEVICE_BANNED',
            retry_after_seconds: failure.retryAfterSeconds,
          }
        : { detail: 'INVALID_ADMIN_CREDENTIALS' },
    })
  }

  await clearAdminLoginGuard(event)
  setAdminSession(event)
  return { ok: true }
})
