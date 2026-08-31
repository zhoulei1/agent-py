<script setup lang="ts">
import { CopyOutline, PersonOutline, SparklesOutline } from '@vicons/ionicons5'
import { NButton, NIcon, NTooltip, useMessage } from 'naive-ui'
import { computed } from 'vue'

import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
import TypingIndicator from '@/components/chat/TypingIndicator.vue'
import type { UiMessage } from '@/types'

const props = defineProps<{ message: UiMessage }>()

const message = useMessage()

const isUser = computed(() => props.message.role === 'user')
/** 空内容 + streaming 时显示打字动画 */
const showTyping = computed(() => props.message.streaming && !props.message.content)

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    message.success('已复制')
  } catch {
    message.error('复制失败')
  }
}
</script>

<template>
  <div class="msg" :class="isUser ? 'msg--user' : 'msg--assistant'">
    <!-- DeepSeek 布局：用户消息只有气泡不带头像；AI 消息带头像、无气泡 -->
    <div v-if="!isUser" class="msg__avatar">
      <n-icon :size="18" :component="SparklesOutline" />
    </div>

    <div class="msg__body">
      <div v-if="isUser" class="msg__bubble">
        <n-icon class="msg__user-icon" :size="14" :component="PersonOutline" />
        <span class="msg__user-text">{{ props.message.content }}</span>
      </div>

      <template v-else>
        <TypingIndicator v-if="showTyping" />
        <MarkdownRenderer
          v-else
          :content="props.message.content"
          :streaming="props.message.streaming"
          :class="{ 'is-error': props.message.error }"
        />

        <div v-if="!props.message.streaming && props.message.content" class="msg__actions">
          <n-tooltip trigger="hover" placement="bottom">
            <template #trigger>
              <n-button quaternary size="tiny" @click="copyContent">
                <template #icon>
                  <n-icon :component="CopyOutline" />
                </template>
              </n-button>
            </template>
            复制回复
          </n-tooltip>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  gap: 12px;
  width: 100%;
  max-width: var(--content-width);
  margin: 0 auto;
  animation: fade-in 0.25s ease;
}

.msg--user {
  justify-content: flex-end;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.msg__avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  margin-top: 2px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
}

.msg__body {
  min-width: 0;
}

.msg--assistant .msg__body {
  flex: 1;
}

.msg--user .msg__body {
  max-width: 80%;
}

/* 用户气泡：右对齐、浅蓝底、宽度自适应 */
.msg__bubble {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  border-top-right-radius: 6px;
  background: var(--user-bubble);
  color: var(--user-bubble-text);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.msg__user-icon {
  flex-shrink: 0;
  margin-top: 5px;
  opacity: 0.5;
}

.msg__user-text {
  min-width: 0;
}

.msg__actions {
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}

.msg:hover .msg__actions {
  opacity: 1;
}

.is-error {
  color: var(--danger);
}

@media (max-width: 768px) {
  .msg--user .msg__body {
    max-width: 88%;
  }
}
</style>
