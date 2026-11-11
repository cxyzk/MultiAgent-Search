<template>
  <div class="row" :class="'row-' + msg.kind">
    <div class="bubble-wrap">
      <!-- 思考过程：挂在这条回答上方，默认折叠 -->
      <div v-if="msg.reasoning" class="reasoning">
        <button class="reasoning-toggle" type="button" @click="reasoningOpen = !reasoningOpen">
          已思考（用时 {{ msg.reasoningSeconds || 1 }} 秒）
          <svg class="reasoning-arrow" :class="{ open: reasoningOpen }" viewBox="0 0 24 24"
               width="12" height="12" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 6l6 6-6 6"/>
          </svg>
        </button>
        <div v-if="reasoningOpen" class="reasoning-body">{{ compactReasoning(msg.reasoning) }}</div>
      </div>
      <div
          v-if="msg.kind === 'assistant'"
          class="bubble bubble-assistant markdown-body"
          v-html="renderedHtml"
          @click="onContentClick"
      ></div>
      <div v-else class="bubble" :class="'bubble-' + msg.kind">{{ msg.text }}</div>

      <!-- 用量统计：仅 assistant 最终回答带，一行灰色小字 -->
      <div v-if="msg.kind === 'assistant' && msg.usage" class="usage-line">
        {{ msg.usage.calls }} 次调用 · {{ formatTokens(msg.usage.total_tokens) }} tokens
        · LLM {{ (msg.usage.llm_latency_ms / 1000).toFixed(1) }}s
        <span v-if="msg.usage.cache_hit_tokens > 0">
          · 缓存命中 {{ formatTokens(msg.usage.cache_hit_tokens) }}
        </span>
      </div>

      <!-- 知识库引用：仅当后端推过 citations 才出现，默认折叠 -->
      <div v-if="msg.kind === 'assistant' && msg.citations?.length" class="citations">
        <button class="cite-toggle" type="button" @click="open = !open">
          <span class="cite-arrow" :class="{ open }">▸</span>
          {{ open ? '收起' : '展开' }}参考片段（{{ msg.citations.length }}）
        </button>
        <ul v-if="open" class="cite-list">
          <li v-for="c in msg.citations" :key="c.chunk_id">
            <span class="cite-title">《{{ c.title }}》</span>
            <span class="cite-score">score {{ c.score }}</span>
            <span class="cite-id">#{{ c.chunk_id }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {computed, ref} from 'vue'
import {compactReasoning} from '../utils/text'
import {Marked} from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import type {ChatMessage} from '../types/types'

const props = defineProps<{ msg: ChatMessage }>()

// 点「运行」时把源码抛给 App，由它打开预览抽屉（本组件不碰预览 UI）
const emit = defineEmits<{ preview: [code: string] }>()

// 引用列表的展开状态，每条消息独立
const open = ref(false)

// 思考过程的折叠状态（历史消息默认收起，省空间）
const reasoningOpen = ref(false)

/** 1234 → "1.2k"；不足千直接显示 */
function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

// ===== 代码块工具栏：语言标签 + 复制 =====

/** 只有纯 HTML 能直接跑；vue 单文件组件跑不了，给了按钮等于骗人 */
const RUNNABLE_LANGS = new Set(['html', 'htm', 'xhtml'])

/** 生成"工具栏 + 代码体"的 HTML（由自定义 renderer 调用） */
function buildCodeBlock(language: string, highlightedHtml: string): string {
  // 语言名来自模型输出，拼进 HTML 前只保留安全字符
  const label = (language || 'text').replace(/[^\w#+.-]/g, '') || 'text'

  // 模型常大写（```HTML），比较时统一小写
  const runButton = RUNNABLE_LANGS.has(label.toLowerCase())
      ? `<button type="button" class="code-btn code-run">`
        + `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor"`
        + ` stroke-width="2" stroke-linejoin="round"><path d="M7 4l14 8-14 8V4z"/></svg>`
        + `运行</button>`
      : ''

  return (
      `<div class="code-block">` +
      `<div class="code-toolbar">` +
      `<span class="code-lang">${label}</span>` +
      `<span class="code-actions">` +
      `<button type="button" class="code-btn code-copy">复制</button>` +
      runButton +
      `</span>` +
      `</div>` +
      `<pre><code class="hljs language-${label}">${highlightedHtml}</code></pre>` +
      `</div>`
  )
}

/** 复制到剪贴板：安全上下文用 Clipboard API，HTTP（手机局域网）降级 execCommand */
async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 落到下面的降级路径
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(textarea)
  return ok
}

/** 按钮临时反馈（"已复制"），1.5 秒后复原 */
function flashButton(button: HTMLButtonElement, text: string): void {
  const original = button.textContent ?? ''
  button.textContent = text
  button.classList.add('done')
  window.setTimeout(() => {
    button.textContent = original
    button.classList.remove('done')
  }, 1500)
}

/** v-html 渲染的按钮不在 Vue 响应式里 → 事件委托统一处理 */
async function onContentClick(event: MouseEvent): Promise<void> {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('button.code-btn')
  if (!button) return

  const block = button.closest('.code-block')
  const codeElement = block?.querySelector('pre code')
  if (!codeElement) return

  const code = codeElement.textContent ?? ''

  // ★ 先判运行：源码直接向上抛，预览面板和沙箱都在 HtmlPreview 里
  if (button.classList.contains('code-run')) {
    emit('preview', code)
    return
  }

  if (button.classList.contains('code-copy')) {
    const ok = await copyToClipboard(code)
    flashButton(button, ok ? '已复制' : '复制失败')
  }
}

// Markdown 渲染管线：自定义 code 渲染（带工具栏）-> 语法高亮 -> DOMPurify 消毒
const md = new Marked({
  renderer: {
    // marked v13+ 的签名是对象参数：{ text, lang, escaped }
    code({text, lang}) {
      const language = (lang || '').match(/\S*/)?.[0] ?? ''
      const highlighted = language && hljs.getLanguage(language)
          ? hljs.highlight(text, {language}).value
          : hljs.highlightAuto(text).value   // 模型没标语言时自动探测
      return buildCodeBlock(language, highlighted)
    },
  },
})

const renderedHtml = computed(() =>
    DOMPurify.sanitize(md.parse(props.msg.text) as string),
)
</script>


<style scoped>
/* 行：决定左对齐还是右对齐 */
.row {
  display: flex;
}

/* 气泡 + 引用块的纵向容器：不加这层，flex 行会把引用块横向摆到气泡右边 */
.bubble-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  /* assistant 占满整行（代码块/表格才不被压缩）；宽度上限只给 user 气泡用
     —— 这是 problem.md 第 12 条记过的坑，别在这里再限制一次 */
  flex: 1;
  min-width: 0;
}

.row-user .bubble-wrap {
  align-items: flex-end;
  flex: 0 1 auto;    /* user 不撑满，按内容收缩 */
  max-width: 90%;    /* 长问题尽量少换行，到 90% 才折 */
}

/* 步骤/错误是全宽日志，不受气泡宽度限制 */
.row-step .bubble-wrap,
.row-error .bubble-wrap {
  max-width: 100%;
}

.row-user {
  justify-content: flex-end;
}

.row-assistant,
.row-error {
  justify-content: flex-start;
}

.row-step {
  justify-content: flex-start;
  padding-left: 8px;
}

/* 气泡公共 */
.bubble {
  padding: 10px 14px;
  border-radius: 14px;
  /* 基准字号：user 和 assistant 共用，各自的子元素继承这里 */
  font-size: 16px;
  line-height: 1.7;
  white-space: pre-wrap; /* 保留后端回答里的换行 */
  word-break: break-word;
}

/* 用户：蓝底白字，右下角收一个小尖 */
.bubble-user {
  max-width: 100%;
  min-width: 0;
  background: var(--accent-wash);
  color: var(--text-1);
  border-bottom-right-radius: 4px;
}

/* 最终回答：纯文本流，无背景无阴影，与页面完全融合 */
.bubble-assistant {
  width: 100%;       /* 父层已是 flex:1，这里补上让短内容也占满 */
  box-sizing: border-box;
  background: transparent;
  box-shadow: none;
  border: none;
  border-radius: 0;
  /* 字号和颜色都由 .bubble / body 统一提供，这里不再重复声明 */
  /* 左右内缩：正文和代码块都从这里获得呼吸空间。
     叠加 .message-list 的 16px 后，文字距窗口左缘约 24px */
  padding-left: 8px;
  padding-right: 8px;
}

/* 工具进度：弱视觉的灰色日志字 */
.bubble-step {
  background: none;
  color: var(--text-2);
  font-size: 13px;
  font-family: Consolas, monospace;
  padding: 2px 4px;
  max-width: 100%;
}

/* 错误：浅红底 */
.bubble-error {
  background: var(--danger-wash);
  color: var(--danger-text);
  max-width: 100%;
}

.markdown-body {
  white-space: normal;
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.markdown-body :deep(a) {
  color: var(--accent-ink);
}

/* 代码块容器：纯白底 + 细灰边 + 圆角 */
/* ===== 代码块：工具栏（语言 + 复制/下载）+ 代码体 =====
   注意：这些元素是 v-html 注入的，没有 scoped 的 data-v 属性，
   必须用 :deep() 穿透，否则样式不生效 */
.markdown-body :deep(.code-block) {
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;            /* 圆角裁切工具栏与代码体 */
  background: var(--bg-inset);
}

.markdown-body :deep(.code-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 12px;
  /* 与代码块背景一致（继承 .code-block 的 #f6f8fa），保留为透明即可 */
  background: transparent;
  font-size: 12px;
  color: var(--text-2);
}

.markdown-body :deep(.code-lang) {
  font-family: Consolas, monospace;
  text-transform: lowercase;
}

.markdown-body :deep(.code-actions) {
  display: flex;
  gap: 2px;
}

.markdown-body :deep(.code-btn) {
  border: none;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  /* 按钮里有 svg，inline-flex + gap 才能和文字垂直居中 */
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

/* 运行按钮：和复制之间的分隔线。
   ★ 不能用 border-left —— border 属于按钮自己的盒模型，hover 时
   背景色铺满整个 border-box，那条线就被灰色块一起包进去了。
   改用伪元素，线画在按钮外面，不参与 hover 背景。

   ★ 间距要对称：按钮间总间隙 = .code-actions 的 gap(2px) + 这里的 margin-left(7px) = 9px。
   9 - 线宽 1 = 8，左右各 4px → 线左边缘 = 按钮左边缘 - 5px。
   总间隙如果是奇数（比如 7px）就永远分不匀，只能是 4/2。 */
.markdown-body :deep(.code-run) {
  position: relative;
  margin-left: 7px;
  /* 与其他按钮统一内边距：线在盒子外面，不需要额外左留白 */
  padding-left: 8px;
  /* 恢复全圆角：左边不再是直角 */
  border-radius: 5px;
}

.markdown-body :deep(.code-run)::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 50%;
  width: 1px;
  height: 12px;
  margin-top: -6px;
  background: var(--border);
  /* 线是装饰，别挡住按钮的点击区域 */
  pointer-events: none;
}
.markdown-body :deep(.code-btn:hover) {
  background: var(--bg-hover-inset);
  color: var(--text-1);
}
.markdown-body :deep(.code-btn.done) {
  color: var(--success-text);
}

/* 基础态（手机端）：保持横向滚动，行为不变 */
.markdown-body :deep(pre) {
  background: transparent;     /* 背景/圆角交给 .code-block（工具栏与代码体共用一块底） */
  border-radius: 0;
  margin: 0;
  padding: 0;
  overflow-x: auto;
  /* ★ 必须显式关闭纵向：overflow-x 设为 auto 时，overflow-y 的 visible 会被
     计算成 auto（CSS 规范），代码块高度差 1px 就会冒出竖滚动条 */
  overflow-y: hidden;
}

/* 桌面端：代码软换行，不再横向滚动。
   表格不受影响 —— 它走自己的 width:max-content + overflow-x 规则。
   断点与项目 isMobile 的 matchMedia('(max-width: 768px)') 严格互补，不重不漏 */
@media (min-width: 769px) {
  .markdown-body :deep(pre) {
    white-space: pre-wrap;
    /* 长 token（URL / base64 / 压缩成一行 的 JS）必须允许从任意处断开，
       否则 pre-wrap 遇到不可断词还是会顶出容器 */
    overflow-wrap: anywhere;
    word-break: break-word;    /* 老 Safari 不支持 overflow-wrap:anywhere，兜底 */
    /* 换行后不该再有任何滚动条（顺带解决 overflow-x:auto 把
       overflow-y 的 visible 算成 auto、差 1px 就冒竖条的老问题） */
    overflow: hidden;
    /* tab 默认 8 格，桌面端容器也装不下几层缩进，统一成 4 格 */
    tab-size: 4;
    -moz-tab-size: 4;
  }
}

/* 块内代码：透明底，颜色全部交给高亮主题 */
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 12px 16px;
  /* ★ 代码块字号只写在这里：字体实际由 <pre code> 控制，
     写在 <pre> 上会被它自己的 font-size 覆盖掉（之前踩过）
     手机端在 @media (max-width: 768px) 里单独覆盖成 12px */
  font-size: 13px;
  line-height: 1.6;
}

/* 行内代码：浅灰小块（保留你原来的） */
.markdown-body :deep(code) {
  background: var(--bg-hover);
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: Consolas, monospace;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  /* 按内容撑开列宽（不被压扁），超出气泡宽度时才横向滚动 */
  display: block;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  white-space: nowrap;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 4px 10px;
}


/* ===== 知识库引用 ===== */
.citations {
  margin-top: 6px;
  width: 100%;
}

.cite-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.cite-toggle:hover {
  background: var(--bg-hover);
  color: var(--accent-brand);
}

.cite-arrow {
  display: inline-block;
  font-size: 10px;
  transition: transform 0.15s;
}

.cite-arrow.open {
  transform: rotate(90deg);
}

.cite-list {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
}

.cite-list li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 9px;
  margin-bottom: 4px;
  background: var(--bg-sunken);
  border-left: 2px solid var(--accent-border);
  border-radius: 0 7px 7px 0;
  font-size: 12px;
  line-height: 1.6;
}

.cite-title {
  /* 颜色不单独指定，继承 style.css 里 body 的全局色（#0f1115） */
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-score {
  flex-shrink: 0;
  color: var(--text-2);
  font-family: Consolas, monospace;
}

.cite-id {
  flex-shrink: 0;
  color: var(--text-disabled);
  font-family: Consolas, monospace;
}

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  /* 用户气泡放宽：窄屏下 72% 会显得太局促 */
  .row-user .bubble-wrap {
    max-width: 86%;
  }

  /* 代码块字号必须写在 <pre code> 上——字体实际由它控制，
     写在 <pre> 上会被它自己的 font-size 覆盖掉（之前这里就是无效的） */
  .markdown-body :deep(pre code) {
    font-size: 12px;
    line-height: 1.55;
    padding: 10px 12px;
  }

  /* 工具栏按钮：手机上加大触摸区域 */
  .markdown-body :deep(.code-btn) {
    padding: 6px 10px;
    font-size: 13px;
  }

  /* 行内代码同步缩小，和块代码保持比例 */
  .markdown-body :deep(code) {
    font-size: 12px;
    padding: 1px 4px;
  }

  /* 表格字号也收一点，13px 在 390px 屏上一行放不下几列 */
  .markdown-body :deep(th),
  .markdown-body :deep(td) {
    font-size: 12px;
    padding: 4px 8px;
  }

  /* 表格在窄屏复用基础样式（max-content + nowrap + 横向滚动），无需额外覆盖 */

  /* 移动端：横向滚动条默认隐藏（滑动功能保留，PC 不受影响） */
  .markdown-body :deep(pre),
  .markdown-body :deep(table) {
    scrollbar-width: none;        /* Firefox */
  }

  .markdown-body :deep(pre)::-webkit-scrollbar,
  .markdown-body :deep(table)::-webkit-scrollbar {
    display: none;                /* WebKit / Android Chrome */
  }

}

/* 用量统计：assistant 回答下方的一行小字
   用 .bubble-wrap 前缀提高特异性，避免被气泡/正文的颜色规则盖掉 */
.bubble-wrap .usage-line {
  display: block;
  margin: 4px 4px 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-2);
}
</style>