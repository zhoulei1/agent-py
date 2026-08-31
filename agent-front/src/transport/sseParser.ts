/**
 * SSE 帧解析（纯函数，无外部依赖，便于单独测试）。
 */

/** 事件之间的分隔：一个空行，兼容 LF 与 CRLF */
const FRAME_SEPARATOR = /\r?\n\r?\n/

/**
 * 解析单个 SSE 事件帧，返回其 data 字段内容。
 *
 * 一帧内可以有多行 `data:`，它们用 `\n` 连接还原成原始内容。
 *
 * 这一点对本项目至关重要 —— 原 chat.html 对每行 `data:` 做 `.trim()` 后
 * 无分隔符直接拼接，导致 AI 回复里 Markdown 的换行和缩进全部丢失
 * （列表、代码块、表格渲染塌陷）。
 *
 * ## 为什么不剥离 `data:` 后的前导空格
 *
 * SSE 规范建议客户端移除 `data:` 后的一个前导空格，因为服务端**惯例**写作
 * `data: value`。但 Spring WebFlux 的 `ServerSentEventHttpMessageWriter` 并不加这个空格：
 *
 * ```java
 * sb.append(fieldName).append(':').append(fieldValue).append('\n');   // writeField：冒号后无空格
 * text = StringUtils.replace(text, "\n", "\ndata:");                  // 每个换行拆成新的 data: 行
 * ```
 *
 * 也就是说 `data:` 之后的每一个字符都是正文。若按规范剥离一个空格，
 * 4 空格缩进的代码块会变成 3 空格 —— 这已被 sseParser 的测试用例捕获。
 * 因此这里**不剥离**，使本函数成为上述编码逻辑的精确逆运算。
 *
 * @returns data 内容；帧内没有 data 字段（注释心跳、纯 event/id 帧）时返回 null
 */
export function parseEventFrame(frame: string): string | null {
  const dataLines: string[] = []

  for (const rawLine of frame.split('\n')) {
    // 去掉 CRLF 换行残留的 \r
    const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine

    // `:` 开头是注释/心跳，忽略
    if (line.startsWith(':')) continue
    if (!line.startsWith('data:')) continue

    dataLines.push(line.slice(5))
  }

  return dataLines.length > 0 ? dataLines.join('\n') : null
}

/**
 * 从流式缓冲区中切出所有**完整**的事件帧。
 *
 * @returns frames 已完整接收的帧；rest 尚未收尾、需留在缓冲区等待后续数据的部分
 */
export function splitFrames(buffer: string): { frames: string[]; rest: string } {
  const frames: string[] = []
  let rest = buffer

  for (;;) {
    const match = FRAME_SEPARATOR.exec(rest)
    if (!match) break
    const frame = rest.slice(0, match.index)
    rest = rest.slice(match.index + match[0].length)
    if (frame) frames.push(frame)
  }

  return { frames, rest }
}
