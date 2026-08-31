/**
 * SSE 解析器测试。
 *
 * 运行：npm run test:sse
 *
 * 用例按 Spring WebFlux `ServerSentEventHttpMessageWriter` 的真实编码规则构造：
 *   sb.append(fieldName).append(':').append(fieldValue)   // 冒号后无空格
 *   text = StringUtils.replace(text, "\n", "\ndata:")     // 每个换行拆成新 data: 行
 *   结尾补 "\n\n"
 * 解析器必须是这段编码的精确逆运算。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

// 直接从 TS 源码剥离类型：本文件只有函数与常量，没有类型注解以外的 TS 语法
const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'sseParser.ts'), 'utf8')
const js = src
  .replace(/export function (\w+)\(frame: string\): string \| null/, 'function $1(frame)')
  .replace(
    /export function (\w+)\(buffer: string\): \{ frames: string\[\]; rest: string \}/,
    'function $1(buffer)',
  )
  .replace(/const dataLines: string\[\] = \[\]/, 'const dataLines = []')
  .replace(/const frames: string\[\] = \[\]/, 'const frames = []')
const { parseEventFrame, splitFrames } = await import(
  'data:text/javascript,' +
    encodeURIComponent(js + '\nexport { parseEventFrame, splitFrames };')
)

/** 模拟 Spring 的 data 编码 */
const springEncode = (text) => 'data:' + text.replaceAll('\n', '\ndata:')

test('还原 Markdown 换行（原 chat.html 会塌陷成一行）', () => {
  const markdown = '# 标题\n\n- 项目1\n- 项目2'
  assert.equal(parseEventFrame(springEncode(markdown)), markdown)
})

test('保留代码块缩进 —— 不可剥离 data: 后的前导空格', () => {
  const code = '```java\npublic class A {\n    int x = 1;\n}\n```'
  assert.equal(parseEventFrame(springEncode(code)), code)
})

test('内容前导空格原样保留', () => {
  assert.equal(parseEventFrame('data:  两个空格'), '  两个空格')
})

test('忽略注释/心跳帧', () => {
  assert.equal(parseEventFrame(':heartbeat'), null)
  assert.equal(parseEventFrame('event:ping\nid:1'), null)
})

test('兼容 CRLF', () => {
  assert.equal(parseEventFrame('data:a\r\ndata:b'), 'a\nb')
})

test('空 data 行还原为空行', () => {
  assert.equal(parseEventFrame('data:a\ndata:\ndata:b'), 'a\n\nb')
})

test('切分完整帧，残帧留在缓冲区等待后续数据', () => {
  const { frames, rest } = splitFrames('data:one\n\ndata:two\n\ndata:par')
  assert.equal(frames.length, 2)
  assert.equal(parseEventFrame(frames[0]), 'one')
  assert.equal(parseEventFrame(frames[1]), 'two')
  assert.equal(rest, 'data:par')
})

test('分片到达时跨块拼接不丢内容', () => {
  // 模拟 TCP 把一个帧切成两段先后到达
  let buffer = ''
  const out = []
  for (const chunk of ['data:hel', 'lo\n\ndata:wor', 'ld\n\n']) {
    buffer += chunk
    const { frames, rest } = splitFrames(buffer)
    buffer = rest
    frames.forEach((f) => out.push(parseEventFrame(f)))
  }
  assert.deepEqual(out, ['hello', 'world'])
})
