<script setup lang="ts">
import {
  ChatbubbleEllipsesOutline,
  CreateOutline,
  EllipsisHorizontal,
  TrashOutline,
} from '@vicons/ionicons5'
import { NDropdown, NIcon, type DropdownOption } from 'naive-ui'
import { computed, h, type Component } from 'vue'

import type { Conversation } from '@/types'

const props = defineProps<{
  item: Conversation
  active?: boolean
}>()

const emit = defineEmits<{
  select: [item: Conversation]
  rename: [item: Conversation]
  remove: [item: Conversation]
}>()

const title = computed(() => props.item.conversationName || '未命名会话')

const renderIcon = (icon: Component) => () => h(NIcon, { component: icon })

const options: DropdownOption[] = [
  { label: '重命名', key: 'rename', icon: renderIcon(CreateOutline) },
  { label: '删除', key: 'remove', icon: renderIcon(TrashOutline) },
]

function onAction(key: string) {
  if (key === 'rename') emit('rename', props.item)
  if (key === 'remove') emit('remove', props.item)
}
</script>

<template>
  <div
    class="item"
    :class="{ 'item--active': props.active }"
    :title="title"
    @click="emit('select', props.item)"
  >
    <n-icon class="item__icon" :size="15" :component="ChatbubbleEllipsesOutline" />
    <span class="item__name">{{ title }}</span>

    <n-dropdown
      trigger="click"
      placement="bottom-end"
      :options="options"
      @select="onAction"
      @click.stop
    >
      <button class="item__more" type="button" title="更多操作" @click.stop>
        <n-icon :size="16" :component="EllipsisHorizontal" />
      </button>
    </n-dropdown>
  </div>
</template>

<style scoped>
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  margin-bottom: 2px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13.5px;
  color: var(--text-secondary);
  transition:
    background 0.15s,
    color 0.15s;
  user-select: none;
}

.item:hover {
  background: var(--sidebar-hover);
  color: var(--text-primary);
}

.item--active {
  background: var(--sidebar-active);
  color: var(--text-primary);
  font-weight: 500;
}

.item__icon {
  flex-shrink: 0;
  opacity: 0.65;
}

.item__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item__more {
  flex-shrink: 0;
  display: none;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.item:hover .item__more,
.item--active .item__more {
  display: flex;
}

.item__more:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
</style>
