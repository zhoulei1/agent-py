import { io, type Socket } from 'socket.io-client'

import { SOCKET_URL } from '@/config'
import type {
  ChatSendPayload,
  ChatStreamHandle,
  ChatStreamHandlers,
  ChatTransport,
} from '@/transport/types'

/**
 * Socket.IO 传输适配器。
 *
 * ⚠️ 当前后端【尚未实现】Socket.IO 服务端：
 * `build.gradle` 中没有 netty-socketio 依赖，`AIController` 只提供 SSE
 * （`POST /ai/streamChat`, produces = text/event-stream）。
 * 因此把 `VITE_CHAT_TRANSPORT` 切成 `socketio` 会连接失败。
 *
 * 启用前需要在后端补齐：
 *   1. build.gradle 引入 `com.corundumstudio.socketio:netty-socketio`
 *   2. 配置 SocketIOServer Bean 并随 Spring 生命周期启停
 *   3. 实现下列事件协议
 *
 * 事件协议（客户端 → 服务端）：
 *   - `chat:send`   载荷 ChatSendPayload，额外带 `requestId` 用于多路复用
 *   - `chat:abort`  载荷 `{ requestId }`，中断指定请求
 *
 * 事件协议（服务端 → 客户端）：
 *   - `chat:chunk`  `{ requestId, delta }`  增量片段
 *   - `chat:done`   `{ requestId, full? }`  流结束
 *   - `chat:error`  `{ requestId, message }` 出错
 */
export class SocketIoChatTransport implements ChatTransport {
  readonly name = 'socketio'

  private socket: Socket | null = null
  private seq = 0

  private ensureSocket(): Socket {
    if (!this.socket) {
      // SOCKET_URL 为空时连同源，握手路径 /socket.io 已在 vite.config.ts 配了代理
      this.socket = SOCKET_URL
        ? io(SOCKET_URL, { transports: ['websocket', 'polling'] })
        : io({ transports: ['websocket', 'polling'] })
    }
    return this.socket
  }

  send(payload: ChatSendPayload, handlers: ChatStreamHandlers): ChatStreamHandle {
    const socket = this.ensureSocket()
    const requestId = `req-${Date.now()}-${++this.seq}`

    let full = ''
    let settled = false

    const cleanup = () => {
      socket.off('chat:chunk', onChunk)
      socket.off('chat:done', onDone)
      socket.off('chat:error', onError)
      socket.off('connect_error', onConnectError)
    }

    const finish = (fn: () => void) => {
      if (settled) return
      settled = true
      cleanup()
      fn()
    }

    const onChunk = (data: { requestId: string; delta: string }) => {
      if (data.requestId !== requestId || settled) return
      full += data.delta
      handlers.onChunk(data.delta)
    }

    const onDone = (data: { requestId: string; full?: string }) => {
      if (data.requestId !== requestId) return
      finish(() => handlers.onDone(data.full ?? full))
    }

    const onError = (data: { requestId: string; message?: string }) => {
      if (data.requestId !== requestId) return
      finish(() => handlers.onError(new Error(data.message ?? '服务端返回错误')))
    }

    const onConnectError = (error: Error) => {
      finish(() =>
        handlers.onError(
          new Error(`Socket.IO 连接失败：${error.message}（后端可能尚未启用 Socket.IO 服务端）`),
        ),
      )
    }

    socket.on('chat:chunk', onChunk)
    socket.on('chat:done', onDone)
    socket.on('chat:error', onError)
    socket.on('connect_error', onConnectError)

    socket.emit('chat:send', { ...payload, requestId })

    return {
      abort: () => {
        socket.emit('chat:abort', { requestId })
        // 中断同样走 onDone，保留已接收内容，与 SSE 传输行为一致
        finish(() => handlers.onDone(full))
      },
    }
  }

  dispose(): void {
    this.socket?.disconnect()
    this.socket = null
  }
}
