/**
 * 会话消息流（SSE）：只负责连接生命周期、消息解析和重连策略。
 *
 * 事件 → UI 的映射不在这里——通过 onEvent 单回调交回调用方，
 * 让"经常改的部分"和 App 的界面代码待在一起。
 */
import { onUnmounted, ref } from 'vue'

import { getClientId } from '../utils/client'

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
  // 连接代次：每次 connect/disconnect 递增。
  // source.close() 只能阻止"后续"事件，已经排进浏览器消息队列的那些仍会派发 ——
  // 切会话时正是它们把上一个会话的 token/result 灌进新会话。用代次在回调里丢掉。
  let generation = 0

  function disconnect(): void {
    generation++                                  // 让在途回调全部作废
    source?.close()
    source = null
    connected.value = false
  }

  function connect(sessionId: string): void {
    disconnect()                                  // 切换会话时先断开旧连接
    const gen = generation                        // 本次连接属于哪一代
    source = new EventSource(`/api/events/${sessionId}?client_id=${getClientId()}`)

    source.onopen = () => {
      if (gen !== generation) return
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
      if (gen !== generation) return              // 旧连接的残留事件：直接丢弃
      try {
        options.onEvent(JSON.parse(event.data) as ServerEvent)
      } catch (e) {
        console.error('SSE 消息解析失败', e, event.data)
      }
    }

    source.onerror = () => {
      if (gen !== generation) return
      // 不写重连：浏览器按 ~3 秒间隔自动重连，成功后再次触发 onopen
      connected.value = false
    }
  }

  onUnmounted(disconnect)

  return { connected, connect, disconnect }
}
