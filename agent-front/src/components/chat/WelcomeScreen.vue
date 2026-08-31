<script setup lang="ts">
import { SparklesOutline } from '@vicons/ionicons5'
import { NButton, NIcon } from 'naive-ui'

defineProps<{
  /** 无会话时展示「新建会话」引导按钮；已在会话内则只展示提示语 */
  showCreate?: boolean
}>()

const emit = defineEmits<{ create: [] }>()

const SUGGESTIONS = ['iPhone 16 现在多少钱？', '帮我查一下我的订单', '我要投诉物流太慢']
</script>

<template>
  <div class="welcome">
    <div class="welcome__logo">
      <n-icon :size="30" :component="SparklesOutline" />
    </div>

    <h1 class="welcome__title">有什么可以帮你的？</h1>
    <p class="welcome__subtitle">
      我是基于 LangChain4j 多 Agent 工作流的智能客服，可以解答商品咨询、查询订单和处理投诉。
    </p>

    <n-button v-if="showCreate" type="primary" size="large" @click="emit('create')">
      新建会话
    </n-button>

    <ul v-else class="welcome__tips">
      <li v-for="tip in SUGGESTIONS" :key="tip">{{ tip }}</li>
    </ul>
  </div>
</template>

<style scoped>
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  gap: 12px;
}

.welcome__logo {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
  margin-bottom: 4px;
}

.welcome__title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.welcome__subtitle {
  max-width: 440px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.welcome__tips {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.welcome__tips li {
  padding: 7px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
