import { API_BASE_URL } from '@/config'
import { parseEventFrame, splitFrames } from '@/transport/sseParser'
import type {
  ChatSendPayload,
  ChatStreamHandle,
  ChatStreamHandlers,
  ChatTransport,
} from '@/transport/types'

/**
 * 基于 fetch + ReadableStream 的 SSE 传输。
 *
 * 对接后端 `POST /ai/streamChat`（produces = text/event-stream）。
 * 用 fetch 而非 EventSource，因为 EventSource 只支持 GET、无法发送 JSON body。
 */
export class SseChatTransport implements ChatTransport {
  readonly name = 'sse'

  send(payload: ChatSendPayload, handlers: ChatStreamHandlers): ChatStreamHandle {
    const controller = new AbortController()
    let aborted = false
    let full = ''

    const run = async () => {
      const resp = await fetch(`${API_BASE_URL}/ai/streamChat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: payload.message,
          conversationId: payload.conversationId,
          userId: payload.userId,
        }),
        signal: controller.signal,
      })

      if (!resp.ok) {
        throw new Error(`请求失败（HTTP ${resp.status}）`)
      }
      if (!resp.body) {
        throw new Error('当前浏览器不支持流式响应')
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const emit = (frame: string) => {
        const data = parseEventFrame(frame)
        if (data === null) return
        full += data
        handlers.onChunk(data)
      }

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const { frames, rest } = splitFrames(buffer)
        buffer = rest
        frames.forEach(emit)
      }

      // flush 解码器与缓冲区里最后一个没有以空行收尾的帧
      buffer += decoder.decode()
      if (buffer.trim()) emit(buffer)

      handlers.onDone(full)
    }

    run().catch((error: unknown) => {
      // 用户主动中断：不算错误，把已收到的内容落定即可
      if (aborted || (error instanceof DOMException && error.name === 'AbortError')) {
        handlers.onDone(full)
        return
      }
      handlers.onError(error instanceof Error ? error : new Error(String(error)))
    })

    return {
      abort() {
        aborted = true
        controller.abort()
      },
    }
  }
}
