import { API_BASE_URL } from '@/config'

/** 带状态码的请求错误 */
export class HttpError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}

export function buildUrl(path: string, query?: Record<string, string | undefined>): string {
  const base = `${API_BASE_URL}${path}`
  if (!query) return base

  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.append(key, value)
  }
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

async function toError(resp: Response): Promise<HttpError> {
  let detail = ''
  try {
    detail = (await resp.text()).slice(0, 200)
  } catch {
    // 读取失败时忽略，仅保留状态码
  }
  return new HttpError(resp.status, detail || `请求失败（HTTP ${resp.status}）`)
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

/**
 * 发起请求并解析 JSON。
 *
 * 后端的 PUT /ai/conversation 与 DELETE /ai/conversation/{conversationId} 是 void 返回（空 body），
 * 这里对空响应做容错，返回 undefined 而不是抛 JSON 解析错误。
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options

  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })

  if (!resp.ok) throw await toError(resp)

  const text = await resp.text()
  if (!text) return undefined as T

  return JSON.parse(text) as T
}
