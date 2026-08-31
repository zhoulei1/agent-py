<script setup lang="ts">
import { NSpin } from 'naive-ui'
import { ref, watch } from 'vue'

import Conversation from '@/components/chat/Conversation.vue'
import { useAutoScroll } from '@/composables/useAutoScroll'
import type { UiMessage } from '@/types'

const props = defineProps<{
  messages: UiMessage[]
  loading?: boolean
}>()

const scroller = ref<HTMLElement | null>(null)
const { onScroll, scrollToBottom } = useAutoScroll(scroller)

// 新消息 / 流式增量都触发一次贴底滚动（用户上滑时不打断，由 composable 判断）
watch(
  () => props.messages.map((m) => m.content.length).join(','),
  () => void scrollToBottom(),
)

watch(
  () => props.messages.length,
  () => void scrollToBottom(),
)

defineExpose({ scrollToBottom })
</script>

<template>
  <div ref="scroller" class="list scroll-y" @scroll.passive="onScroll">
    <div v-if="props.loading" class="list__loading">
      <n-spin size="medium" />
    </div>

    <div v-else class="list__inner">
      <Conversation v-for="msg in props.messages" :key="msg.id" :message="msg" />
    </div>
  </div>
</template>

<style scoped>
.list {
  flex: 1;
  min-height: 0;
  padding: 24px 24px 8px;
}

.list__inner {
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.list__loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

@media (max-width: 768px) {
  .list {
    padding: 16px 14px 4px;
  }
}
</style>
