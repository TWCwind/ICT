export type ApiError = {
  code: string
  message: string
}

export type ApiResponse<T> = {
  request_id: string
  success: boolean
  data: T
  error?: ApiError | null
}

// HTTP / 网络层失败的统一中文说明。页面捕获后直接展示，避免把
// “Unexpected token …”/“Failed to fetch” 这类英文底层错误暴露给用户。
function httpErrorMessage(status: number): string {
  if (status >= 500) return `本地服务暂时不可用（HTTP ${status}），请确认后端已启动后重试`
  if (status === 404) return '请求的接口不存在（HTTP 404），请刷新页面后重试'
  return `请求失败（HTTP ${status}），请稍后重试`
}

async function parseEnvelope<T>(resp: Response, fallback: string): Promise<ApiResponse<T>> {
  const text = await resp.text()
  try {
    const body = JSON.parse(text) as ApiResponse<T>
    if (!resp.ok) {
      // 信封格式但 HTTP 失败：优先用后端返回的中文 message
      body.success = false
      if (!body.error?.message) {
        body.error = { code: `HTTP_${resp.status}`, message: httpErrorMessage(resp.status) }
      }
    }
    return body
  } catch {
    // 非 JSON 正文（例如代理返回的纯文本错误页）
    return {
      request_id: '',
      success: false,
      data: null as T,
      error: { code: resp.ok ? 'INVALID_BODY' : `HTTP_${resp.status}`, message: resp.ok ? `${fallback}：服务返回了无法解析的内容` : httpErrorMessage(resp.status) },
    }
  }
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  let resp: Response
  try {
    resp = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    // 后端断开 / 代理不可达：fetch 直接拒绝
    return { request_id: '', success: false, data: null as T, error: { code: 'NETWORK', message: '本地服务未连接，请确认后端已启动后重试' } }
  }
  return parseEnvelope<T>(resp, '请求失败')
}

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  let resp: Response
  try {
    resp = await fetch(path)
  } catch {
    return { request_id: '', success: false, data: null as T, error: { code: 'NETWORK', message: '本地服务未连接，请确认后端已启动后重试' } }
  }
  return parseEnvelope<T>(resp, '请求失败')
}

export type StreamEvent = {
  event: 'start' | 'status' | 'chunk' | 'final' | 'error' | 'done' | string
  data: any
}

export async function apiStream<T>(
  path: string,
  body: unknown,
  handlers: {
    onStart?: (data: any) => void
    onStatus?: (data: any) => void
    onChunk?: (data: any) => void
    onFinal?: (data: T) => void
    onError?: (message: string, data?: any) => void
    onDone?: () => void
  },
): Promise<void> {
  const resp = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
  })

  if (!resp.ok || !resp.body) {
    throw new Error(`流式请求失败：HTTP ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const rawEvent of events) {
      const line = rawEvent
        .split('\n')
        .map((line) => line.trim())
        .find((line) => line.startsWith('data: '))
      if (!line) continue
      const payload = JSON.parse(line.slice(6)) as StreamEvent
      if (payload.event === 'start') handlers.onStart?.(payload.data)
      else if (payload.event === 'status') handlers.onStatus?.(payload.data)
      else if (payload.event === 'chunk') handlers.onChunk?.(payload.data)
      else if (payload.event === 'final') handlers.onFinal?.(payload.data as T)
      else if (payload.event === 'error') handlers.onError?.(payload.data?.message || '流式请求失败', payload.data)
      else if (payload.event === 'done') handlers.onDone?.()
    }
  }
}

