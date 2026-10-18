<template>
  <div class="app-shell">

    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sider-title">
        <span>MultiAgent-Search</span>
        <button
            class="collapse-btn"
            type="button"
            :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <ViewBoxIcon/>
        </button>
      </div>

      <button class="new-btn" @click="createSession">
        <NewChatIcon/>
        开启新会话
      </button>
      <ul class="session-list">
        <li
            v-for="s in sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === sessionId }"
            @click="switchSession(s.id)"
        >
          <span class="session-title">{{ s.title || '新会话' }}</span>
          <button
              class="more-btn"
              type="button"
              aria-label="更多操作"
              aria-haspopup="menu"
              :aria-expanded="menu.visible && menu.session?.id === s.id"
              @click.stop="toggleMenu($event, s)"
          >
            <svg class="more-icon" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="5" cy="12" r="2"/>
              <circle cx="12" cy="12" r="2"/>
              <circle cx="19" cy="12" r="2"/>
            </svg>
          </button>
        </li>
      </ul>
      <Teleport to="body">
        <div
            v-if="menu.visible"
            class="context-menu"
            role="menu"
            :style="{ left: menu.x + 'px', top: menu.y + 'px' }"
            @click.stop
            @contextmenu.prevent
        >
          <div class="menu-item" role="menuitem" @click="onRename">重命名</div>
          <div class="menu-item danger" role="menuitem" @click="onDelete">删除</div>
        </div>
      </Teleport>
    </aside>

    <div class="app-body">
      <header class="app-header">
        <div class="session-title">{{ sessions.find((s) => s.id === sessionId)?.title || '新会话' }}</div>
        <div class="header-meta">
          <span class="status-dot" :class="connected ? 'on' : 'off'"></span>
          <span>{{ connected ? '已连接' : '未连接' }}</span>
          <span class="session-id">#{{ sessionId }}</span>
        </div>
      </header>
      <div class="chat-app">
        <main ref="listEl" class="message-list">
          <div v-if="notice" class="notice">{{ notice }}</div>
          <ChatBubble v-for="m in messages" :key="m.id" :msg="m"/>
          <div v-if="streamingText" class="streaming-row">
            <div class="streaming-bubble">
              {{ streamingText }}<span class="cursor">▍</span>
            </div>
          </div>
          <p v-if="messages.length === 0" class="empty-hint">
            试试问：北京现在的天气如何？
          </p>
        </main>

        <form class="input-bar" @submit.prevent="handleSend">
          <textarea
              v-model="input"
              class="chat-input"
              placeholder="给multiagent-agent发送消息"
              :disabled="!connected"
              rows="4"
              @keydown.enter.prevent="handleSend"
          ></textarea>

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
    <PromptDialog
        :open="renameDialog.open"
        title="重命名会话"
        :initial="renameDialog.session?.title || ''"
        confirm-text="保存"
        @confirm="onRenameConfirm"
        @cancel="renameDialog.open = false"
    />
    <ConfirmDialog
        :open="deleteDialog.open"
        title="删除会话"
        :message="`「${deleteDialog.session?.title || '新会话'}」的聊天记录会一并清空，且不可恢复。`"
        confirm-text="删除"
        danger
        @confirm="onDeleteConfirm"
        @cancel="deleteDialog.open = false"
    />

  </div>
</template>


<script setup lang="ts">
import {ref, watch, nextTick, onMounted, onUnmounted, onBeforeUnmount} from 'vue'
import {fetchMessages, fetchSessions, fetchTasks, submitTask, deleteSession, renameSession} from './api'
import type {SessionItem, TaskItem} from './api'
import type {ChatMessage, ServerEvent} from './types/types'
import ChatBubble from './components/ChatBubble.vue'
import NewChatIcon from './components/NewChatIcon.vue'


const messages = ref<ChatMessage[]>([])
const input = ref('')
const connected = ref(false)
const running = ref(false)
const listEl = ref<HTMLElement | null>(null)
const streamingText = ref('')
let es: EventSource | null = null
// ★ 新增：中断提示（用 ref 而不是 push 消息——重连时幂等，不会累积）
const notice = ref('')

// ★ 当前会话 id 改成响应式：切换会话 = 改它 + 重连
const sessionId = ref<string>(
    localStorage.getItem('session_id') ?? crypto.randomUUID().slice(0, 8),
)
// ★ 值一变就同步到 localStorage，刷新后回到同一会话
watch(sessionId, (id) => localStorage.setItem('session_id', id), {immediate: true})

// ★ 侧边栏的会话列表
const sessions = ref<SessionItem[]>([])

const menu = ref<{ visible: boolean; x: number; y: number; session: SessionItem | null }>({
  visible: false,
  x: 0,
  y: 0,
  session: null,
})


function closeMenu(): void {
  menu.value.visible = false
}

import ConfirmDialog from './components/ConfirmDialog.vue'
import PromptDialog from './components/PromptDialog.vue'

// 弹窗状态
const renameDialog = ref<{ open: boolean; session: SessionItem | null }>({open: false, session: null})
const deleteDialog = ref<{ open: boolean; session: SessionItem | null }>({open: false, session: null})

function toggleMenu(event: MouseEvent, session: SessionItem): void {
  if (menu.value.visible && menu.value.session?.id === session.id) {
    menu.value.visible = false
    return
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menu.value = {                                   // ★ ref 整体替换，响应式保持
    visible: true,
    x: rect.left,
    y: Math.min(rect.bottom + 4, window.innerHeight - 90),
    session: session,
  }
}


function onRename(): void {
  const s = menu.value.session
  menu.value.visible = false
  if (!s) return
  renameDialog.value = {open: true, session: s}
}

async function onRenameConfirm(title: string): Promise<void> {
  const s = renameDialog.value.session
  renameDialog.value.open = false
  if (!s) return
  try {
    await renameSession(s.id, title)
  } catch (e) {
    console.error('重命名失败', e)
    return
  }
  sessions.value = sessions.value.map((x) => (x.id === s.id ? {...x, title} : x))
}

function onDelete(): void {
  const s = menu.value.session
  menu.value.visible = false
  if (!s) return
  deleteDialog.value = {open: true, session: s}
}

async function onDeleteConfirm(): Promise<void> {
  const s = deleteDialog.value.session
  deleteDialog.value.open = false
  if (!s) return
  try {
    await deleteSession(s.id)
  } catch (e) {
    console.error('删除会话失败', e)
    return
  }
  sessions.value = sessions.value.filter((x) => x.id !== s.id)
  if (s.id === sessionId.value) {
    const next = sessions.value[0]
    if (next) switchSession(next.id)
    else createSession()
  }
}


import ViewBoxIcon from './components/ViewBoxIcon.vue'

// 侧边栏折叠状态（读 localStorage，刷新后保持）
const sidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === '1')
watch(sidebarCollapsed, (v) => localStorage.setItem('sidebar_collapsed', v ? '1' : '0'))


function push(kind: ChatMessage['kind'], text: string): void {
  messages.value.push({id: Date.now(), kind, text})
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
  // 当前会话就是空的、且已经存在于列表 → 不重复创建
  if (messages.value.length === 0 && sessions.value.some((s) => s.id === sessionId.value)) return
  const id = crypto.randomUUID().slice(0, 8)
  sessions.value.unshift({id, title: '', updated_at: ''})
  switchSession(id)
}

// ★ 切换会话：关旧连接 → 换 id → 重连（onopen 里会自动拉新会话的历史）
function switchSession(id: string): void {
  if (id === sessionId.value) return
  es?.close()
  sessionId.value = id
  connect()
}

function connect() {
  // 相对路径走 vite 代理（不再硬编码 ws://127.0.0.1:8001）
  es = new EventSource(`/api/events/${sessionId.value}`)
  // 每次（重）连成功都会触发 open —— 历史对齐逻辑原样保留
  es.onopen = async () => {
    connected.value = true
    try {
      await restoreHistory()
    } catch (e) {
      console.error('恢复历史失败', e)
    }
  }
  es.onmessage = (event: MessageEvent<string>) => {
    handleEvent(JSON.parse(event.data) as ServerEvent)
  }
  es.onerror = () => {
    // 不写重连！浏览器按 ~3 秒间隔自动重连，成功后会再次触发 onopen
    connected.value = false
  }
}


async function restoreHistory() {
  // 历史和任务状态一起查
  const [data, tasks] = await Promise.all([
    fetchMessages(sessionId.value),
    fetchTasks(sessionId.value),
  ])
  messages.value = data.map((m, i) => ({
    id: i,
    kind: m.role,
    text: m.content,
  }))
  // ★ 精确判断：有没有正在跑的任务（替换原来"最后一条是不是 user"的启发式）
  running.value = tasks.some((t) => t.status === 'running')
  // ★ 最近一条任务被中断 → 给用户一个解释（重连/切换会话时自动重算）
  const latest = tasks[0]
  streamingText.value = ''
  notice.value = latest?.status === 'interrupted' ? '上次的任务被中断了（服务重启），可以重新提问' : ''
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
      listEl.value?.scrollTo({top: listEl.value.scrollHeight, behavior: 'auto'})
    },
)

onMounted(() => {
  connect()
  void loadSessions()
  document.addEventListener('click', closeMenu)      // ★ 新增
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)   // ★ 新增：不移除会泄漏，还会响应已卸载的组件
  es?.close()
  es = null
})

</script>


<style scoped>

.app-shell {
  display: flex;
  flex-direction: row;
  height: 100vh;
  margin: 0 auto;
  padding: 0 4px;
  overflow: hidden;
}

.app-header {
  display: flex;
  height: 52px; /* 固定高度 */
  align-items: center;
  justify-content: space-between;
  padding: 0px 16px;
  background: #fff;
  flex-shrink: 0; /* 不被压缩 */
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

.app-body {
  flex: 1; /* 撑满剩余高度 */
  display: flex;

  flex-direction: column;
  min-height: 0; /* 允许内部滚动 */
  width: 100%;
}


.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

/* 折叠按钮 */
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.collapse-btn:hover {
  background: #e9ecf1;
  color: #111827;
}

/* 折叠态：变成 48px 窄条，只留按钮 */
.sidebar {
  transition: width 0.2s ease;
}
.sidebar.collapsed {
  width: 48px;
}
.sidebar.collapsed .sider-title {
  justify-content: center;
  padding: 0 4px 10px;
}
.sidebar.collapsed .sider-title > span,
.sidebar.collapsed .new-btn,
.sidebar.collapsed .session-list {
  display: none;
}

/* ★ 新增：侧边栏 */
.sidebar {
  width: 261px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 0;
  background: rgb(249, 250, 251);
  border-right: 0.8px solid rgb(0, 0, 0, 0.04);
  min-height: 0;
}

.sider-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 0 12px 10px;      /* 按你现有间距微调 */
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  white-space: nowrap;
}
.new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 12px;
  margin: 8px 13px;
  border: 0.8px solid #d1d5db;
  border-radius: 100px;
  background: #ffffff;
  color: #0f1115;
  font-size: 14px;
  cursor: pointer;

  flex-shrink: 0; /* 防止被文字压扁 */

  /* 常态：黑色微阴影 */
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8),
  0 1px 2px rgba(0, 0, 0, 0.04);

  transition: border-color 0.2s ease,
  background-color 0.2s ease,
  box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1),
  transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.new-btn:hover {
  /* 改成黑色系阴影 */
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9),
  0 4px 8px rgba(0, 0, 0, 0.08), /* 近距 */ 0 8px 16px rgba(0, 0, 0, 0.06); /* 远距 */
  transform: translateY(-1px);
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1; /* ★ 关键：从"内容多高就多高"改成"占满剩余空间" */
  min-height: 0; /* ★ 允许被压扁 → overflow-y 才生效 */
}

/* ★ 替换 .session-item：从"整行省略号"改成 flex 两端布局 */
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  margin: 0px 13px;
  border-radius: 8px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
}

.session-item:hover {
  background: #f3f4f6;
  border-radius: 13px;
}

.session-item.active {
  background: #e4edfd;
  color: #1d4ed8;
  border-radius: 13px;
}

/* ★ 新增：标题截断（flex 子项里省略号的关键是 min-width: 0） */
.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ★ 新增：三点按钮——平时隐身，hover 该行才出现 */
.more-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}

.session-item:hover .more-btn,
.session-item.active .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background: #e5e7eb;
  color: #3b82f6;
}

/* ★ 新增：悬浮菜单 */
.context-menu {
  position: fixed;
  min-width: 120px;
  padding: 4px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  z-index: 1000;
}

.menu-item {
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
}

.menu-item:hover {
  background: #f3f4f6;
}

.menu-item.danger {
  color: #ef4444;
}

.menu-item.danger:hover {
  background: #fef2f2;
}

.menu-item.disabled {
  color: #d1d5db;
  cursor: not-allowed;
}

.menu-item.disabled:hover {
  background: transparent;
}


.chat-app {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0; /* 防止 flex 子项被长内容撑破 */
  max-width: 800px;
  min-height: 0;
  width: 100%; /* ★ 显式撑开，抵消 auto margin 的收缩 */
  margin: 0 auto; /* 水平居中（在 width:100% 的前提下仍然有效） */
}

.message-list {
  flex: 1;
  gap: 10px;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0; /* ★ */
}

.notice {
  margin: 0 20px 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fef3c7;
  color: #92400e;
  font-size: 13px;
}


.empty-hint {
  margin: auto;
  color: #9ca3af;
  font-size: 14px;
}

.input-bar {
  display: flex;
  position: relative; /* 只做定位参照 */
  margin-bottom: 20px;
}

.chat-input {
  flex: 1;
  width: 100%;
  padding: 12px 90px 12px 16px; /* 右侧留出按钮空间 */
  border: 1px solid #d1d5db;
  border-radius: 16px;
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
  "PingFang SC", "Hiragino Sans GB",
  "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  outline: none;
  background: #fff;
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;
}


.chat-input:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

.send-btn {
  position: absolute;
  right: 8px;
  bottom: 8px; /* ← 贴右下角 */
  /* 删掉 top 和 transform */
  padding: 8px 18px;
  border: none;
  border-radius: 12px;
  background: #3b82f6;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}


.send-btn:hover:not(:disabled) {
  background: #2563eb;
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
  white-space: pre-wrap; /* 保留换行，直播裸文本 */
  word-break: break-word;
}

.cursor {
  display: inline-block;
  color: #3b82f6;
  animation: blink 1s steps(1) infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

</style>