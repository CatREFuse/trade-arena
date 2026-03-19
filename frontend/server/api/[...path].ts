import { getRequestURL, proxyRequest } from 'h3'

const BACKEND_ORIGIN = 'http://127.0.0.1:8000'

export default defineEventHandler((event) => {
  const url = getRequestURL(event)
  return proxyRequest(event, `${BACKEND_ORIGIN}${url.pathname}${url.search}`)
})
