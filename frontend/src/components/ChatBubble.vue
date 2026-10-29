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

// 引用列表的展开状态，每条消息独立
const open = ref(false)

// 思考过程的折叠状态（历史消息默认收起，省空间）
const reasoningOpen = ref(false)

/** 1234 → "1.2k"；不足千直接显示 */
function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

// ===== 代码块工具栏：语言标签 + 复制 =====

/** 生成"工具栏 + 代码体"的 HTML（由自定义 renderer 调用） */
function buildCodeBlock(language: string, highlightedHtml: string): string {
  // 语言名来自模型输出，拼进 HTML 前只保留安全字符
  const label = (language || 'text').replace(/[^\w#+.-]/g, '') || 'text'
  return (
      `<div class="code-block">` +
      `<div class="code-toolbar">` +
      `<span class="code-lang">${label}</span>` +
      `<span class="code-actions">` +
      `<button type="button" class="code-btn code-copy">复制</button>` +
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
  /* assistant 占满整行（代码块/表格才不被压缩）；72% 只给 user 气泡用
     —— 这是 problem.md 第 12 条记过的坑，别在这里再限制一次 */
  flex: 1;
  min-width: 0;
}

.row-user .bubble-wrap {
  align-items: flex-end;
  flex: 0 1 auto;    /* user 不撑满，按内容收缩 */
  max-width: 72%;
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
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap; /* 保留后端回答里的换行 */
  word-break: break-word;
}

/* 用户：蓝底白字，右下角收一个小尖 */
.bubble-user {
  max-width: 100%;
  min-width: 0;
  background: #edf3fe;
  color: #0f1115;
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
  /* 左右内缩：正文和代码块都从这里获得呼吸空间。
     叠加 .message-list 的 16px 后，文字距窗口左缘约 24px */
  padding-left: 8px;
  padding-right: 8px;
}

/* 工具进度：弱视觉的灰色日志字 */
.bubble-step {
  background: none;
  color: #6b7280;
  font-size: 13px;
  font-family: Consolas, monospace;
  padding: 2px 4px;
  max-width: 100%;
}

/* 错误：浅红底 */
.bubble-error {
  background: #fee2e2;
  color: #b91c1c;
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
  color: #3b82f6;
}

/* 代码块容器：纯白底 + 细灰边 + 圆角 */
/* ===== 代码块：工具栏（语言 + 复制/下载）+ 代码体 =====
   注意：这些元素是 v-html 注入的，没有 scoped 的 data-v 属性，
   必须用 :deep() 穿透，否则样式不生效 */
.markdown-body :deep(.code-block) {
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;            /* 圆角裁切工具栏与代码体 */
  background: #f6f8fa;
}

.markdown-body :deep(.code-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 12px;
  /* 与代码块背景一致（继承 .code-block 的 #f6f8fa），保留为透明即可 */
  background: transparent;
  font-size: 12px;
  color: #6b7280;
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
  color: #6b7280;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.markdown-body :deep(.code-btn:hover) {
  background: rgba(15, 23, 42, 0.07);
  color: #111827;
}
.markdown-body :deep(.code-btn.done) {
  color: #16a34a;
}

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

/* 块内代码：透明底，颜色全部交给高亮主题 */
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
}

/* 行内代码：浅灰小块（保留你原来的） */
.markdown-body :deep(code) {
  background: #f3f4f6;
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
  color: #6b7280;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.cite-toggle:hover {
  background: #f3f4f6;
  color: #1d4ed8;
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
  background: #f9fafb;
  border-left: 2px solid #bfdbfe;
  border-radius: 0 7px 7px 0;
  font-size: 12px;
  line-height: 1.6;
}

.cite-title {
  color: #374151;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-score {
  flex-shrink: 0;
  color: #9ca3af;
  font-family: Consolas, monospace;
}

.cite-id {
  flex-shrink: 0;
  color: #d1d5db;
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
  color: #9ca3af;
}
</style>