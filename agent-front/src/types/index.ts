/**
 * 与后端 DTO 对齐的类型定义。
 */

/** 对应 langchain4j 的 `ChatMessageType`，后端实际只会返回 USER / AI */
export type ChatMessageType = 'SYSTEM' | 'USER' | 'AI' | 'TOOL_EXECUTION_RESULT' | 'CUSTOM'

/**
 * 对应后端 `entity/Conversation`。
 *
 * 后端 `ConversationService.save()` 只生成 conversationId，因此前端全程用
 * `conversationId` 作为会话唯一键。
 */
export interface Conversation {
  userId?: string | null
  conversationId: string
  conversationName?: string | null
  createTime?: string | null
  updateTime?: string | null
}

/** 对应后端 `entity/ChatMessage` */
export interface ChatMessage {
  messageId?: string | null
  conversationId: string
  userId?: string | null
  messageText?: string | null
  chatMessageType: ChatMessageType
  createTime?: string | null
}

/** 界面上的消息角色 */
export type MessageRole = 'user' | 'assistant'

/** 界面渲染用的消息模型（区别于后端存储模型） */
export interface UiMessage {
  /** 前端本地唯一 id，用于 v-for key 与流式更新定位 */
  id: string
  role: MessageRole
  content: string
  /** 是否正在流式接收中（显示打字动画） */
  streaming?: boolean
  /** 该条消息是否为错误提示 */
  error?: boolean
  createTime?: string | null
}

/** 把后端消息映射为界面消息 */
export function toUiMessage(msg: ChatMessage, index: number): UiMessage {
  return {
    id: msg.messageId ?? `history-${index}`,
    role: msg.chatMessageType === 'USER' ? 'user' : 'assistant',
    content: msg.messageText ?? '',
    createTime: msg.createTime,
  }
}
