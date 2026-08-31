import { darkTheme, lightTheme, type GlobalTheme } from 'naive-ui'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

export const THEME_MODE = {
  LIGHT: 'light',
  DARK: 'dark',
  SYSTEM: 'system',
} as const

export type ThemeMode = (typeof THEME_MODE)[keyof typeof THEME_MODE]

const STORAGE_KEY = 'agent-front:theme-mode'

function readStoredMode(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === THEME_MODE.LIGHT || saved === THEME_MODE.DARK || saved === THEME_MODE.SYSTEM) {
    return saved
  }
  return THEME_MODE.SYSTEM
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(readStoredMode())

  // 跟随系统偏好
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(media.matches)
  media.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

  const isDark = computed(() =>
    mode.value === THEME_MODE.SYSTEM ? systemDark.value : mode.value === THEME_MODE.DARK,
  )

  /** 传给 NConfigProvider 的主题对象 */
  const naiveTheme = computed<GlobalTheme>(() => (isDark.value ? darkTheme : lightTheme))

  function setMode(next: ThemeMode) {
    mode.value = next
  }

  /** 在亮/暗之间切换（从 system 出发时，切到当前生效色的反面） */
  function toggle() {
    mode.value = isDark.value ? THEME_MODE.LIGHT : THEME_MODE.DARK
  }

  watch(mode, (value) => localStorage.setItem(STORAGE_KEY, value))

  // 供纯 CSS 使用的开关：html[data-theme="dark"]
  watch(
    isDark,
    (value) => {
      document.documentElement.dataset.theme = value ? 'dark' : 'light'
      document.documentElement.style.colorScheme = value ? 'dark' : 'light'
    },
    { immediate: true },
  )

  return { mode, isDark, naiveTheme, setMode, toggle }
})
