<template>
  <div class="app-shell">
    <!-- ★ 新增：侧边栏 -->
    <aside class="sidebar">
      <button class="new-btn" @click="createSession">＋ 新会话</button>
      <ul class="session-list">
        <li
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === sessionId }"
          @click="switchSession(s.id)"
        >
          {{ s.title || '新会话' }}
        </li>
      </ul>
    </aside>
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
  </div>
</template>



<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { fetchMessages, fetchSessions, submitTask } from './api'
import type { SessionItem } from './api'
import type { ChatMessage, ServerEvent } from './types/types'
import ChatBubble from './components/ChatBubble.vue'

const messages = ref<ChatMessage[]>([])
const input = ref('')
const connected = ref(false)
const running = ref(false)
const listEl = ref<HTMLElement | null>(null)
const streamingText = ref('')
let ws: WebSocket | null = null
let manualClose = false

// ★ 当前会话 id 改成响应式：切换会话 = 改它 + 重连
const sessionId = ref<string>(
  localStorage.getItem('session_id') ?? crypto.randomUUID().slice(0, 8),
)
// ★ 值一变就同步到 localStorage，刷新后回到同一会话
watch(sessionId, (id) => localStorage.setItem('session_id', id), { immediate: true })

// ★ 侧边栏的会话列表
const sessions = ref<SessionItem[]>([])

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
      streamingText.value = ''
      running.value = false
      void loadSessions()   // ★ 标题/排序变了，刷新侧边栏
      break
    case 'error':
      push('error', msg.error)
      streamingText.value = ''
      running.value = false
      break
  }
}

// ★ 拉会话列表
async function loadSessions(): Promise<void> {
  try {
    sessions.value = await fetchSessions()
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

// ★ 新建会话：本地先插一条占位，发第一条消息后由 loadSessions 替换成真实数据
function createSession(): void {
  const id = crypto.randomUUID().slice(0, 8)
  sessions.value.unshift({ id, title: '', updated_at: '' })
  switchSession(id)
}

// ★ 切换会话：关旧连接 → 换 id → 重连（onopen 里会自动拉新会话的历史）
function switchSession(id: string): void {
  if (id === sessionId.value) return
  ws?.close()
  sessionId.value = id
  connect()
}

function connect() {
  const socket = new WebSocket(`ws://127.0.0.1:8001/api/ws/${sessionId.value}`)
  ws = socket
  socket.onopen = async () => {
    if (ws !== socket) return     // ★ 已被替换的旧连接，忽略
    connected.value = true
    try {
      await restoreHistory()
    } catch (e) {
      console.error('恢复历史失败', e)
    }
  }
  socket.onmessage = (event: MessageEvent<string>) => {
    if (ws !== socket) return
    handleEvent(JSON.parse(event.data) as ServerEvent)
  }
  socket.onclose = () => {
    if (ws !== socket) return     // ★ 关键：旧连接的关闭不触发重连、不改状态
    connected.value = false
    if (!manualClose) setTimeout(connect, 2000)
  }
  socket.onerror = () => {
    socket.close()
  }
}

async function restoreHistory() {
  const data = await fetchMessages(sessionId.value)
  messages.value = data.map((m, i) => ({
    id: i,
    kind: m.role,
    text: m.content,
  }))
  // 最后一条是 user → 说明有个任务没跑完（可能还在跑，也可能已经断了）
  running.value = data[data.length - 1]?.role === 'user'
  streamingText.value = ''
}

// 前端点击发送
async function handleSend(): Promise<void> {
  const query = input.value.trim()
  if (!query || running.value || !connected.value) return
  push('user', query)
  input.value = ''
  running.value = true
  try {
    await submitTask(query, sessionId.value)
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

onMounted(() => {
  connect()
  void loadSessions()
})
onUnmounted(() => {
  manualClose = true
  ws?.close()
  ws = null
})

</script>


<style scoped>

/* ★ 新增：两列外壳 */
.app-shell {
  display: flex;
  gap: 12px;
  height: 100vh;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 12px;
}

/* ★ 新增：侧边栏 */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 0;
}
.new-btn {
  padding: 9px 12px;
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  background: #fff;
  color: #3b82f6;
  font-size: 13px;
  cursor: pointer;
}
.new-btn:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}
.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.session-item {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;   /* 标题太长省略号截断 */
}
.session-item:hover { background: #f3f4f6; }
.session-item.active { background: #eff6ff; color: #1d4ed8; }


/* ★ 改：.chat-app 原来有 max-width: 760px; margin: 0 auto; —— 删掉这两行，换成： */
.chat-app {
  flex: 1;
  min-width: 0;        /* 防止 flex 子项被长内容撑破 */
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