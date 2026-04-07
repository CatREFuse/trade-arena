const ISO_TIMESTAMP_WITHOUT_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

export function parseApiDate(value?: string | number | Date | null): Date {
  if (value === null || value === undefined || value === '') {
    return new Date(Number.NaN)
  }

  if (value instanceof Date) {
    return new Date(value.getTime())
  }

  if (typeof value === 'number') {
    return new Date(value)
  }

  const normalized = value.trim()
  if (!normalized) {
    return new Date(Number.NaN)
  }

  if (ISO_TIMESTAMP_WITHOUT_TZ_RE.test(normalized)) {
    return new Date(`${normalized}Z`)
  }

  return new Date(normalized)
}
