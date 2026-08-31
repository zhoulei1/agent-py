import { nextTick, onMounted, ref, type Ref } from 'vue'

/** 距底部多少像素以内算作「贴底」 */
const STICK_THRESHOLD = 80

/**
 * 消息区自动滚动。
 *
 * 只在用户本来就贴着底部时才自动滚到最新 —— 用户往上翻看历史时不会被流式输出打断。
 */
export function useAutoScroll(target: Ref<HTMLElement | null>) {
  const stickToBottom = ref(true)

  function isNearBottom(el: HTMLElement): boolean {
    return el.scrollHeight - el.scrollTop - el.clientHeight <= STICK_THRESHOLD
  }

  function onScroll() {
    const el = target.value
    if (el) stickToBottom.value = isNearBottom(el)
  }

  /** 滚到底部；force = true 时忽略「用户已上滑」状态（如切换会话、用户刚发消息） */
  async function scrollToBottom(force = false) {
    if (!force && !stickToBottom.value) return
    await nextTick()
    const el = target.value
    if (!el) return
    el.scrollTop = el.scrollHeight
    stickToBottom.value = true
  }

  onMounted(() => scrollToBottom(true))

  return { stickToBottom, onScroll, scrollToBottom }
}
