import { createError, readBody } from 'h3'
import { setAdminSession, validateAdminCredentials } from '~/server/utils/adminAuth'

interface LoginBody {
  username?: string
  password?: string
}

export default defineEventHandler(async (event) => {
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
    throw createError({
      statusCode: 401,
      statusMessage: 'Unauthorized',
      data: { detail: 'INVALID_ADMIN_CREDENTIALS' },
    })
  }

  setAdminSession(event)
  return { ok: true }
})
