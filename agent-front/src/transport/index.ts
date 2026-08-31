import { CHAT_TRANSPORT } from '@/config'
import { SocketIoChatTransport } from '@/transport/socketIoTransport'
import { SseChatTransport } from '@/transport/sseTransport'
import type { ChatTransport } from '@/transport/types'

export type {
  ChatSendPayload,
  ChatStreamHandle,
  ChatStreamHandlers,
  ChatTransport,
} from '@/transport/types'

/** 按配置创建传输实现。未知取值回退到 SSE。 */
export function createChatTransport(kind: string = CHAT_TRANSPORT): ChatTransport {
  if (kind === 'socketio') return new SocketIoChatTransport()
  if (kind !== 'sse') {
    console.warn(`[transport] 未知的 VITE_CHAT_TRANSPORT="${kind}"，回退到 sse`)
  }
  return new SseChatTransport()
}

/** 全局单例，供 store 使用 */
let instance: ChatTransport | null = null

export function getChatTransport(): ChatTransport {
  if (!instance) instance = createChatTransport()
  return instance
}
