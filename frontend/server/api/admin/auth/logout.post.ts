import { clearAdminSession } from '~/server/utils/adminAuth'

export default defineEventHandler((event) => {
  clearAdminSession(event)
  return { ok: true }
})
