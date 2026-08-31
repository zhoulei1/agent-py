<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  dateZhCN,
  zhCN,
  type GlobalThemeOverrides,
} from 'naive-ui'
import { computed } from 'vue'

import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

/** 让 Naive UI 组件的主色与 DeepSeek 蓝保持一致 */
const themeOverrides = computed<GlobalThemeOverrides>(() => {
  const primary = themeStore.isDark ? '#7C8FFB' : '#4D6BFE'
  const primaryHover = themeStore.isDark ? '#93A3FC' : '#3F5AE8'
  return {
    common: {
      primaryColor: primary,
      primaryColorHover: primaryHover,
      primaryColorPressed: primaryHover,
      primaryColorSuppl: primaryHover,
      borderRadius: '8px',
    },
  }
})
</script>

<template>
  <n-config-provider
    :theme="themeStore.naiveTheme"
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-message-provider :max="3" placement="top">
      <n-dialog-provider>
        <RouterView />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
