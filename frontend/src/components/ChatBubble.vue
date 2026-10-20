<template>
  <div class="row" :class="'row-' + msg.kind">
    <div class="bubble-wrap">
      <div
          v-if="msg.kind === 'assistant'"
          class="bubble bubble-assistant markdown-body"
          v-html="renderedHtml"
      ></div>
      <div v-else class="bubble" :class="'bubble-' + msg.kind">{{ msg.text }}</div>

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
import {Marked} from 'marked'
import {markedHighlight} from 'marked-highlight'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import type {ChatMessage} from '../types/types'

const props = defineProps<{ msg: ChatMessage }>()

// 引用列表的展开状态，每条消息独立
const open = ref(false)

// Markdown 渲染管线：语法高亮 -> 转 HTML -> DOMPurify 消毒
const md = new Marked(
    markedHighlight({
      langPrefix: 'hljs language-',
      highlight(code, lang) {
        return lang && hljs.getLanguage(lang)
            ? hljs.highlight(code, {language: lang}).value
            : hljs.highlightAuto(code).value   // 模型没标语言时自动探测
      },
    }),
)

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
.markdown-body :deep(pre) {
  background: #f6f8fa;
  border-radius: 8px;
  padding: 0;
  overflow-x: auto;
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

  /* 表格窄屏可横向滚动 */
  .markdown-body :deep(table) {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }
}
</style>