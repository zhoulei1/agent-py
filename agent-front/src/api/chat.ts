import { buildUrl, request } from '@/api/http'
import type { ChatMessage, Conversation } from '@/types'

/**
 * 会话与消息接口，一一对应后端 `AIController`。
 *
 * GET    /ai/conversations                    会话列表（按 createTime DESC）
 * POST   /ai/conversation                     新建会话，后端生成 conversationId
 * PUT    /ai/conversation                     重命名会话（空返回）
 * DELETE /ai/conversation/{conversationId}    删除会话及其消息（空返回）
 * GET    /ai/chatMessages?conversationId=     会话消息（按 createTime ASC）
 */

export function listConversations(): Promise<Conversation[]> {
  return request<Conversation[]>('/ai/conversations')
}

export function createConversation(conversationName: string): Promise<Conversation> {
  return request<Conversation>('/ai/conversation', {
    method: 'POST',
    body: { conversationName },
  })
}

export function renameConversation(
  conversationId: string,
  conversationName: string,
): Promise<void> {
  return request<void>('/ai/conversation', {
    method: 'PUT',
    body: { conversationId, conversationName },
  })
}

export function deleteConversation(conversationId: string): Promise<void> {
  return request<void>(`/ai/conversation/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  })
}

export function listChatMessages(conversationId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(buildUrl('/ai/chatMessages', { conversationId }))
}
