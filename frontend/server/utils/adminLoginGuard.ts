import { createHash, randomBytes } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { basename, dirname, isAbsolute, resolve } from 'node:path'
import { deleteCookie, getCookie, getRequestHeader, setCookie } from 'h3'

const ADMIN_DEVICE_COOKIE = 'ta_console_device'
const DEFAULT_STATE_FILE = '.runtime/admin-login-guard/state.json'
const FAILURE_LIMIT = 3
const INITIAL_BAN_HOURS = 6

interface LoginGuardDeviceState {
  banLevel: number
  banUntil: string | null
  deviceKey: string
  failureCount: number
  lastFailureAt: string | null
  lastIp: string | null
  lastSuccessAt: string | null
  lastUserAgent: string | null
  lastUsername: string | null
}

interface LoginGuardState {
  devices: Record<string, LoginGuardDeviceState>
  version: number
}

export interface AdminDeviceBanStatus {
  banned: boolean
  deviceKey: string
  retryAfterSeconds: number
}

export interface AdminFailureResult extends AdminDeviceBanStatus {
  banHours: number | null
}

let stateWriteQueue = Promise.resolve()

function sha256(input: string): string {
  return createHash('sha256').update(input).digest('hex')
}

function getStateFilePath(): string {
  const runtimeConfig = useRuntimeConfig()
  const configured = String(runtimeConfig.adminLoginGuardStateFile || '').trim()
  const cwd = process.cwd()
  const projectRoot = basename(cwd) === 'frontend' ? resolve(cwd, '..') : cwd
  if (configured)
    return isAbsolute(configured) ? configured : resolve(projectRoot, configured)
  return resolve(projectRoot, DEFAULT_STATE_FILE)
}

function getNow(): Date {
  return new Date()
}

function createEmptyState(): LoginGuardState {
  return { version: 1, devices: {} }
}

function buildDeviceKey(fingerprint: string): string {
  return sha256(fingerprint).slice(0, 16)
}

function getClientIp(event: Parameters<typeof getCookie>[0]): string | null {
  const forwarded = getRequestHeader(event, 'x-forwarded-for')
  if (forwarded) {
    const first = forwarded.split(',')[0]?.trim()
    if (first)
      return first
  }
  return getRequestHeader(event, 'x-real-ip') || null
}

async function readStateFile(): Promise<LoginGuardState> {
  const stateFile = getStateFilePath()
  try {
    const raw = await readFile(stateFile, 'utf-8')
    const parsed = JSON.parse(raw) as Partial<LoginGuardState>
    if (!parsed || typeof parsed !== 'object')
      return createEmptyState()
    return {
      version: Number(parsed.version || 1),
      devices: typeof parsed.devices === 'object' && parsed.devices ? parsed.devices as Record<string, LoginGuardDeviceState> : {},
    }
  }
  catch (error: any) {
    if (error?.code === 'ENOENT')
      return createEmptyState()
    throw error
  }
}

async function writeStateFile(state: LoginGuardState): Promise<void> {
  const stateFile = getStateFilePath()
  await mkdir(dirname(stateFile), { recursive: true })
  await writeFile(stateFile, `${JSON.stringify(state, null, 2)}\n`, 'utf-8')
}

async function withStateMutation<T>(mutator: (state: LoginGuardState) => Promise<T> | T): Promise<T> {
  const run = async () => {
    const state = await readStateFile()
    const result = await mutator(state)
    await writeStateFile(state)
    return result
  }
  const pending = stateWriteQueue.then(run, run)
  stateWriteQueue = pending.then(() => undefined, () => undefined)
  return pending
}

function getOrCreateDeviceState(state: LoginGuardState, fingerprint: string): LoginGuardDeviceState {
  if (!state.devices[fingerprint]) {
    state.devices[fingerprint] = {
      banLevel: 0,
      banUntil: null,
      deviceKey: buildDeviceKey(fingerprint),
      failureCount: 0,
      lastFailureAt: null,
      lastIp: null,
      lastSuccessAt: null,
      lastUserAgent: null,
      lastUsername: null,
    }
  }
  return state.devices[fingerprint]
}

function getRetryAfterSeconds(banUntil: string | null, now: Date): number {
  if (!banUntil)
    return 0
  const remainingMs = new Date(banUntil).getTime() - now.getTime()
  if (remainingMs <= 0)
    return 0
  return Math.ceil(remainingMs / 1000)
}

export function ensureAdminDeviceFingerprint(event: Parameters<typeof getCookie>[0]): string {
  const existing = getCookie(event, ADMIN_DEVICE_COOKIE)
  if (existing)
    return existing

  const runtimeConfig = useRuntimeConfig()
  const fingerprint = randomBytes(24).toString('hex')
  setCookie(event, ADMIN_DEVICE_COOKIE, fingerprint, {
    httpOnly: true,
    maxAge: 60 * 60 * 24 * 365,
    path: '/',
    sameSite: 'lax',
    secure: Boolean(runtimeConfig.adminCookieSecure),
  })
  return fingerprint
}

export async function getAdminDeviceBanStatus(event: Parameters<typeof getCookie>[0]): Promise<AdminDeviceBanStatus> {
  const fingerprint = ensureAdminDeviceFingerprint(event)
  const state = await readStateFile()
  const device = state.devices[fingerprint]
  const now = getNow()
  const retryAfterSeconds = getRetryAfterSeconds(device?.banUntil || null, now)
  return {
    banned: retryAfterSeconds > 0,
    deviceKey: device?.deviceKey || buildDeviceKey(fingerprint),
    retryAfterSeconds,
  }
}

export async function registerAdminLoginFailure(
  event: Parameters<typeof getCookie>[0],
  username: string,
): Promise<AdminFailureResult> {
  const fingerprint = ensureAdminDeviceFingerprint(event)
  const userAgent = getRequestHeader(event, 'user-agent') || null
  const ip = getClientIp(event)
  const now = getNow()

  return withStateMutation(async (state) => {
    const device = getOrCreateDeviceState(state, fingerprint)
    const retryAfterSeconds = getRetryAfterSeconds(device.banUntil, now)
    if (retryAfterSeconds > 0) {
      return {
        banned: true,
        banHours: null,
        deviceKey: device.deviceKey,
        retryAfterSeconds,
      }
    }

    device.failureCount += 1
    device.lastFailureAt = now.toISOString()
    device.lastIp = ip
    device.lastUserAgent = userAgent
    device.lastUsername = username || null

    if (device.failureCount < FAILURE_LIMIT) {
      return {
        banned: false,
        banHours: null,
        deviceKey: device.deviceKey,
        retryAfterSeconds: 0,
      }
    }

    device.failureCount = 0
    device.banLevel += 1
    const banHours = INITIAL_BAN_HOURS * (2 ** (device.banLevel - 1))
    device.banUntil = new Date(now.getTime() + banHours * 60 * 60 * 1000).toISOString()
    return {
      banned: true,
      banHours,
      deviceKey: device.deviceKey,
      retryAfterSeconds: getRetryAfterSeconds(device.banUntil, now),
    }
  })
}

export async function clearAdminLoginGuard(event: Parameters<typeof getCookie>[0]): Promise<void> {
  const fingerprint = getCookie(event, ADMIN_DEVICE_COOKIE)
  if (!fingerprint)
    return

  const userAgent = getRequestHeader(event, 'user-agent') || null
  const ip = getClientIp(event)
  const now = getNow().toISOString()

  await withStateMutation(async (state) => {
    const device = getOrCreateDeviceState(state, fingerprint)
    device.failureCount = 0
    device.banLevel = 0
    device.banUntil = null
    device.lastSuccessAt = now
    device.lastIp = ip
    device.lastUserAgent = userAgent
  })
}

export function clearAdminDeviceFingerprint(event: Parameters<typeof deleteCookie>[0]) {
  deleteCookie(event, ADMIN_DEVICE_COOKIE, { path: '/' })
}
