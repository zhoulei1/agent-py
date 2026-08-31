/** 一次对话请求的载荷，对应后端 `pojo/QueryVo` */
export interface ChatSendPayload {
  conversationId: string
  message: string
  userId: string
}

/** 流式回调 */
export interface ChatStreamHandlers {
  /** 收到一个增量片段 */
  onChunk(delta: string): void
  /** 流正常结束，full 为完整内容 */
  onDone(full: string): void
  /** 流出错（用户主动中断不会触发此回调） */
  onError(error: Error): void
}

/** 一次进行中的流，可主动中断 */
export interface ChatStreamHandle {
  abort(): void
}

/**
 * 聊天传输抽象。
 *
 * store 只依赖此接口，因此更换底层传输（SSE / Socket.IO / WebSocket）
 * 不需要改动任何组件或状态逻辑。
 */
export interface ChatTransport {
  readonly name: string
  send(payload: ChatSendPayload, handlers: ChatStreamHandlers): ChatStreamHandle
  dispose?(): void
}
