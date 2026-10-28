/**
 * 会话消息流（SSE）：只负责连接生命周期、消息解析和重连策略。
 *
 * 事件 → UI 的映射不在这里——通过 onEvent 单回调交回调用方，
 * 让"经常改的部分"和 App 的界面代码待在一起。
 */
import { onUnmounted, ref } from 'vue'

import type { ServerEvent } from '../types/types'

export interface ChatStreamOptions {
  /** 每次（重）连成功都会触发：调用方在这里对齐历史 */
  onOpen?: () => void | Promise<void>
  /** 每条 SSE 消息解析后原样交给调用方 */
  onEvent: (event: ServerEvent) => void
}

export function useChatStream(options: ChatStreamOptions) {
  const connected = ref(false)
  let source: EventSource | null = null

  function disconnect(): void {
    source?.close()
    source = null
    connected.value = false
  }

  function connect(sessionId: string): void {
    disconnect()                                  // 切换会话时先断开旧连接
    source = new EventSource(`/api/events/${sessionId}`)

    source.onopen = () => {
      connected.value = true
      // onOpen 可能是异步的（拉历史），失败只记日志，不影响连接
      void (async () => {
        try {
          await options.onOpen?.()
        } catch (e) {
          console.error('SSE onOpen 处理失败', e)
        }
      })()
    }

    source.onmessage = (event: MessageEvent<string>) => {
      try {
        options.onEvent(JSON.parse(event.data) as ServerEvent)
      } catch (e) {
        console.error('SSE 消息解析失败', e, event.data)
      }
    }

    source.onerror = () => {
      // 不写重连：浏览器按 ~3 秒间隔自动重连，成功后再次触发 onopen
      connected.value = false
    }
  }

  onUnmounted(disconnect)

  return { connected, connect, disconnect }
}
