<template>
  <!-- ★ 不再 Teleport 到 body：桌面端它要做 .app-shell 的 flex 子项，
       占住右侧空间、把聊天区自然挤到左边；Teleport 出去就脱离 flex 流了。
       移动端在 CSS 里改回 position:fixed 全屏覆盖。 -->
  <transition name="pv-fade">
    <div
        v-if="open"
        class="pv-drawer"
        :class="{ dragging }"
        :style="{ '--pv-w': width + 'px' }"
    >
      <!-- 左边缘拖拽条：贴着边缘 1px 的细线鼠标抓不住，所以做到 8px -->
      <div class="pv-resizer" @pointerdown="onResizeStart"></div>

      <header class="pv-head">
        <span class="pv-title">HTML 预览</span>
        <div class="pv-actions">
          <button type="button" class="pv-btn" title="重新运行" @click="reload">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 1 1-2.64-6.36"/>
              <path d="M21 3v6h-6"/>
            </svg>
          </button>
          <button type="button" class="pv-btn" title="新窗口打开" @click="openInNewTab">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 4h6v6"/>
              <path d="M20 4l-9 9"/>
              <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>
            </svg>
          </button>
          <button type="button" class="pv-btn" title="关闭（Esc）" @click="emit('close')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round">
              <path d="M6 6l12 12M18 6L6 18"/>
            </svg>
          </button>
        </div>
      </header>

      <!-- 关键：sandbox 只放 allow-scripts，绝不给 allow-same-origin。
           否则 agent 生成的脚本可以 parent.document / parent.localStorage，
           沙箱形同虚设 -->
      <iframe
          :key="reloadKey"
          class="pv-frame"
          :srcdoc="code"
          sandbox="allow-scripts allow-modals allow-forms allow-popups"
          referrerpolicy="no-referrer"
          title="HTML 预览"
      ></iframe>
    </div>
  </transition>
</template>

<script setup lang="ts">
import {ref, onMounted, onBeforeUnmount} from 'vue'

const props = defineProps<{ open: boolean; code: string }>()
const emit = defineEmits<{ close: [] }>()

const MIN_W = 360
const DEFAULT_W = 560
// 不落 localStorage：每次打开都是默认宽度，拖拽只在本次打开期间有效
const width = ref(DEFAULT_W)

// 拖动中：iframe 会吃掉 pointermove，必须临时禁掉它的命中
const dragging = ref(false)

/** 预览可用的最大宽度：并排布局下要给侧边栏和聊天区都留位置 */
function maxWidth(): number {
  // 侧边栏宽度是可变的（展开 261 / 折叠 48），实测取值而不是写死
  const sidebar = document.querySelector('.sidebar')
  const sidebarW = sidebar instanceof HTMLElement ? sidebar.getBoundingClientRect().width : 0
  // 聊天区至少留 380px，否则消息列被压得没法读
  return Math.max(MIN_W, window.innerWidth - sidebarW - 380)
}

/** 窗口变窄时别让抽屉宽过屏幕（分屏 / 小窗 / 手机横屏） */
function clampWidth(): void {
  const max = maxWidth()
  if (width.value > max) width.value = max
}

function onResizeStart(event: PointerEvent): void {
  event.preventDefault()
  const startX = event.clientX
  const startW = width.value
  // 拖动期间窗口和侧边栏都不会变，上限算一次就够，
  // 避免每帧 getBoundingClientRect 触发同步重排
  const max = maxWidth()
  dragging.value = true

  const onMove = (e: PointerEvent) => {
    const next = startW - (e.clientX - startX)   // 往左拖 = 变宽
    width.value = Math.min(Math.max(next, MIN_W), max)
  }
  const onUp = () => {
    dragging.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// srcdoc 赋相同值不会重载 → 换 key 强制重建 iframe
const reloadKey = ref(0)
function reload(): void {
  reloadKey.value += 1
}

/** 新窗口打开：用 blob: 造独立源，顺带天然隔离，不会碰主站 localStorage */
function openInNewTab(): void {
  const blob = new Blob([props.code], {type: 'text/html;charset=utf-8'})
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) emit('close')
}

onMounted(() => {
  clampWidth()
  window.addEventListener('resize', clampWidth)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', clampWidth)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
/* 桌面端：作为 .app-shell 的 flex 子项并排在右侧。
   聊天区（.app-body 是 flex:1）会自动收缩让位，
   里面的 header / 消息列 / 输入框都靠 max-width 自适应，不用额外改。
   ★ 不要改回 position:fixed —— 那样是浮在聊天区上面，会挡住右侧消息 */
.pv-drawer {
  /* 默认宽度。实际值由模板的 :style="{ '--pv-w': width + 'px' }" 注入，
     内联自定义属性的优先级高于这条规则，拖拽时会正常覆盖。
     写在这里有两个用处：① 给 IDE 一个可静态解析的声明，
     消除 "Cannot resolve '--pv-w' custom property" 提示；
     ② 万一内联值非法（例如 NaNpx 被浏览器丢弃），这里有兜底 */
  --pv-w: 560px;
  position: relative;
  flex: 0 0 auto;
  width: var(--pv-w);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-raised);
  border-left: 1px solid var(--border);
  /* 并排两栏，阴影比覆盖式时代轻：只要一点层次，不要"浮起来"的错觉 */
  box-shadow: -6px 0 24px var(--shadow-color-1);
  /* ★ 宽度过渡：关掉预览时面板从当前宽度收到 0，
     .app-body（flex:1）会逐帧重算 → 聊天区平滑展开，不再"啪"地弹回。
     打开时反过来，聊天区平滑收缩让位 */
  transition: width 0.26s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.18s ease;
}

.pv-resizer {
  position: absolute;
  top: 0;
  left: -4px;
  bottom: 0;
  width: 8px;
  z-index: 1;
  background: transparent;
  cursor: col-resize;
}

.pv-resizer:hover {
  background: var(--accent-grip);
}

/* ★ 拖动期间禁掉 iframe 命中，否则 pointermove 被它吃掉，拖动会卡死 */
.pv-drawer.dragging .pv-frame {
  pointer-events: none;
}

.pv-drawer.dragging {
  cursor: col-resize;
  user-select: none;
}

.pv-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 44px;
  padding: 0 10px 0 14px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-subtle);
}

.pv-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  /* 标题过长时让位给右侧按钮，而不是把按钮挤出面板 */
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pv-actions {
  display: flex;
  gap: 2px;
  /* 宽度过渡时别让按钮被压缩变形 */
  flex-shrink: 0;
}

.pv-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.pv-btn svg {
  width: 15px;
  height: 15px;
}

.pv-btn:hover {
  background: var(--bg-hover);
  color: var(--text-1);
}

.pv-frame {
  /* ★ min-height:0 必须写：flex 子项默认 min-height:auto，
     iframe 内容高时会把容器撑破，而不是出自己的滚动条 */
  flex: 1;
  min-height: 0;
  /* ★ min-width：宽度过渡收缩到 360 以下时就撑住不再缩，
     让面板"把内容推出视野"而不是把 iframe 压成窄条疯狂重排。
     溢出部分由过渡期间的 overflow:hidden 裁掉 */
  min-width: 360px;
  display: block;
  width: 100%;
  border: none;
  background: #fff;
}

/* 进场/退场：宽度从 0 展开 / 收到 0，配合 .pv-drawer 上的 width transition，
   让聊天区的伸缩是逐帧的而不是瞬间跳变。
   ★ overflow 只在过渡期间开：常驻的话会把左边缘的拖拽手柄（left:-5px）裁掉，
     平时拖不动 */
.pv-fade-enter-active,
.pv-fade-leave-active {
  overflow: hidden;
}

.pv-fade-enter-from,
.pv-fade-leave-to {
  width: 0;
  opacity: 0;
}

/* 手机：没有并排空间，改回全屏覆盖整屏 */
@media (max-width: 768px) {
  .pv-drawer {
    position: fixed;
    inset: 0;
    z-index: 800;
    width: 100%;
    border-left: none;
    box-shadow: none;
  }

  /* 手机上拖拽没有意义，隐藏手柄 */
  .pv-resizer {
    display: none;
  }

  .pv-head {
    height: calc(48px + env(safe-area-inset-top, 0px));
    padding-top: env(safe-area-inset-top, 0px);
  }

  .pv-title {
    font-size: 14px;
  }

  .pv-btn {
    width: 36px;
    height: 36px;
  }

  .pv-btn svg {
    width: 18px;
    height: 18px;
  }
}
</style>
