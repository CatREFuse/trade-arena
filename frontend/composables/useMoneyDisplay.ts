type MoneyLike = number | string | null | undefined

export interface FormatCnyOptions {
  compact?: boolean
  minimumFractionDigits?: number
  maximumFractionDigits?: number
}

export function formatCny(value: MoneyLike, options: FormatCnyOptions = {}) {
  const amount = Number(value ?? 0)
  const safeAmount = Number.isFinite(amount) ? amount : 0
  const formatter = new Intl.NumberFormat('zh-CN', {
    notation: options.compact ? 'compact' : 'standard',
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.maximumFractionDigits ?? (options.compact ? 2 : 0),
  })

  return `¥${formatter.format(safeAmount)}`
}

export function toNumber(value: MoneyLike) {
  const amount = Number(value ?? 0)
  return Number.isFinite(amount) ? amount : 0
}
