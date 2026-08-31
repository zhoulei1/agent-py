<script setup lang="ts">
import { ArrowUpOutline, StopOutline } from '@vicons/ionicons5'
import { NButton, NIcon, NInput } from 'naive-ui'
import { computed, ref } from 'vue'

const props = defineProps<{
  disabled?: boolean
  streaming?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const text = ref('')

const canSend = computed(() => !props.streaming && !props.disabled && text.value.trim().length > 0)

function submit() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
}

/** Enter 发送，Shift+Enter 换行 —— 与原 chat.html 行为一致 */
function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return
  e.preventDefault()
  submit()
}
</script>

<template>
  <div class="input-area">
    <div class="input-wrap">
      <n-input
        v-model:value="text"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 8 }"
        :maxlength="50000"
        placeholder="给 AI 助手发送消息…"
        :disabled="props.disabled"
        class="input-area__textarea"
        @keydown="onKeydown"
      />

      <div class="input-area__toolbar">
        <n-button
          v-if="props.streaming"
          circle
          type="error"
          title="停止生成"
          @click="emit('stop')"
        >
          <template #icon>
            <n-icon :component="StopOutline" />
          </template>
        </n-button>
        <n-button
          v-else
          circle
          type="primary"
          :disabled="!canSend"
          title="发送 (Enter)"
          @click="submit"
        >
          <template #icon>
            <n-icon :component="ArrowUpOutline" />
          </template>
        </n-button>
      </div>
    </div>

    <p class="input-area__hint">Enter 发送 · Shift + Enter 换行 · AI 生成内容仅供参考</p>
  </div>
</template>

<style scoped>
.input-area {
  flex-shrink: 0;
  padding: 8px 24px 16px;
}

.input-wrap {
  max-width: var(--content-width);
  margin: 0 auto;
  padding: 10px 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  background: var(--input-bg);
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.input-wrap:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

/* 去掉 Naive UI textarea 自带的边框/底色，让整块容器成为视觉输入框 */
.input-area__textarea :deep(.n-input__border),
.input-area__textarea :deep(.n-input__state-border) {
  display: none;
}

.input-area__textarea :deep(.n-input-wrapper) {
  padding: 0;
}

.input-area__textarea :deep(.n-input__textarea-el) {
  background: transparent;
  font-size: 15px;
  line-height: 1.6;
}

.input-area__toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

.input-area__hint {
  max-width: var(--content-width);
  margin: 8px auto 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 768px) {
  .input-area {
    padding: 8px 12px 12px;
  }

  .input-area__hint {
    display: none;
  }
}
</style>
