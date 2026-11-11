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
        <div
            ref="sessionListEl"
            class="session-scroll"
            @scroll.passive="onSessionListScroll"
        >
          <div v-for="g in sessionGroups" :key="g.label" class="session-group">
            <div class="session-group-label">{{ g.label }}</div>
            <ul class="session-list">
              <li
                  v-for="s in g.items"
                  :key="s.id"
                  class="session-item"
                  :class="{ active: s.id === sessionId }"
                  @click="onSessionClick($event, s.id)"
                  @touchstart.passive="onItemTouchStart($event, s)"
                  @touchmove.passive="onItemTouchMove"
                  @touchend.passive="onItemTouchEnd"
                  @touchcancel.passive="onItemTouchEnd"
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
        </div>
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
          <div ref="innerEl" class="message-inner">
            <div v-if="notice" class="notice">{{ notice }}</div>
            <ChatBubble v-for="m in messages" :key="m.id" :msg="m" @preview="onPreview"/>
            <div v-if="reasoningText" class="reasoning">
              <button class="reasoning-toggle" type="button" @click="reasoningOpen = !reasoningOpen">
                思考中…
                <svg class="reasoning-arrow" :class="{ open: reasoningOpen }" viewBox="0 0 24 24"
                     width="12" height="12" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 6l6 6-6 6"/>
                </svg>
              </button>
              <div v-if="reasoningOpen" class="reasoning-body">{{ reasoningCompact }}</div>
            </div>
            <div v-if="streamingText" class="streaming-row">
              <div class="streaming-bubble">
                {{ streamingText }}<span class="cursor">▍</span>
              </div>
            </div>
            <p v-if="messages.length === 0" class="empty-hint">
              试试问：知识库里关于并发限流的笔记说了什么？
            </p>
          </div>
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
                  :class="{ on: deepThink }"
                  title="深度思考：关闭时模型直接回答；开启时先推理再回答（更慢、更费 token）"
                  @click="toggleDeepThink"
              >
                <ThinkingIcon/>
                深度思考
              </button>
              <button
                  class="tool-toggle"
                  type="button"
                  :class="{ on: webSearch }"
                  title="联网搜索：关闭时绝不联网；开启后由模型自行决定是否搜索"
                  @click="toggleWebSearch"
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
    <HtmlPreview :open="preview.open" :code="preview.code" @close="preview.open = false"/>

  </div>
  <Toast/>
</template>


<script setup lang="ts">
import {ref, computed, watch, nextTick, onMounted, onUnmounted} from 'vue'
import {fetchMessages, fetchSessions, fetchTasks, submitTask, deleteSession, renameSession} from './api/session'
import type {SessionItem} from './api/session'
import Toast from './components/Toast.vue'
import {toast} from './composables/useToast'
import {useChatStream} from './composables/useChatStream'
import {hapticTap} from './utils/haptic'
import {getClientId} from './utils/client'
import {compactReasoning} from './utils/text'
import type {ChatMessage, Citation, ServerEvent, UsageInfo} from './types/types'
import ChatBubble from './components/ChatBubble.vue'
import HtmlPreview from './components/HtmlPreview.vue'
import NewChatIcon from './components/NewChatIcon.vue'
import KbPanel from './components/KbPanel.vue'
import ThinkingIcon from './components/ThinkingIcon.vue'
import SearchIcon from './components/SearchIcon.vue'


const messages = ref<ChatMessage[]>([])
const input = ref('')
const running = ref(false)
// 本轮思考过程（reasoning_content）：流式累积，不落库，刷新后消失
const reasoningText = ref('')
const reasoningOpen = ref(true)
// 展示时才压缩连续空行，原始文本保持不动
const reasoningCompact = computed(() => compactReasoning(reasoningText.value))
// 输入框工具开关（刷新后保持）
const deepThink = ref(localStorage.getItem('tool_deep_think') === '1')
const webSearch = ref(localStorage.getItem('tool_web_search') === '1')
watch(deepThink, (v) => localStorage.setItem('tool_deep_think', v ? '1' : '0'))
watch(webSearch, (v) => localStorage.setItem('tool_web_search', v ? '1' : '0'))

function toggleDeepThink(): void {
  deepThink.value = !deepThink.value
  hapticTap()
}

function toggleWebSearch(): void {
  webSearch.value = !webSearch.value
  hapticTap()
}
const listEl = ref<HTMLElement | null>(null)
const innerEl = ref<HTMLElement | null>(null)
const streamingText = ref('')
// ★ 新增：中断提示（用 ref 而不是 push 消息——重连时幂等，不会累积）
const notice = ref('')
// ★ 知识库面板开关
const kbOpen = ref(false)
// ★ HTML 预览抽屉：哪段代码在跑。code 为空 = 从没打开过
const preview = ref<{ open: boolean; code: string }>({open: false, code: ''})

function onPreview(code: string): void {
  preview.value = {open: true, code}
}
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

/** 会话按时间分组：今天 / 昨天 / 7天内 / 30天内 / 更早按年月（2026-09） */
const sessionGroups = computed(() => {
  const now = new Date()
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(dayStart)
  yesterday.setDate(dayStart.getDate() - 1)
  const weekAgo = new Date(dayStart)
  weekAgo.setDate(dayStart.getDate() - 7)
  const monthAgo = new Date(dayStart)
  monthAgo.setDate(dayStart.getDate() - 30)

  // 后端给的是 "YYYY-MM-DD HH:mm:ss"，Safari 不认这种写法，补个 T 转 ISO
  const parse = (v: string): Date => new Date(v.includes('T') ? v : v.replace(' ', 'T'))

  // Map 保持插入顺序 —— sessions 本身已按 updated_at 倒序，分组不会乱
  const buckets = new Map<string, SessionItem[]>()
  for (const s of sessions.value) {
    const t = parse(s.updated_at)
    let label: string
    if (Number.isNaN(t.getTime())) label = '更早'
    else if (t >= dayStart) label = '今天'
    else if (t >= yesterday) label = '昨天'
    else if (t >= weekAgo) label = '7天内'
    else if (t >= monthAgo) label = '30天内'
    else label = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}`

    const arr = buckets.get(label)
    if (arr) arr.push(s)
    else buckets.set(label, [s])
  }
  return Array.from(buckets, ([label, items]) => ({label, items}))
})

const menu = ref<{ visible: boolean; x: number; y: number; session: SessionItem | null }>({
  visible: false,
  x: 0,
  y: 0,
  session: null,
})

// 菜单 DOM：渲染后量实际尺寸再做位置校正（手机上防止菜单超出屏幕）
const menuEl = ref<HTMLElement | null>(null)

// 会话列表滚动条：滚动时显现，停下 800ms 后隐藏（只控制显隐，颜色走全局变量）
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

/** 把菜单定位到某个元素旁边（三点按钮和手机长按共用） */
async function openMenuAt(anchorEl: HTMLElement, session: SessionItem): Promise<void> {
  const anchor = anchorEl.getBoundingClientRect()
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

/** 桌面端：点三点按钮开关菜单 */
async function toggleMenu(event: MouseEvent, session: SessionItem): Promise<void> {
  if (menu.value.visible && menu.value.session?.id === session.id) {
    menu.value.visible = false
    return
  }
  await openMenuAt(event.currentTarget as HTMLElement, session)
}

// ===== 手机端长按会话：弹出重命名/删除 =====
const LONG_PRESS_MS = 500      // 按住多久算长按
const LONG_PRESS_MOVE = 10     // 手指移动超过这个距离就当成在滚动，取消长按

let longPressTimer: number | undefined
let longPressOrigin = {x: 0, y: 0}
// 长按已经弹过菜单，紧随其后的 click 要吃掉，否则会顺带切换会话/关掉菜单
let longPressFired = false

function onItemTouchStart(event: TouchEvent, session: SessionItem): void {
  if (!isMobile.value) return
  const touch = event.touches[0]
  if (!touch) return
  const el = event.currentTarget as HTMLElement

  longPressOrigin = {x: touch.clientX, y: touch.clientY}
  longPressFired = false
  window.clearTimeout(longPressTimer)
  longPressTimer = window.setTimeout(() => {
    longPressFired = true
    hapticTap(30)             // 复用 utils/haptic.ts，iOS 没有 Web 触觉 API 会静默跳过
    // ★ 用三点按钮做锚点，而不是整个 li —— 点按钮时菜单贴在按钮下方，
    //   长按如果拿 li 的 rect 会跑到左边去，两处位置就对不上。
    //   按钮在手机上虽然 opacity:0，但仍在布局里，rect 有效。
    const anchorEl = el.querySelector<HTMLElement>('.more-btn') ?? el
    void openMenuAt(anchorEl, session)
  }, LONG_PRESS_MS)
}

function onItemTouchMove(event: TouchEvent): void {
  const touch = event.touches[0]
  if (!touch) return
  const dx = Math.abs(touch.clientX - longPressOrigin.x)
  const dy = Math.abs(touch.clientY - longPressOrigin.y)
  if (dx > LONG_PRESS_MOVE || dy > LONG_PRESS_MOVE) {
    window.clearTimeout(longPressTimer)   // 在滚动列表，不是长按
  }
}

function onItemTouchEnd(): void {
  window.clearTimeout(longPressTimer)
}

function onSessionClick(event: MouseEvent, id: string): void {
  if (longPressFired) {
    longPressFired = false
    // 别让它冒泡到 document —— 那里的 closeMenu 会立刻把刚弹出的菜单关掉
    event.stopPropagation()
    return
  }
  switchSession(id)
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
// 切会话时顺手关掉预览：否则右边还跑着上一个会话的代码，容易看错
watch(sessionId, () => {
  if (isMobile.value) drawerOpen.value = false
  preview.value.open = false
})


function push(kind: ChatMessage['kind'], text: string, citations?: Citation[],
              usage?: UsageInfo, reasoning?: string, reasoningSeconds?: number): void {
  messages.value.push({id: Date.now() + Math.random(), kind, text, citations, usage, reasoning, reasoningSeconds})
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
    case 'reasoning':
      reasoningText.value += msg.delta
      break
    case 'token':
      streamingText.value += msg.delta
      break
    case 'result':
      // 思考过程跟着这条回答走（渲染在气泡上方）；流式面板随即清空
      push('assistant', msg.content, pendingCitations.length ? pendingCitations : undefined,
          msg.usage, reasoningText.value || undefined,
          msg.usage?.thinking_ms
              ? Math.max(1, Math.round(msg.usage.thinking_ms / 1000))
              : undefined)
      pendingCitations = []
      reasoningText.value = ''
      streamingText.value = ''
      running.value = false
      void loadSessions()   // 标题/排序变了，刷新侧边栏
      break
    case 'error':
      push('error', msg.error)
      pendingCitations = []
      reasoningText.value = ''
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
  // 立刻清掉上一个会话的界面状态。否则在 restoreHistory 返回之前，
  // 旧会话的消息还挂在屏幕上，看起来像"切不过去"。
  messages.value = []
  streamingText.value = ''
  reasoningText.value = ''
  notice.value = ''
  pendingCitations = []
  running.value = false
  connect(sessionId.value)               // connect 内部会先断开旧连接
}

async function restoreHistory() {
  const target = sessionId.value        // 拍下本次请求对应的会话
  // 历史和任务状态一起查
  const [data, tasks] = await Promise.all([
    fetchMessages(target),
    fetchTasks(target),
  ])
  // 期间又切了会话 → 这次结果作废，否则会用旧会话的内容覆盖新会话
  if (target !== sessionId.value) return
  messages.value = data.map((m, i) => ({
    id: i,
    kind: m.role,
    text: m.content,
    reasoning: m.reasoning || undefined,
    reasoningSeconds: m.usage?.thinking_ms
        ? Math.max(1, Math.round(m.usage.thinking_ms / 1000))
        : undefined,
    usage: m.usage || undefined,
  }))
  // ★ 精确判断：有没有正在跑的任务（替换原来"最后一条是不是 user"的启发式）
  running.value = tasks.some((t) => t.status === 'running')
  // ★ 最近一条任务被中断 → 给用户一个解释（重连/切换会话时自动重算）
  const latest = tasks[0]
  streamingText.value = ''
  notice.value = latest?.status === 'interrupted' ? '上次的任务被中断了（服务重启），可以重新提问' : ''
  // messages 被整体替换、高度已变，重新贴底
  stickToBottom = true
  await nextTick()
  scrollToBottom()
}

// 前端点击发送
async function handleSend(): Promise<void> {
  const query = input.value.trim()
  if (!query || running.value || !connected.value) return
  hapticTap()                    // 提交成功才震（手机上给一次轻触反馈）
  stickToBottom = true           // 自己发的消息，一定贴底
  push('user', query)
  input.value = ''
  running.value = true
  pendingCitations = []          // ★ 新一轮开始，清掉上一轮残留的引用
  reasoningText.value = ''       // 新一轮的思考过程
  reasoningOpen.value = true
  try {
    await submitTask(query, sessionId.value, {
      deep_think: deepThink.value,
      web_search: webSearch.value,
      client_id: getClientId(),      // 只把流推给当前标签页
    })
  } catch (e) {
    running.value = false
    push('error', '任务提交失败，请检查后端服务')
  }
}

// ===== 自动滚到底 =====
// 只监听 messages.length 不够：流式输出时变长的是 streamingText，
// 而 messages 要等 result 事件才 push，条数从头到尾不变 → 打字期间一次都不会滚。
// 改为观察内容容器的实际高度，高度一变就贴底：
// 覆盖流式追加、图片加载、代码块渲染等全部情况，且每帧最多触发一次。
let stickToBottom = true            // 用户是否贴着底部
let ro: ResizeObserver | null = null

// 距底部 80px 以内算贴底；超出就当作在翻历史，不再强行拉回
function updateStick(): void {
  const el = listEl.value
  if (!el) return
  stickToBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 80
}

function scrollToBottom(): void {
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(() => {
  // 内容高度一变就贴底
  if (innerEl.value) {
    ro = new ResizeObserver(() => {
      if (stickToBottom) scrollToBottom()
    })
    ro.observe(innerEl.value)
  }
  listEl.value?.addEventListener('scroll', updateStick, {passive: true})

  // 移动端断点：768px 以下走抽屉模式
  mql = window.matchMedia('(max-width: 768px)')
  syncMobile(mql)
  mql.addEventListener('change', syncMobile)

  connect(sessionId.value)
  void loadSessions()
  document.addEventListener('click', closeMenu)      // ★ 新增
})

onUnmounted(() => {
  ro?.disconnect()                                   // 停止观察内容高度
  ro = null
  listEl.value?.removeEventListener('scroll', updateStick)
  mql?.removeEventListener('change', syncMobile)
  mql = null
  document.removeEventListener('click', closeMenu)   // ★ 不移除会泄漏，还会响应已卸载的组件
  window.clearTimeout(sessionListScrollTimer)        // 滚动条自动隐藏的计时器
  window.clearTimeout(longPressTimer)                // 长按检测的计时器
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
  background: var(--bg);
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
  color: var(--text-2);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.on {
  background: var(--success);
}

.status-dot.off {
  background: var(--text-2);
}

.session-id {
  font-family: Consolas, monospace;
}

.app-body {
  flex: 1; /* 撑满剩余高度 */
  display: flex;

  flex-direction: column;
  min-height: 0; /* 允许内部纵向压缩 */
  /* ★ 必须写：flex 子项默认 min-width:auto，会被消息里的代码块/表格
     撑出一个很大的"最小宽度"，于是拒绝收缩，把右侧 HTML 预览面板
     顶出 .app-shell 边界，被 overflow:hidden 裁掉（表现为标题栏按钮消失） */
  min-width: 0;
  width: 100%;
  overflow: hidden; /* 内容在内部自己滚，不要越界去盖住预览面板 */
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
  color: var(--text-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

@media (hover: hover) {
  .collapse-btn:hover {
    background: var(--bg-hover-strong);
    color: var(--text-1);
  }
}

.collapse-btn:active {
  background: var(--bg-hover-strong);
  color: var(--text-1);
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
  background: var(--bg-sunken);
  border-right: 0.8px solid var(--border-subtle);
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
  /* ★ 整个侧边栏的左右填充：标题、按钮、会话列表共用这一层缩进，
     滚动条会落在右侧填充区的内边缘 */
  padding: 0 12px;
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
  /* 左边不再单独留 12px（.sidebar-inner 已有填充），右边 40px 是给折叠按钮让位 */
  padding: 0 40px 10px 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-1);
  white-space: nowrap;
}

.new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 12px;
  /* 左右 margin 归零：缩进统一由 .sidebar-inner 的 padding 提供 */
  margin: 8px 0;
  border: 0.8px solid var(--border-strong);
  border-radius: 100px;
  background: var(--bg-raised);
  color: var(--text-1);
  font-size: 14px;
  cursor: pointer;

  flex-shrink: 0; /* 防止被文字压扁 */

  /* 常态：黑色微阴影 */
  box-shadow: inset 0 1px 0 var(--highlight-line),
  0 1px 2px var(--shadow-color-1);

  transition: border-color 0.2s ease,
  background-color 0.2s ease,
  box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1),
  transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.new-btn:hover {
  /* 改成黑色系阴影 */
  box-shadow: inset 0 1px 0 var(--highlight-line),
  0 4px 8px var(--shadow-color-2), /* 近距 */ 0 8px 16px var(--shadow-color-2); /* 远距 */
  transform: translateY(-1px);
}

/* 知识库入口：比"开启新会话"弱一档，避免两个主按钮抢注意力 */
.kb-btn {
  margin-top: 0;
  /* 字号收小一档做层次即可，颜色继承全局 body 的 #0f1115 */
  font-size: 13px;
}

.kb-btn-icon {
  font-size: 13px;
  line-height: 1;
}

/* 滚动容器：分组之后，滚动职责从 ul 搬到这个外层 */
.session-scroll {
  /* 顶部不留白，紧接按钮区。
     右侧 -12px：抵消 .sidebar-inner 的 padding-right，让容器铺到侧边栏边缘，
     滚动条才会落在最外侧的填充区里。
     左侧不动 —— 外层 padding-left 已经提供了缩进 */
  margin: 0 -12px 0 0;
  overflow-x: hidden;
  overflow-y: auto;
  flex: 1; /* 占满剩余空间，内容多时才滚 */
  min-height: 0; /* 允许被压扁 → overflow-y 才生效 */
  /* 滚动条只控制显隐，颜色引用全局变量 --scroll-thumb */
  scrollbar-color: transparent transparent;
}

.session-scroll.scrolling {
  scrollbar-color: var(--scroll-thumb) transparent;
}

/* 分组间隔：对齐参考稿的 Margin 16px + Padding 4px。
   之前只给了 6px，组与组之间太挤，"昨天""7天内"贴得紧 */
.session-group + .session-group {
  margin-top: 16px;
  padding-top: 4px;
}

/* 分组标题：sticky 吸顶。当前组的标题钉在顶部，
   下一组标题滚上来会把它顶走（纯 CSS，不需要 JS 监听滚动位置） */
.session-group-label {
  position: sticky;
  top: 0;
  z-index: 1;
  /* 对齐参考稿：12px 字 / 18px 行高 / 上下 2px padding = 22px 高 */
  padding: 2px 10px;
  font-size: 12px;
  line-height: 18px;
  font-weight: 500;
  color: var(--text-group);
  /* 背景必须不透明，否则下面的会话条目会从标题底下透出来 */
  background: var(--bg-sunken);
  user-select: none;
}

/* 分组内的条目列表：只负责排布，不再承担滚动 */
.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* ★ 替换 .session-item：从"整行省略号"改成 flex 两端布局 */
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  /* 复刻参考稿的 40px：padding 9 上下 + 行高 22 = 40。
     不是"18 行高 + 11 padding"——那样文字块占比小，看着反而空 */
  padding: 9px 6px 9px 10px;
  border-radius: 8px;
  font-size: 14px;
  /* 行高 22px：和 9px 上下 padding 配起来正好 40px 高（对齐参考稿） */
  line-height: 22px;
  /* 文字色不单独指定，继承全局 body 的 #0f1115 */
  cursor: pointer;
  /* 手机长按用来自定义菜单，要压掉系统默认的"选中文字 / 弹上下文菜单" */
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  transition: background-color 0.15s ease, color 0.15s ease;
}

/* 只有真正支持悬停的设备（鼠标）才用 hover 变色。
   手机上 :hover 会在点击后"粘住"，造成点完整行一直是灰底 */
@media (hover: hover) {
  .session-item:hover {
    /* 原 #f3f4f6 太浅，鼠标移上去几乎看不出高亮 */
    background: var(--bg-hover-strong);
    border-radius: 13px;
  }
}

/* 触摸/鼠标按下时的即时反馈，替代浏览器默认的 tap highlight */
.session-item:active {
  background: var(--bg-active);
  border-radius: 13px;
}

.session-item.active {
  background: var(--accent-wash-active);
  /* 选中项：蓝字 + 浅蓝底 */
  color: var(--accent-brand);
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
  /* 按钮 28×28 保证点得到，但行高只有 22，直接放会把整条撑到 46px。
     上下各 -3px 的负 margin 让它只占 22px 的交叉轴空间，
     会话项仍是 40px，按钮本身该多大还是多大 */
  width: 28px;
  height: 28px;
  margin: -3px 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}

/* 三点图标给定尺寸，不靠 100% 撑满 —— 之前没设，缩到 16px 按钮里
   被 flex 压成 0，三个点直接消失了 */
.more-icon {
  width: 16px;
  height: 16px;
  display: block;
  flex-shrink: 0;
}

/* 只有支持悬停的设备才"平时隐身、悬停出现"。
   触摸设备没有 hover，若照搬会导致三点按钮永远不可见 → 手机上无法重命名/删除 */
@media (hover: hover) {
  .session-item:hover .more-btn {
    opacity: 1;
  }
}

/* 触摸设备：未选中时完全隐藏，只在当前会话上显示（下方 .active 规则会盖成 1）。
   ★ 代价：手机上要先点一下把会话选中，才能看到并操作三点按钮 */
@media (hover: none) {
  .more-btn {
    opacity: 0;
  }
}

.session-item.active .more-btn {
  opacity: 1;
}

.more-btn:active {
  background: var(--bg-active);
  color: var(--accent-ink);
}

@media (hover: hover) {
  .more-btn:hover {
    background: var(--bg-active);
    color: var(--accent-ink);
  }
}

/* ★ 新增：悬浮菜单 */
.context-menu {
  position: fixed;
  min-width: 120px;
  padding: 4px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 24px var(--shadow-color-2);
  z-index: 1000;
}

.menu-item {
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-1);
  cursor: pointer;
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-item.danger {
  color: var(--danger);
}

.menu-item.danger:hover {
  background: var(--danger-wash-weak);
}

.menu-item.disabled {
  color: var(--text-disabled);
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
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0; /* ★ */
  /* 居中交给内层容器：滚动容器保持全宽，滚动条才会贴窗口右侧 */
}

/* 内容列：800px 居中（margin auto，不依赖 calc，折叠动画/缩放时都稳） */
.message-inner {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notice {
  margin: 0 20px 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--warning-wash);
  color: var(--warning-text);
  font-size: 13px;
}


.empty-hint {
  margin: auto;
  color: var(--text-2);
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
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
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
  color: var(--text-1);
  outline: none;
  background: transparent;
  box-sizing: border-box;
  resize: none; /* 卡片布局下不给手动拖拽，高度由 rows + max-height 控制 */
  overflow-y: auto;
}

.chat-input::placeholder {
  color: var(--text-2);
}

.chat-input:disabled {
  background: var(--bg-sunken);
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
  border: 1px solid var(--border);
  border-radius: 100px;
  background: var(--bg-raised);
  color: var(--text-1);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  /* 移动端：跳过双击缩放检测 → click 立即触发，避免"松手后延迟变色" */
  touch-action: manipulation;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

/* 图标跟着文字色走（currentColor），尺寸压到 13px 与 12px 文字更协调。
   子组件内部的 svg 带的是自己的 scope id，必须用 :deep() 才能选中 */
.tool-toggle :deep(svg) {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

/* 只有真鼠标才应用 hover（触摸设备点一下会把 hover"粘住"，导致和选中色叠成多次变色） */
@media (hover: hover) and (pointer: fine) {
  .tool-toggle:hover:not(:disabled) {
    background: var(--bg-hover);
  }

  /* 选中的开关 hover 时保持蓝色（上面的灰白 hover 特异性更高，会盖掉 .on） */
  .tool-toggle.on:hover:not(:disabled) {
    background: var(--accent-wash-strong);
  }
}

.tool-toggle:active:not(:disabled) {
  background: var(--bg-hover);
}

/* 选中态按下去也保持蓝色（同理：提高特异性避免被覆盖） */
.tool-toggle.on:active:not(:disabled) {
  background: var(--accent-border);
  border-color: var(--accent-border-strong);
  color: var(--accent-brand);
}

/* 触摸设备：按下不改背景（否则会和状态色叠成多次变色），只保留 scale 反馈 */
@media (hover: none) {
  .tool-toggle:active:not(:disabled) {
    background: var(--bg-raised);
  }

  .tool-toggle.on:active:not(:disabled) {
    background: var(--accent-wash);
  }
}

/* 禁用态用颜色变浅而不是整体 opacity：SVG 描边能均匀变灰，不会糊成一团 */
.tool-toggle:disabled {
  color: var(--text-disabled);
  border-color: var(--border-subtle);
  background: var(--bg-raised);
  cursor: not-allowed;
}

/* 激活态：底色与用户气泡（.bubble-user）统一为 --accent-wash */
.tool-toggle.on {
  background: var(--accent-wash);
  border-color: var(--accent-border);
  color: var(--accent-brand);
}

.send-btn {
  flex-shrink: 0;
  padding: 7px 18px;
  border: none;
  border-radius: 11px;
  background: var(--accent);
  color: var(--on-accent);
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
  background: var(--accent-border);
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
  color: var(--accent-ink);
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
  color: var(--text-1);
  cursor: pointer;
  transition: background 0.15s;
}

@media (hover: hover) {
  .hamburger:hover {
    background: var(--bg-hover);
  }
}

.hamburger:active {
  background: var(--bg-active);
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
  background: var(--mask);
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
    box-shadow: 2px 0 16px var(--shadow-color-2);
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

  /* 手机端：滚动容器仍撑到最右（继承桌面的 -12px），overlay 滚动条才会落在
     最外侧的填充区里；但条目自己收回 12px，否则选中态的蓝底会顶出
     侧边栏边界、盖到遮罩上 */
  .session-item {
    margin-right: 12px;
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
    background: var(--bg);
  }

  .message-inner {
    padding: 12px;
  }

  .message-list {
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