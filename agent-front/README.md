# agent-front

`agent-py`（智能客服 Agent 后端，Python/FastAPI）的前端工程，由原单文件页面 `chat.html` 重构而来。

**技术栈**：Vue 3（`<script setup>`）+ TypeScript + Vite + Pinia + Naive UI + Vue Router + marked/DOMPurify/highlight.js
**视觉**：参考 DeepSeek 聊天界面，支持亮/暗双主题。

## 快速开始

```bash
npm install
npm run dev        # http://localhost:5173，/ai 自动代理到后端 8080
```

后端（agent-py）需先启动（依赖 MongoDB / Redis / Qdrant）：

```bash
cd .. && uv run python main.py
```

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 开发服务器（Vite） |
| `npm run build` | 类型检查（`vue-tsc`）+ 生产构建 |
| `npm run typecheck` | 仅类型检查 |
| `npm run test:sse` | SSE 解析器单元测试 |
| `npm run preview` | 预览构建产物 |

## 目录结构

```
src/
├── api/           后端接口封装（http.ts 通用请求 / chat.ts 业务接口）
├── components/
│   ├── chat/      消息列表、消息气泡、Markdown 渲染、输入框、欢迎页、打字动画
│   └── layout/    侧边栏、会话列表项
├── composables/   useAutoScroll —— 贴底自动滚动
├── config/        运行时配置（可被 .env 的 VITE_* 覆盖）
├── router/        /chat/:conversationId? 路由（支持深链、刷新保持）
├── stores/        Pinia：chat（会话与消息）/ theme（主题）
├── transport/     聊天传输抽象层 ★
├── types/         与后端 DTO 对齐的类型
└── views/         ChatView 页面装配
```

## 业务逻辑

核心是「会话管理 + 消息流式收发」，由 `stores/chat.ts` 统一驱动：

```
加载会话列表 ──► 选中/新建会话 ──► 加载历史消息 ──► 发送消息
                                                      │
                         乐观插入用户气泡 + assistant 占位（打字动画）
                                                      │
                         走传输层发送 → onChunk 逐片段累加 → onDone 落定
                                                      │
                         后端落库后刷新会话列表（updateTime 排序生效）
```

- **会话操作**：新建（后端生成 conversationId）、重命名、删除、列表按创建时间倒序
- **流式接收**：`sendMessage` 乐观插入用户消息 → 插入 assistant 占位 → 逐片段累加 → 完成/出错落定
- **中断**：生成中可手动停止，已接收内容保留
- **路由驱动**：`/chat/:conversationId?` 深链直达会话，切换会话时丢弃过期响应

## 技术架构

### 传输层抽象（核心设计）

`stores/chat.ts` 只依赖 `ChatTransport` 接口，更换底层传输无需改动任何组件：

| 实现 | 状态 | 说明 |
| --- | --- | --- |
| `sseTransport.ts` | ✅ 默认启用 | 对接后端 `POST /ai/streamChat`（`text/event-stream`） |
| `socketIoTransport.ts` | ⚠️ 需后端配套 | 代码已就绪，但后端（agent-py）尚无 Socket.IO 服务端 |

切换方式：在项目根目录新建 `.env.development`，写入 `VITE_CHAT_TRANSPORT=socketio`。

### 其他设计点

- **Markdown 渲染**：`marked` 解析 + `DOMPurify` 防 XSS + `highlight.js` 代码高亮，含代码块复制按钮
- **SSE 解析**：`sseParser.ts` 是对后端 SSE 编码的精确逆运算（`data:` 后不加空格、多行 `data:` 按换行还原），避免列表/代码块/表格塌陷
- **主题**：`stores/theme.ts` 通过 `html[data-theme]` 切换亮/暗，CSS 变量统一管理配色
- **自动滚动**：`useAutoScroll` 只在用户贴底时才自动滚到最新，上翻历史不被流式输出打断

## 可配置项

默认值开箱可用（见 `src/config/index.ts`）。如需覆盖，新建 `.env.development` / `.env.production`：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | 空 | 空 = 相对路径（开发走 vite proxy） |
| `VITE_CHAT_TRANSPORT` | `sse` | `sse` \| `socketio` |
| `VITE_SOCKET_URL` | 空 | 空 = 同源 |

## 已知约束

- **登录**：后端 `AIController.getLoginUserId()` 硬编码返回 `"1"`，前端 `CURRENT_USER_ID` 与之对齐。接入真实鉴权后需一并调整。
- **流式**：后端当前一次性返回整段回答（非逐 token 推流）。前端已按真正的增量流实现，后端改造后无需改动前端。
- **TS 约束**：`tsconfig.app.json` 开启了 `erasableSyntaxOnly`（禁用 TS `enum`，用 `as const` 联合类型替代）与 `noUnusedLocals`/`noUnusedParameters`。
