import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as chatApi from '@/api/chat'
import { CURRENT_USER_ID } from '@/config'
import { getChatTransport } from '@/transport'
import type { ChatStreamHandle } from '@/transport/types'
import { toUiMessage, type Conversation, type UiMessage } from '@/types'

let uid = 0
function nextId(prefix: string): string {
  return `${prefix}-${Date.now()}-${++uid}`
}

export const useChatStore = defineStore('chat', () => {
  // ---------- state ----------
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<string | null>(null)
  const messages = ref<UiMessage[]>([])

  const loadingItems = ref(false)
  const loadingMessages = ref(false)
  const isStreaming = ref(false)

  /** 进行中的流句柄，用于中断 */
  let streamHandle: ChatStreamHandle | null = null

  // ---------- getters ----------
  const currentConversation = computed(
    () =>
      conversations.value.find((c) => c.conversationId === currentConversationId.value) ?? null,
  )

  const currentTitle = computed(
    () => currentConversation.value?.conversationName || 'AI 助手',
  )

  const hasMessages = computed(() => messages.value.length > 0)

  // ---------- actions ----------

  async function loadConversations() {
    loadingItems.value = true
    try {
      conversations.value = await chatApi.listConversations()
    } finally {
      loadingItems.value = false
    }
  }

  async function createConversation(conversationName: string): Promise<Conversation> {
    const created = await chatApi.createConversation(conversationName)
    // 后端列表按 createTime DESC 排序，新会话置顶与之一致
    conversations.value = [created, ...conversations.value]
    return created
  }

  async function renameConversation(conversationId: string, conversationName: string) {
    await chatApi.renameConversation(conversationId, conversationName)
    const target = conversations.value.find((c) => c.conversationId === conversationId)
    if (target) target.conversationName = conversationName
  }

  async function removeConversation(conversationId: string) {
    await chatApi.deleteConversation(conversationId)
    conversations.value = conversations.value.filter(
      (c) => c.conversationId !== conversationId,
    )
    if (currentConversationId.value === conversationId) {
      resetCurrent()
    }
  }

  function resetCurrent() {
    abort()
    currentConversationId.value = null
    messages.value = []
  }

  /** 切换到指定会话并加载其历史消息 */
  async function openConversation(conversationId: string) {
    abort()
    currentConversationId.value = conversationId
    messages.value = []
    loadingMessages.value = true
    try {
      const history = await chatApi.listChatMessages(conversationId)
      // 期间用户可能又切走了，丢弃过期结果
      if (currentConversationId.value !== conversationId) return
      messages.value = history.map(toUiMessage)
    } finally {
      if (currentConversationId.value === conversationId) loadingMessages.value = false
    }
  }

  /**
   * 发送消息并接收流式回复。
   *
   * 乐观插入用户气泡 → 插入 assistant 占位（打字动画）→ 逐片段累加 → 落定。
   */
  function sendMessage(text: string) {
    const content = text.trim()
    const conversationId = currentConversationId.value
    if (!content || !conversationId || isStreaming.value) return

    messages.value.push({
      id: nextId('user'),
      role: 'user',
      content,
    })

    const assistant: UiMessage = {
      id: nextId('assistant'),
      role: 'assistant',
      content: '',
      streaming: true,
    }
    messages.value.push(assistant)

    isStreaming.value = true

    const settle = (finalContent: string, isError = false) => {
      // 会话已被切走/删除时，不要把内容写到别的会话里
      if (currentConversationId.value !== conversationId) return
      const target = messages.value.find((m) => m.id === assistant.id)
      if (!target) return
      target.content = finalContent
      target.streaming = false
      target.error = isError
    }

    streamHandle = getChatTransport().send(
      {
        conversationId,
        message: content,
        userId: CURRENT_USER_ID,
      },
      {
        onChunk(delta) {
          if (currentConversationId.value !== conversationId) return
          const target = messages.value.find((m) => m.id === assistant.id)
          if (target) target.content += delta
        },
        onDone(full) {
          settle(full || assistant.content || '（无响应内容）')
          isStreaming.value = false
          streamHandle = null
          // 后端已把消息落库，刷新列表让 updateTime 排序生效
          void loadConversations().catch(() => undefined)
        },
        onError(error) {
          const target = messages.value.find((m) => m.id === assistant.id)
          const received = target?.content ?? ''
          settle(received || `请求失败：${error.message}`, !received)
          isStreaming.value = false
          streamHandle = null
        },
      },
    )
  }

  /** 中断当前流式生成，已接收内容保留 */
  function abort() {
    if (streamHandle) {
      streamHandle.abort()
      streamHandle = null
    }
    isStreaming.value = false
    const last = messages.value[messages.value.length - 1]
    if (last?.streaming) {
      last.streaming = false
      if (!last.content) last.content = '（已中断）'
    }
  }

  return {
    // state
    conversations,
    currentConversationId,
    messages,
    loadingItems,
    loadingMessages,
    isStreaming,
    // getters
    currentConversation,
    currentTitle,
    hasMessages,
    // actions
    loadConversations,
    createConversation,
    renameConversation,
    removeConversation,
    openConversation,
    resetCurrent,
    sendMessage,
    abort,
  }
})
