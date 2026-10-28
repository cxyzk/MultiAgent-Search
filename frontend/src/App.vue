<template>
  <div class="app-shell" :class="{ 'is-mobile': isMobile }">

    <!-- 移动端抽屉遮罩：点一下收起侧边栏 -->
    <div
        v-if="isMobile && drawerOpen"
        class="drawer-mask"
        @click="onDrawerMask"
    ></div>

    <aside
        class="sidebar"
        :class="{ collapsed: sidebarCollapsed, 'drawer-open': drawerOpen }"
    >
      <!-- 内层锁死 261px：折叠动画期间只被外层裁切，子元素完全不重排 -->
      <div class="sidebar-inner">
        <div class="sider-title">
          <span>MultiAgent-Search</span>
        </div>

        <button class="new-btn" @click="createSession">
          <NewChatIcon/>
          开启新会话
        </button>
        <button class="new-btn kb-btn" type="button" @click="kbOpen = true">
          <span class="kb-btn-icon">📚</span>
          知识库
        </button>
        <ul
            ref="sessionListEl"
            class="session-list"
            @scroll.passive="onSessionListScroll"
        >
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
      </div>

      <!-- 折叠/抽屉按钮必须在内层之外：内层折叠时 opacity:0 + pointer-events:none，
           放进去就会连"展开"的入口一起失效（开关不能被开关隐藏） -->
      <button
          class="collapse-btn"
          type="button"
          :title="isMobile ? '收起菜单' : (sidebarCollapsed ? '展开侧边栏' : '收起侧边栏')"
          @click="isMobile ? (drawerOpen = false) : (sidebarCollapsed = !sidebarCollapsed)"
      >
        <ViewBoxIcon/>
      </button>

      <Teleport to="body">
        <div
            v-if="menu.visible"
            ref="menuEl"
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
        <!-- 移动端：汉堡按钮打开侧边栏抽屉 -->
        <button
            v-if="isMobile"
            class="hamburger"
            type="button"
            aria-label="打开菜单"
            @click="drawerOpen = true"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round">
            <path d="M4 7h16M4 12h16M4 17h16"/>
          </svg>
        </button>
        <div class="session-title">{{ sessions.find((s) => s.id === sessionId)?.title || '新会话' }}</div>
        <div class="header-meta">
          <span class="status-dot" :class="connected ? 'on' : 'off'"></span>
          <span>{{ connected ? '已连接' : '未连接' }}</span>
          <span v-if="!isMobile" class="session-id">#{{ sessionId }}</span>
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
            试试问：知识库里关于并发限流的笔记说了什么？
          </p>
        </main>

        <form class="input-bar" @submit.prevent="handleSend">
          <textarea
              v-model="input"
              class="chat-input"
              placeholder="给 multiagent-agent 发送消息"
              :disabled="!connected"
              rows="2"
              @keydown.enter.exact.prevent="handleSend"
          ></textarea>

          <!-- 工具栏：左侧放各类开关，右侧放发送 -->
          <div class="input-toolbar">
            <div class="toolbar-left">
              <button
                  class="tool-toggle"
                  type="button"
                  disabled
                  title="即将支持"
              >
                <ThinkingIcon/>
                深度思考
              </button>
              <button
                  class="tool-toggle"
                  type="button"
                  disabled
                  title="即将支持"
              >
                <SearchIcon/>
                智能搜索
              </button>
            </div>

            <button
                class="send-btn"
                type="submit"
                :disabled="running || !input.trim()"
            >
              {{ running ? '思考中…' : '发送' }}
            </button>
          </div>
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
    <KbPanel :open="kbOpen" @close="kbOpen = false"/>

  </div>
  <Toast/>
</template>


<script setup lang="ts">
import {ref, watch, nextTick, onMounted, onUnmounted, onBeforeUnmount} from 'vue'
import {fetchMessages, fetchSessions, fetchTasks, submitTask, deleteSession, renameSession} from './api/session'
import type {SessionItem, TaskItem} from './api/session'
import Toast from './components/Toast.vue'
import {toast} from './composables/useToast'
import {useChatStream} from './composables/useChatStream'
import type {ChatMessage, Citation, ServerEvent, UsageInfo} from './types/types'
import ChatBubble from './components/ChatBubble.vue'
import NewChatIcon from './components/NewChatIcon.vue'
import KbPanel from './components/KbPanel.vue'
import ThinkingIcon from './components/ThinkingIcon.vue'
import SearchIcon from './components/SearchIcon.vue'


const messages = ref<ChatMessage[]>([])
const input = ref('')
const running = ref(false)
const listEl = ref<HTMLElement | null>(null)
const streamingText = ref('')
// ★ 新增：中断提示（用 ref 而不是 push 消息——重连时幂等，不会累积）
const notice = ref('')
// ★ 知识库面板开关
const kbOpen = ref(false)
// ★ 本轮累积的知识库引用，等 result 到达时挂到那条 assistant 消息上
let pendingCitations: Citation[] = []

// ★ 生成短 id（8 位）。
//   crypto.randomUUID() 只在安全上下文（HTTPS / localhost）可用；
//   手机通过 http://192.168.x.x 访问时它是 undefined，会直接抛错导致白屏。
//   这里降级到 getRandomValues，再不支持才用 Math.random。
function shortId(): string {
  const c = globalThis.crypto
  if (c?.randomUUID) return c.randomUUID().slice(0, 8)
  if (c?.getRandomValues) {
    const buf = new Uint8Array(4)
    c.getRandomValues(buf)
    return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('')
  }
  return Math.random().toString(16).slice(2, 10).padEnd(8, '0')
}

// ★ 当前会话 id 改成响应式：切换会话 = 改它 + 重连
const sessionId = ref<string>(localStorage.getItem('session_id') || shortId())
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

// 菜单 DOM：渲染后量实际尺寸再做位置校正（手机上防止菜单超出屏幕）
const menuEl = ref<HTMLElement | null>(null)

// 会话列表滚动条：滚动时显现，停下 800ms 后淡出
const sessionListEl = ref<HTMLElement | null>(null)
let sessionListScrollTimer: number | undefined

function onSessionListScroll(): void {
  const el = sessionListEl.value
  if (!el) return
  el.classList.add('scrolling')
  window.clearTimeout(sessionListScrollTimer)
  sessionListScrollTimer = window.setTimeout(() => {
    el.classList.remove('scrolling')
  }, 800)
}


function closeMenu(): void {
  menu.value.visible = false
}

import ConfirmDialog from './components/ConfirmDialog.vue'
import PromptDialog from './components/PromptDialog.vue'

// 弹窗状态
const renameDialog = ref<{ open: boolean; session: SessionItem | null }>({open: false, session: null})
const deleteDialog = ref<{ open: boolean; session: SessionItem | null }>({open: false, session: null})

async function toggleMenu(event: MouseEvent, session: SessionItem): Promise<void> {
  if (menu.value.visible && menu.value.session?.id === session.id) {
    menu.value.visible = false
    return
  }

  const anchor = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const MARGIN = 8   // 距屏幕边缘的最小安全距离

  // 先按"按钮下方左对齐"渲染，再测量实际宽高校正（菜单宽高随字体/内容变化，不能写死）
  menu.value = {
    visible: true,
    x: anchor.left,
    y: anchor.bottom + 4,
    session: session,
  }
  await nextTick()
  const menuElement = menuEl.value
  if (!menuElement) return
  const {width, height} = menuElement.getBoundingClientRect()

  // 右边界：超出就往左收
  let x = anchor.left
  if (x + width > window.innerWidth - MARGIN) {
    x = Math.max(MARGIN, window.innerWidth - width - MARGIN)
  }

  // 下方放不下：翻到按钮上方；上方也放不下：贴底边（保证整体可见）
  let y = anchor.bottom + 4
  if (y + height > window.innerHeight - MARGIN) {
    const above = anchor.top - height - 4
    y = above >= MARGIN ? above : window.innerHeight - height - MARGIN
  }

  menu.value.x = x
  menu.value.y = y
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
    toast.error('重命名失败')
    return
  }
  sessions.value = sessions.value.map((x) => (x.id === s.id ? {...x, title} : x))
  toast.success('已重命名')
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
    toast.error('删除失败')
    return
  }
  sessions.value = sessions.value.filter((x) => x.id !== s.id)
  toast.success('会话已删除')
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

// ★ 移动端：侧边栏做成抽屉。isMobile 决定是"抽屉"还是"常驻栏"的交互模型
const isMobile = ref(false)
// ★ 抽屉是否打开（仅移动端生效）
const drawerOpen = ref(false)
let mql: MediaQueryList | null = null

function syncMobile(e: { matches: boolean }): void {
  isMobile.value = e.matches
  if (!e.matches) drawerOpen.value = false   // 切回桌面端时收起抽屉，避免遮罩残留
}

function onDrawerMask(): void {
  drawerOpen.value = false
}

// 移动端选中会话后自动收起抽屉（否则挡住聊天区）
watch(sessionId, () => {
  if (isMobile.value) drawerOpen.value = false
})


function push(kind: ChatMessage['kind'], text: string, citations?: Citation[], usage?: UsageInfo): void {
  messages.value.push({id: Date.now() + Math.random(), kind, text, citations, usage})
}

// 工具名 -> 中文标签，进度日志不再直接甩英文函数名
const TOOL_LABEL: Record<string, string> = {
  kb_search: '知识库检索',
  search_agent: '联网搜索',
  weather_agent: '天气查询',
  tavily_search: 'Tavily 搜索',
  get_weather: '天气 API',
}

function labelOf(tool: string): string {
  return TOOL_LABEL[tool] ?? tool
}

// 事件 → UI 的映射留在 App（和界面一起改最方便）；连接本身在 useChatStream 里
function handleEvent(msg: ServerEvent): void {
  switch (msg.type) {
    case 'progress':
      push('step', `⚙ 第 ${msg.round} 轮 · ${msg.tools.map(labelOf).join('、')}`)
      break
    case 'tool_result':
      push('step', `✅ ${labelOf(msg.tool)} 返回`)
      break
    case 'citations':
      // 只暂存，等 result 时随最终回答一起展示；按 chunk_id 去重（多轮检索可能重复命中）
      for (const citation of msg.items) {
        if (!pendingCitations.some((item) => item.chunk_id === citation.chunk_id)) {
          pendingCitations.push(citation)
        }
      }
      break
    case 'token':
      streamingText.value += msg.delta
      break
    case 'result':
      push('assistant', msg.content, pendingCitations.length ? pendingCitations : undefined, msg.usage)
      pendingCitations = []
      streamingText.value = ''
      running.value = false
      void loadSessions()   // 标题/排序变了，刷新侧边栏
      break
    case 'error':
      push('error', msg.error)
      pendingCitations = []
      streamingText.value = ''
      running.value = false
      break
  }
}

const {connected, connect} = useChatStream({
  onOpen: restoreHistory,   // 每次（重）连成功都对齐一次历史
  onEvent: handleEvent,     // 解析后的事件原样交回来
})

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
  const id = shortId()
  sessions.value.unshift({id, title: '', updated_at: ''})
  switchSession(id)
}

// ★ 切换会话：关旧连接 → 换 id → 重连（onopen 里会自动拉新会话的历史）
function switchSession(id: string): void {
  if (id === sessionId.value) return
  sessionId.value = id
  connect(sessionId.value)               // connect 内部会先断开旧连接
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
  pendingCitations = []          // ★ 新一轮开始，清掉上一轮残留的引用
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
  // 移动端断点：768px 以下走抽屉模式
  mql = window.matchMedia('(max-width: 768px)')
  syncMobile(mql)
  mql.addEventListener('change', syncMobile)

  connect(sessionId.value)
  void loadSessions()
  document.addEventListener('click', closeMenu)      // ★ 新增
})

onUnmounted(() => {
  mql?.removeEventListener('change', syncMobile)
  mql = null
  document.removeEventListener('click', closeMenu)   // ★ 不移除会泄漏，还会响应已卸载的组件
  // SSE 连接由 useChatStream 内部的 onUnmounted 自动清理
})

</script>


<style scoped>

.app-shell {
  display: flex;
  flex-direction: row;
  /* 100vh 在移动端是"地址栏隐藏时的最大高度"，地址栏一出现就会把底部顶出屏幕。
     100dvh 跟随可视视口变化；不支持的浏览器回退到 100vh。 */
  height: 100vh;
  height: 100dvh;
  margin: 0 auto;
  padding: 0 4px;
  overflow: hidden;
  /* iOS 键盘弹起时 visualViewport 会缩小，用 svh 下限兜底避免整块被推到屏幕外 */
  min-height: -webkit-fill-available;
}

.app-header {
  display: flex;
  height: 52px; /* 固定高度 */
  align-items: center;
  justify-content: space-between;
  padding: 0px 16px;
  background: #fff;
  flex-shrink: 0; /* 不被压缩 */
  width: 100%;
  max-width: 800px;
  margin: 0 auto; /* 与消息列同宽居中 */
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

@media (hover: hover) {
  .collapse-btn:hover {
    background: #e9ecf1;
    color: #111827;
  }
}

.collapse-btn:active {
  background: #e9ecf1;
  color: #111827;
}

/* 侧边栏：完整态 */
.sidebar {
  --sb-w: 261px;
  position: relative; /* 折叠按钮绝对定位的参照 */
  width: var(--sb-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 14px 0;
  background: rgb(249, 250, 251);
  border-right: 0.8px solid rgb(0, 0, 0, 0.04);
  min-height: 0;
  overflow: hidden; /* 折叠时裁掉内层，而不是让内容重排 */
  transition: width 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 折叠态：变成 48px 窄条，只留按钮 */
.sidebar.collapsed {
  width: 48px;
}

/* 内层锁死 261px：外层怎么缩，子元素的计算宽度都不变
   → 标题的 text-overflow 省略号位置全程固定，不会逐帧跳动 */
.sidebar-inner {
  width: var(--sb-w);
  /* ★ 必须撑满 .sidebar 的高度：否则高度=内容高度，
     session-list 的 flex:1 无处可分配，会话一多就撑高 inner 被 overflow:hidden 裁掉 */
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: opacity 0.12s ease;
}

/* 折叠时淡出而非 display:none 硬切；pointer-events 保证折叠态点不到 */
.sidebar.collapsed .sidebar-inner {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.08s ease;
}

/* 折叠按钮常驻：放在内层之外，任何状态都点得到（开关不能被开关隐藏） */
.sidebar .collapse-btn {
  position: absolute;
  top: 14px;
  right: 12px;
  z-index: 2;
}

.sidebar.collapsed .collapse-btn {
  right: 50%;
  transform: translateX(50%);
}

.sider-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  /* 右侧留出折叠按钮的绝对定位空间，避免标题被压到按钮底下 */
  padding: 0 40px 10px 12px;
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

/* 知识库入口：比"开启新会话"弱一档，避免两个主按钮抢注意力 */
.kb-btn {
  margin-top: 0;
  color: #374151;
  font-size: 13px;
}

.kb-btn-icon {
  font-size: 13px;
  line-height: 1;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-x: hidden; /* ← 加这行：禁止横向滚动 */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1; /* ★ 关键：从"内容多高就多高"改成"占满剩余空间" */
  min-height: 0; /* ★ 允许被压扁 → overflow-y 才生效 */

  /* 滚动条"用时出现、不用时消失"：宽度沿用全局（不跳），滑块平时透明 */
  scrollbar-width: thin;
  scrollbar-color: transparent transparent;
}

.session-list.scrolling {
  scrollbar-color: rgba(100, 116, 139, 0.5) transparent;
}

/* WebKit：滑块平时透明，滚动 / 悬停时显现 */
.session-list::-webkit-scrollbar-thumb {
  background-color: transparent;
  border-radius: 999px;
  border: 3px solid transparent;
  background-clip: padding-box;
  transition: background-color 0.25s ease;
}

.session-list.scrolling::-webkit-scrollbar-thumb,
.session-list:hover::-webkit-scrollbar-thumb {
  background-color: rgba(100, 116, 139, 0.5);
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
  transition: background-color 0.15s ease, color 0.15s ease;
}

/* 只有真正支持悬停的设备（鼠标）才用 hover 变色。
   手机上 :hover 会在点击后"粘住"，造成点完整行一直是灰底 */
@media (hover: hover) {
  .session-item:hover {
    background: #f3f4f6;
    border-radius: 13px;
  }
}

/* 触摸/鼠标按下时的即时反馈，替代浏览器默认的 tap highlight */
.session-item:active {
  background: #e5e7eb;
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

/* 只有支持悬停的设备才"平时隐身、悬停出现"。
   触摸设备没有 hover，若照搬会导致三点按钮永远不可见 → 手机上无法重命名/删除 */
@media (hover: hover) {
  .session-item:hover .more-btn {
    opacity: 1;
  }
}

/* 触摸设备：三点按钮常驻（降低存在感即可，不能藏） */
@media (hover: none) {
  .more-btn {
    opacity: 0.55;
  }
}

.session-item.active .more-btn {
  opacity: 1;
}

.more-btn:active {
  background: #e5e7eb;
  color: #3b82f6;
}

@media (hover: hover) {
  .more-btn:hover {
    background: #e5e7eb;
    color: #3b82f6;
  }
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
  /* 摊平：元素本身不生成盒子，header / message-list / input-bar 直接参与
     .app-body 的 flex 布局——滚动条因此挂在 app-body 右边缘（窗口最右），
     而不是贴在 800px 内容列的右边 */
  display: contents;
}

.message-list {
  flex: 1;
  gap: 10px;
  overflow-y: auto;
  /* 宽屏时左右 padding 跟上居中列（800px），内容仍居中；
     窄屏回落到 16px。滚动条在容器右边缘 = 窗口最右 */
  padding: 16px max(16px, calc((100% - 800px) / 2 + 16px));
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

/* 输入区外框：边框、圆角、聚焦高亮都集中在这里，内部元素一律无边框 */
.input-bar {
  display: flex;
  flex-direction: column;
  /* 与居中列对齐：宽 800-32、水平居中；手机上由媒体查询改成 margin 控制 */
  width: calc(100% - 32px);
  max-width: 768px;
  margin: 0 auto 20px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 16px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.chat-input {
  width: 100%;
  min-height: 72px;
  max-height: 200px;
  padding: 14px 16px 8px;
  border: none;
  border-radius: 16px 16px 0 0;
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
  "PingFang SC", "Hiragino Sans GB",
  "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
  color: #1f2937;
  outline: none;
  background: transparent;
  box-sizing: border-box;
  resize: none; /* 卡片布局下不给手动拖拽，高度由 rows + max-height 控制 */
  overflow-y: auto;
}

.chat-input::placeholder {
  color: #9ca3af;
}

.chat-input:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

/* 工具栏：左侧放各类开关，右侧放发送 */
.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px 8px 10px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
}

/* 预留开关按钮：现在禁用态，功能接上后去掉 disabled 即可 */
.tool-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 100px;
  background: #fff;
  color: #6b7280;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

/* 图标跟着文字色走（currentColor），尺寸压到 13px 与 12px 文字更协调。
   子组件内部的 svg 带的是自己的 scope id，必须用 :deep() 才能选中 */
.tool-toggle :deep(svg) {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

@media (hover: hover) {
  .tool-toggle:hover:not(:disabled) {
    background: #f3f4f6;
    border-color: #d1d5db;
    color: #374151;
  }
}

.tool-toggle:active:not(:disabled) {
  background: #f3f4f6;
  transform: scale(0.97);
}

/* 禁用态用颜色变浅而不是整体 opacity：SVG 描边能均匀变灰，不会糊成一团 */
.tool-toggle:disabled {
  color: #c7cbd1;
  border-color: #eceef1;
  background: #fcfcfd;
  cursor: not-allowed;
}

/* 激活态：接上真实开关后加 .on 即可 */
.tool-toggle.on {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #2563eb;
}

.send-btn {
  flex-shrink: 0;
  padding: 7px 18px;
  border: none;
  border-radius: 11px;
  background: #3b82f6;
  color: #fff;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

@media (hover: hover) {
  .send-btn:hover:not(:disabled) {
    background: #2563eb;
  }
}

.send-btn:active:not(:disabled) {
  background: #2563eb;
  transform: scale(0.97);
}

.send-btn:disabled {
  background: #bfdbfe;
  cursor: not-allowed;
}


/* 直播气泡：不能复用 ChatBubble 里的类（scoped 样式出了组件就失效），
   但观感必须和最终 assistant 气泡一致：纯文本流、无边框无阴影。
   否则打字过程是"带框卡片"、打完却突然变成无框，会有跳变 */
.streaming-row {
  display: flex;
  justify-content: flex-start;
}

.streaming-bubble {
  max-width: 100%;
  padding: 0;
  border-radius: 0;
  background: transparent;
  border: none;
  box-shadow: none;
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

/* ============================================================
   移动端适配（<=768px）
   桌面端：侧边栏常驻，可折叠成 48px 窄条
   移动端：侧边栏变成覆盖式抽屉，默认隐藏、遮罩、滑入滑出
   ============================================================ */

/* 汉堡按钮：仅移动端出现 */
.hamburger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  margin-right: 8px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #374151;
  cursor: pointer;
  transition: background 0.15s;
}

@media (hover: hover) {
  .hamburger:hover {
    background: #f3f4f6;
  }
}

.hamburger:active {
  background: #e5e7eb;
}

.hamburger svg {
  width: 20px;
  height: 20px;
}

/* 抽屉遮罩 */
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 900;
  background: rgba(17, 24, 39, 0.4);
  animation: mask-in 0.18s ease;
}

@keyframes mask-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (max-width: 768px) {
  /* 侧边栏改成覆盖式抽屉：脱离文档流，不再挤压聊天区 */
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 950; /* 高于遮罩 900 */
    width: 82vw; /* 不用固定 261px，窄屏手机也能读全标题 */
    max-width: 300px;
    transform: translateX(-100%);
    transition: transform 0.24s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 2px 0 16px rgba(0, 0, 0, 0.12);
    border-right: none;
    padding-top: 12px;
  }

  /* 抽屉打开 */
  .sidebar.drawer-open {
    transform: translateX(0);
  }

  /* 抽屉态下内层始终可见（不受 collapsed 影响），宽度自适应侧边栏 */
  .sidebar .sidebar-inner,
  .sidebar.collapsed .sidebar-inner {
    width: 100%;
    opacity: 1;
    pointer-events: auto;
    transition: none;
  }

  /* 移动端不用折叠态，宽度交给 drawer 控制 */
  .sidebar.collapsed {
    width: 82vw;
  }

  /* 收起按钮固定在抽屉右上角 */
  .sidebar .collapse-btn {
    top: 12px;
    right: 10px;
  }

  /* 移动端折叠按钮语义变成"关闭抽屉"，图标仍复用 */
  .sidebar .collapse-btn svg {
    transform: rotate(180deg);
  }

  /* 聊天区撑满全宽（侧边栏已脱离文档流） */
  .app-body {
    width: 100%;
  }

  /* .chat-app 已是 display: contents，无需再限制宽度 */
  /* ---- 移动端三段式固定布局：header 顶部、消息区滚动、输入框底部 ----
     不用 sticky/fixed 定位（会和 iOS 键盘打架），而是让 flex 容器吃满高度，
     中间的消息区独占剩余空间并自己滚动——这样 header 和输入框天然不动。 */
  .app-body {
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .app-header {
    padding: 0 12px;
    /* 刘海屏安全区：避免标题被状态栏遮住 */
    padding-top: env(safe-area-inset-top, 0px);
    height: calc(52px + env(safe-area-inset-top, 0px));
    background: #fff;
  }

  .message-list {
    padding: 12px;
    /* 关键：只有这一层滚动，且必须能被子项压缩 */
    overflow-y: auto;
    -webkit-overflow-scrolling: touch; /* iOS 惯性滚动 */
    overscroll-behavior: contain; /* 滚到底不带着整页弹 */
  }

  /* 输入框固定在底部，并避开 iPhone 底部横条 */
  .input-bar {
    width: auto; /* 手机上用左右 margin 控制宽度（覆盖宽屏的 calc） */
    margin: 0 12px;
    margin-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
    flex-shrink: 0;
  }

  /* 输入框内部的 textarea 手机上不需要太高，把空间留给消息 */
  .chat-input {
    min-height: 56px;
    max-height: 30vh;
    padding: 12px 14px 6px;
    font-size: 16px; /* 16px 以下 iOS 会自动放大页面，务必别调小 */
  }

  /* 移动端：气泡可以更宽，长代码才不会被压得很难读 */
  .streaming-bubble {
    max-width: 86%;
  }

  /* 关闭按钮足够大，方便手指点 */
  .sidebar .collapse-btn {
    width: 32px;
    height: 32px;
  }

  /* 移动端菜单项加大触摸区域（44px 左右是手指友好的下限） */
  .menu-item {
    padding: 11px 14px;
    font-size: 14px;
  }
}

/* 超窄屏（<=380px）再收一点 */
@media (max-width: 380px) {
  .sider-title {
    font-size: 14px;
  }

  .new-btn {
    font-size: 13px;
    padding: 8px 10px;
  }
}

</style>