<template>
  <div class="chat-app">
    <header class="chat-header">
      <h1 class="app-title">MultiAgent-Search</h1>
      <div class="header-meta">
        <span class="status-dot" :class="connected ? 'on' : 'off'"></span>
        <span>{{ connected ? '已连接' : '未连接' }}</span>
        <span class="session-id">#{{ sessionId }}</span>
      </div>
    </header>

    <main ref="listEl" class="message-list">
      <ChatBubble v-for="m in messages" :key="m.id" :msg="m" />
      <!-- ↓↓↓ 直播气泡，加在这里 ↓↓↓ -->
      <div v-if="streamingText" class="streaming-row">
        <div class="streaming-bubble">
          {{ streamingText }}<span class="cursor">▍</span>
        </div>
      </div>
      <!-- ↑↑↑ -->
      <p v-if="messages.length === 0" class="empty-hint">
        试试问：北京现在的天气如何？
      </p>
    </main>

    <form class="input-bar" @submit.prevent="handleSend">
      <input
        v-model="input"
        class="chat-input"
        type="text"
        placeholder="输入问题，回车发送…"
        :disabled="!connected"
      />
      <button
        class="send-btn"
        type="submit"
        :disabled="running || !input.trim()"
      >
        {{ running ? '思考中…' : '发送' }}
      </button>
  </form>
  </div>

</template>



<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { submitTask } from './api'
import type { ChatMessage, ServerEvent } from './types/types'
import ChatBubble from './components/ChatBubble.vue'


const sessionId = crypto.randomUUID().slice(0, 8)
const messages=ref<ChatMessage[]>([])
const input = ref('')
const connected = ref(false)
const running = ref(false)
const listEl = ref<HTMLElement | null>(null)
const streamingText = ref('')   // 直播中的文本，定稿到达即清空
let ws: WebSocket | null = null
let manualClose = false   // 标记"是我主动关的"，防止关闭页面后还触发重连

function push(kind: ChatMessage['kind'], text: string): void {
  messages.value.push({ id: Date.now(), kind, text })
}

// 后端推送 -> 前端消息的唯一入口
function handleEvent(msg: ServerEvent): void {
  switch (msg.type) {
    case 'progress':
      push('step', `⚙ 第 ${msg.round} 轮 · 调用工具 ${msg.tools.join(', ')}`)
      break
    case 'tool_result':
      push('step', `✅ ${msg.tool} 返回`)
      break
    case 'token':
      streamingText.value += msg.delta
      break
    case 'result':
      push('assistant', msg.content)
      streamingText.value = ''   // 定稿到达，直播气泡退场
      running.value = false
      break
    case 'error':
      push('error', msg.error)
      streamingText.value = ''   // 别留残影
      running.value = false
      break
  }
}



function connect() {
  ws = new WebSocket(`ws://127.0.0.1:8001/api/ws/${sessionId}`)
  ws.onopen = () => {
    connected.value = true
  }
  ws.onmessage = (event: MessageEvent<string>) => {
    handleEvent(JSON.parse(event.data) as ServerEvent)
  }
  ws.onclose = () => {
    connected.value = false
    if (!manualClose) setTimeout(connect, 2000)   // 断线重连
  }
  ws.onerror = () => {
    ws?.close()
  }
}

//前端点击发送
async function handleSend(): Promise<void> {
  const query = input.value.trim()
  if (!query || running.value || !connected.value) return
  push('user', query)
  input.value = ''
  running.value = true
  try {
    await submitTask(query, sessionId)   // 返回的 task_id 目前用不上，先接住
  } catch (e) {
    running.value = false
    push('error', '任务提交失败，请检查后端服务')
  }
}
// 新消息自动滚到底
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'auto' })
  },
)

onMounted(() => {connect()})
onUnmounted(() => {
  manualClose = true
  ws?.close()
  ws = null
})
</script>


<style scoped>
.chat-app {
  max-width: 760px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.app-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.on {
  background: #22c55e;
}
.status-dot.off {
  background: #9ca3af;
}

.session-id {
  font-family: Consolas, monospace;
}

.message-list {
  flex: 1;
  gap: 10px;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.empty-hint {
  margin: auto;
  color: #9ca3af;
  font-size: 14px;
}

.input-bar {
  margin-bottom: 20px;   /* ← 底部留白，整体上移 */
  display: flex;
  gap: 10px;
  padding: 14px 20px;
  background: #fff;
  border: 1px solid #e5e7eb;   /* 四周都加边框，圆角才好看 */
  border-radius: 16px;          /* ← 关键 */
}
.chat-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 14px;
  outline: none;
}
.chat-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgb(59 130 246 / 0.15);
}

.send-btn {
  padding: 10px 22px;
  border: none;
  border-radius: 10px;
  background: #3b82f6;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.send-btn:disabled {
  background: #bfdbfe;
  cursor: not-allowed;
}

/* 直播气泡：不能复用 ChatBubble 里的类，scoped 样式出了组件就失效 */
.streaming-row {
  display: flex;
  justify-content: flex-start;
}
.streaming-bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 14px;
  border-bottom-left-radius: 4px;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;      /* 保留换行，直播裸文本 */
  word-break: break-word;
}
.cursor {
  display: inline-block;
  color: #3b82f6;
  animation: blink 1s steps(1) infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

</style>