import { createError, getRequestURL, getRouterParam, proxyRequest } from 'h3'

const BACKEND_ORIGIN = process.env.NUXT_BACKEND_URL || 'http://127.0.0.1:8000'

export default defineEventHandler((event) => {
  const fileName = getRouterParam(event, 'name')
  if (!fileName) {
    throw createError({ statusCode: 400, statusMessage: 'Missing file name' })
  }

  const url = getRequestURL(event)
  const encodedName = encodeURIComponent(fileName)
  return proxyRequest(event, `${BACKEND_ORIGIN}/api/file/${encodedName}${url.search}`)
})
