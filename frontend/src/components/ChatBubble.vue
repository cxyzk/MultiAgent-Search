<template>
  <div class="row" :class="'row-' + msg.kind">
    <div
      v-if="msg.kind === 'assistant'"
      class="bubble bubble-assistant markdown-body"
      v-html="renderedHtml"
    ></div>
    <div v-else class="bubble" :class="'bubble-' + msg.kind">{{ msg.text }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import type { ChatMessage } from '../types/types'

const props = defineProps<{ msg: ChatMessage }>()

// Markdown 渲染管线：语法高亮 -> 转 HTML -> DOMPurify 消毒
const md = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code, lang) {
      return lang && hljs.getLanguage(lang)
        ? hljs.highlight(code, { language: lang }).value
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
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;      /* 保留后端回答里的换行 */
  word-break: break-word;
}

/* 用户：蓝底白字，右下角收一个小尖 */
.bubble-user {
  background: #3b82f6;
  color: #fff;
  border-bottom-right-radius: 4px;
}

/* 最终回答：白底卡片 */
.bubble-assistant {
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
  border-bottom-left-radius: 4px;
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
  border: 1px solid #fecaca;
  max-width: 100%;
}

.markdown-body {
  white-space: normal;
}

.markdown-body :deep(p) { margin: 0 0 8px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) { margin: 4px 0; padding-left: 20px; }
.markdown-body :deep(a) { color: #3b82f6; }

/* 代码块容器：纯白底 + 细灰边 + 圆角 */
.markdown-body :deep(pre) {
  background: #f6f8fa;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 12px 16px;
  overflow-x: auto;
}

/* 块内代码：透明底，颜色全部交给高亮主题 */
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 13px;
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

.markdown-body :deep(table) { border-collapse: collapse; }
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 4px 10px;
}
</style>