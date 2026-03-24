import { hasValidAdminSession } from '~/server/utils/adminAuth'

export default defineEventHandler((event) => {
  return { authenticated: hasValidAdminSession(event) }
})
