<script setup lang="ts">
import { MenuOutline } from '@vicons/ionicons5'
import { NButton, NDrawer, NIcon, NInput, NModal, useDialog, useMessage } from 'naive-ui'
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ChatInput from '@/components/chat/ChatInput.vue'
import MessageList from '@/components/chat/MessageList.vue'
import WelcomeScreen from '@/components/chat/WelcomeScreen.vue'
import SideBar from '@/components/layout/SideBar.vue'
import { useChatStore } from '@/stores/chat'
import type { Conversation } from '@/types'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const message = useMessage()
const dialog = useDialog()

const drawerOpen = ref(false)

// ---------- 新建会话弹框 ----------
const createModalOpen = ref(false)
const newConversationName = ref('新会话')
const creating = ref(false)

const routeConversationId = computed(() => {
  const value = route.params.conversationId
  return typeof value === 'string' && value ? value : null
})

/** 无选中会话时隐藏输入区，与原 chat.html 一致 */
const showInput = computed(() => chatStore.currentConversationId !== null)

// ---------- 路由驱动的会话加载 ----------
watch(
  routeConversationId,
  async (conversationId) => {
    if (!conversationId) {
      chatStore.resetCurrent()
      return
    }
    if (conversationId === chatStore.currentConversationId) return
    try {
      await chatStore.openConversation(conversationId)
    } catch (e) {
      message.error(`加载会话消息失败：${(e as Error).message}`)
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    await chatStore.loadConversations()
  } catch (e) {
    message.error(`加载历史会话失败：${(e as Error).message}，请确认后端服务已启动`)
  }
})

/**
 * 流式生成中执行会打断的操作前先确认。
 * 替代原 chat.html 的原生 confirm()。
 */
function confirmInterrupt(action: () => void) {
  if (!chatStore.isStreaming) {
    action()
    return
  }
  dialog.warning({
    title: '正在生成回复',
    content: '继续操作将中断当前生成，确定吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: () => {
      chatStore.abort()
      action()
    },
  })
}

// ---------- 会话操作 ----------
function openCreateModal() {
  confirmInterrupt(() => {
    newConversationName.value = '新会话'
    createModalOpen.value = true
  })
}

async function submitCreate() {
  const name = newConversationName.value.trim() || '新会话'
  creating.value = true
  try {
    const created = await chatStore.createConversation(name)
    createModalOpen.value = false
    drawerOpen.value = false
    await router.push(`/chat/${created.conversationId}`)
  } catch (e) {
    message.error(`创建会话失败：${(e as Error).message}`)
  } finally {
    creating.value = false
  }
}

function selectConversation(item: Conversation) {
  if (item.conversationId === chatStore.currentConversationId) {
    drawerOpen.value = false
    return
  }
  confirmInterrupt(() => {
    drawerOpen.value = false
    void router.push(`/chat/${item.conversationId}`)
  })
}

function renameConversation(item: Conversation) {
  const input = ref(item.conversationName ?? '')
  dialog.create({
    title: '重命名会话',
    content: () =>
      h(NInput, {
        value: input.value,
        placeholder: '请输入会话标题',
        maxlength: 50,
        autofocus: true,
        'onUpdate:value': (v: string) => (input.value = v),
      }),
    positiveText: '保存',
    negativeText: '取消',
    onPositiveClick: async () => {
      const name = input.value.trim()
      if (!name || name === item.conversationName) return
      try {
        await chatStore.renameConversation(item.conversationId, name)
        message.success('已重命名')
      } catch (e) {
        message.error(`重命名失败：${(e as Error).message}`)
      }
    },
  })
}

function removeConversation(item: Conversation) {
  dialog.error({
    title: '删除会话',
    content: `确定删除「${item.conversationName || '未命名会话'}」吗？会话和聊天记录将无法恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const wasCurrent = item.conversationId === chatStore.currentConversationId
        await chatStore.removeConversation(item.conversationId)
        message.success('已删除')
        if (wasCurrent) await router.push('/chat')
      } catch (e) {
        message.error(`删除失败：${(e as Error).message}`)
      }
    },
  })
}

function onSend(text: string) {
  chatStore.sendMessage(text)
}
</script>

<template>
  <div class="layout">
    <!-- 桌面端固定侧栏 -->
    <SideBar
      class="layout__sidebar"
      @create="openCreateModal"
      @select="selectConversation"
      @rename="renameConversation"
      @remove="removeConversation"
    />

    <!-- 移动端抽屉侧栏 -->
    <n-drawer v-model:show="drawerOpen" :width="260" placement="left">
      <SideBar
        @create="openCreateModal"
        @select="selectConversation"
        @rename="renameConversation"
        @remove="removeConversation"
      />
    </n-drawer>

    <main class="layout__main">
      <header class="layout__header">
        <n-button
          class="layout__menu"
          quaternary
          circle
          size="small"
          title="打开会话列表"
          @click="drawerOpen = true"
        >
          <template #icon>
            <n-icon :component="MenuOutline" />
          </template>
        </n-button>
        <span class="layout__title">{{ chatStore.currentTitle }}</span>
      </header>

      <WelcomeScreen
        v-if="!chatStore.currentConversationId"
        show-create
        @create="openCreateModal"
      />
      <WelcomeScreen v-else-if="!chatStore.hasMessages && !chatStore.loadingMessages" />
      <MessageList
        v-else
        :messages="chatStore.messages"
        :loading="chatStore.loadingMessages"
      />

      <ChatInput
        v-if="showInput"
        :streaming="chatStore.isStreaming"
        @send="onSend"
        @stop="chatStore.abort()"
      />
    </main>

    <!-- 新建会话 -->
    <n-modal
      v-model:show="createModalOpen"
      preset="dialog"
      title="新建会话"
      positive-text="创建"
      negative-text="取消"
      :loading="creating"
      @positive-click="submitCreate"
    >
      <n-input
        v-model:value="newConversationName"
        placeholder="请输入会话标题"
        :maxlength="50"
        autofocus
        @keydown.enter="submitCreate"
      />
      <p class="modal-hint">输入对话标题，方便后续查找</p>
    </n-modal>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  /* 用视口高度而非 100%：Naive UI 的 Provider 会渲染中间包装层，
     使 .layout 的 height:100% 失效，导致消息列表拿不到确定高度、无法滚动 */
  height: 100vh;
  height: 100dvh;
  background: var(--app-bg);
}

.layout__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.layout__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--header-bg);
  backdrop-filter: blur(8px);
}

.layout__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layout__menu {
  display: none;
}

.modal-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 768px) {
  .layout__sidebar {
    display: none;
  }

  .layout__menu {
    display: inline-flex;
  }

  .layout__header {
    padding: 10px 14px;
  }
}
</style>
