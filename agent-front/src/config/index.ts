/**
 * 运行时配置。
 *
 * 默认值即开箱可用：开发环境走 vite.config.ts 里的 `/ai` 代理，生产环境走同源相对路径。
 * 如需覆盖，在 agent-front 根目录新建 `.env.development` / `.env.production` 写入对应 `VITE_*` 变量即可。
 */

/** 后端 API 基础地址。空字符串 = 相对路径（开发走 vite proxy，生产走同源） */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

/** 聊天传输方式 */
export const CHAT_TRANSPORT: string = import.meta.env.VITE_CHAT_TRANSPORT ?? 'sse'

/** Socket.IO 服务端地址。空字符串 = 同源 */
export const SOCKET_URL: string = import.meta.env.VITE_SOCKET_URL ?? ''

/**
 * 当前登录用户 ID。
 *
 * 后端 `AIController.getLoginUserId()` 目前硬编码返回 "1"，尚无鉴权体系。
 * 这里与之对齐，保证 streamChat 落库的消息 userId 和会话列表查询条件一致
 * —— 原 chat.html 没传 userId，导致 chatMessage.userId 全是 null。
 * 接入真实登录后，改为从用户 store / token 中读取。
 */
export const CURRENT_USER_ID = '1'
