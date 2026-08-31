<script setup lang="ts">
import {
  AddOutline,
  MoonOutline,
  PersonCircleOutline,
  SparklesOutline,
  SunnyOutline,
} from '@vicons/ionicons5'
import { NButton, NEmpty, NIcon, NSpin, NTooltip } from 'naive-ui'

import ChatHistoryItem from '@/components/layout/ChatHistoryItem.vue'
import { useChatStore } from '@/stores/chat'
import { useThemeStore } from '@/stores/theme'
import type { Conversation } from '@/types'

const chatStore = useChatStore()
const themeStore = useThemeStore()

const emit = defineEmits<{
  create: []
  select: [item: Conversation]
  rename: [item: Conversation]
  remove: [item: Conversation]
}>()
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__header">
      <div class="sidebar__logo">
        <n-icon :size="18" :component="SparklesOutline" />
      </div>
      <span class="sidebar__title">AI 助手</span>

      <n-tooltip trigger="hover" placement="bottom">
        <template #trigger>
          <n-button quaternary circle size="small" @click="themeStore.toggle()">
            <template #icon>
              <n-icon :component="themeStore.isDark ? SunnyOutline : MoonOutline" />
            </template>
          </n-button>
        </template>
        {{ themeStore.isDark ? '切换到浅色' : '切换到深色' }}
      </n-tooltip>
    </div>

    <div class="sidebar__new">
      <n-button type="primary" block strong @click="emit('create')">
        <template #icon>
          <n-icon :component="AddOutline" />
        </template>
        新建会话
      </n-button>
    </div>

    <div class="sidebar__list scroll-y">
      <p class="sidebar__label">历史会话</p>

      <div v-if="chatStore.loadingItems" class="sidebar__loading">
        <n-spin size="small" />
      </div>

      <n-empty
        v-else-if="chatStore.conversations.length === 0"
        description="暂无历史会话"
        size="small"
        class="sidebar__empty"
      />

      <template v-else>
        <ChatHistoryItem
          v-for="item in chatStore.conversations"
          :key="item.conversationId"
          :item="item"
          :active="item.conversationId === chatStore.currentConversationId"
          @select="emit('select', $event)"
          @rename="emit('rename', $event)"
          @remove="emit('remove', $event)"
        />
      </template>
    </div>

    <div class="sidebar__footer">
      <n-icon :size="26" :component="PersonCircleOutline" />
      <span>用户</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  user-select: none;
}

.sidebar__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px 10px;
}

.sidebar__logo {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
}

.sidebar__title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar__new {
  padding: 4px 14px 12px;
}

.sidebar__list {
  flex: 1;
  min-height: 0;
  padding: 0 8px 8px;
}

.sidebar__label {
  padding: 6px 8px 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.sidebar__loading {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.sidebar__empty {
  padding: 20px 0;
}

.sidebar__footer {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
