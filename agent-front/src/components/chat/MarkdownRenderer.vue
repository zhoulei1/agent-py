<script setup lang="ts">
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/common'
import { marked } from 'marked'
import { computed, nextTick, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    content: string
    /** 流式接收中：跳过高亮与复制按钮增强，避免每个片段都做一次昂贵的 DOM 处理 */
    streaming?: boolean
  }>(),
  { streaming: false },
)

marked.setOptions({ gfm: true, breaks: true })

const root = ref<HTMLElement | null>(null)

/**
 * Markdown → HTML，并强制净化。
 *
 * 净化是必需的：AI 回复内容不可信，原 chat.html 直接把 marked 输出塞进 innerHTML，
 * 存在 XSS 风险。这里统一走 DOMPurify。
 */
const html = computed(() => {
  if (!props.content) return ''
  try {
    const raw = marked.parse(props.content, { async: false }) as string
    return DOMPurify.sanitize(raw, { ADD_ATTR: ['target', 'rel'] })
  } catch {
    // 解析失败时退化为纯文本，至少不丢内容
    const escaped = document.createElement('div')
    escaped.textContent = props.content
    return escaped.innerHTML
  }
})

/** 给代码块加上「语言标签 + 复制按钮」外壳，并做语法高亮 */
function enhanceCodeBlocks() {
  const el = root.value
  if (!el) return

  el.querySelectorAll<HTMLPreElement>('pre').forEach((pre) => {
    if (pre.parentElement?.classList.contains('md-code-block')) return

    const code = pre.querySelector('code')
    if (!code) return

    if (!code.dataset.highlighted) {
      hljs.highlightElement(code)
      code.dataset.highlighted = 'yes'
    }

    const langClass = Array.from(code.classList).find((c) => c.startsWith('language-'))
    const lang = langClass ? langClass.replace('language-', '') : 'text'

    const wrapper = document.createElement('div')
    wrapper.className = 'md-code-block'

    const head = document.createElement('div')
    head.className = 'md-code-head'

    const label = document.createElement('span')
    label.textContent = lang

    const copyBtn = document.createElement('button')
    copyBtn.className = 'md-copy-btn'
    copyBtn.type = 'button'
    copyBtn.textContent = '复制'
    copyBtn.addEventListener('click', () => {
      void navigator.clipboard.writeText(code.textContent ?? '').then(
        () => {
          copyBtn.textContent = '已复制'
          setTimeout(() => (copyBtn.textContent = '复制'), 1500)
        },
        () => {
          copyBtn.textContent = '复制失败'
          setTimeout(() => (copyBtn.textContent = '复制'), 1500)
        },
      )
    })

    head.append(label, copyBtn)
    pre.replaceWith(wrapper)
    wrapper.append(head, pre)
  })

  // 外链安全属性
  el.querySelectorAll<HTMLAnchorElement>('a[href^="http"]').forEach((a) => {
    a.target = '_blank'
    a.rel = 'noopener noreferrer'
  })
}

watch(
  [html, () => props.streaming],
  async () => {
    if (props.streaming) return
    await nextTick()
    enhanceCodeBlocks()
  },
  { immediate: true, flush: 'post' },
)
</script>

<template>
  <div ref="root" class="markdown-body" v-html="html" />
</template>
