<template>
  <Teleport to="body">
    <div v-if="open" class="kb-mask" @click.self="$emit('close')">
      <aside class="kb-panel">
        <header class="kb-head">
          <h3>知识库</h3>
          <button class="kb-close" @click="$emit('close')">✕</button>
        </header>

        <!-- 上传区 -->
        <section class="kb-section">
          <div class="kb-tabs">
            <button :class="{ on: tab === 'file' }" @click="tab = 'file'">上传文件</button>
            <button :class="{ on: tab === 'text' }" @click="tab = 'text'">粘贴文本</button>
          </div>

          <template v-if="tab === 'file'">
            <label class="kb-drop" :class="{ busy: uploading }">
              <input type="file" accept=".txt,.md" hidden @change="onPickFile"/>
              <span>{{ uploading ? '上传中…' : '点击选择 .txt / .md（≤5MB，UTF-8）' }}</span>
            </label>
          </template>

          <template v-else>
            <input v-model="textTitle" class="kb-input" placeholder="标题（可选）"/>
            <textarea v-model="textBody" class="kb-textarea" rows="5" placeholder="粘贴文本内容…"></textarea>
            <button class="btn primary" :disabled="!textBody.trim() || uploading" @click="onUploadText">
              {{ uploading ? '入库中…' : '入库' }}
            </button>
          </template>

          <p v-if="error" class="kb-error">{{ error }}</p>
        </section>

        <!-- 检索调试 -->
        <section class="kb-section">
          <div class="kb-search">
            <input
                v-model="q" class="kb-input" placeholder="检索调试：输入问题看命中"
                @keydown.enter="onSearch"
            />
            <button class="btn ghost" :disabled="!q.trim()" @click="onSearch">检索</button>
          </div>
          <ul v-if="hits.length" class="kb-hits">
            <li v-for="h in hits" :key="h.chunk_id">
              <div class="hit-meta">《{{ h.title }}》 · score {{ h.score }}</div>
              <div class="hit-text">{{ h.content }}</div>
            </li>
          </ul>
          <p v-else-if="searched" class="kb-empty">没有命中</p>
        </section>

        <!-- 文档列表 -->
        <section class="kb-section kb-list-section">
          <div class="kb-list-head">
            <span>已入库 {{ docs.length }} 篇</span>
            <button class="btn ghost" @click="load">刷新</button>
          </div>
          <ul class="kb-docs">
            <li v-for="d in docs" :key="d.id">
              <div class="doc-row">
                <div class="doc-main" @click="toggleDetail(d.id)">
                  <div class="doc-title">{{ d.title }}</div>
                  <div class="doc-meta">{{ d.chunk_count }} 块 · {{ d.created_at.slice(0, 19) }}</div>
                </div>
                <button class="doc-del" title="删除" @click="onDelete(d)">✕</button>
              </div>
              <ul v-if="detail?.id === d.id" class="doc-chunks">
                <li v-for="c in detail.chunks" :key="c.seq">
                  <span class="seq">#{{ c.seq }}</span>{{ c.content }}
                </li>
              </ul>
            </li>
          </ul>
        </section>
      </aside>
    </div>

    <!-- 删除确认：复用统一弹窗，不再用浏览器原生 confirm -->
    <ConfirmDialog
        :open="deleteDialog.open"
        title="删除文档"
        :message="`「${deleteDialog.doc?.title || ''}」切分后的片段会一并清空，且不可恢复。`"
        confirm-text="删除"
        danger
        @confirm="onDeleteConfirm"
        @cancel="deleteDialog.open = false"
    />
  </Teleport>
</template>

<script setup lang="ts">
import {ref, watch} from 'vue'
import {
  fetchDocuments, fetchDocument, deleteDocument, uploadFile, uploadText, searchKb,
} from '../api/kb'
import type {KbDocumentItem, KbDocumentDetail, KbHit} from '../api/kb'
import ConfirmDialog from './ConfirmDialog.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const tab = ref<'file' | 'text'>('file')
const docs = ref<KbDocumentItem[]>([])
const detail = ref<KbDocumentDetail | null>(null)
const hits = ref<KbHit[]>([])
const q = ref('')
const searched = ref(false)
const textTitle = ref('')
const textBody = ref('')
const uploading = ref(false)
const error = ref('')
// 删除确认弹窗状态
const deleteDialog = ref<{ open: boolean; doc: KbDocumentItem | null }>({open: false, doc: null})

async function load(): Promise<void> {
  try {
    docs.value = await fetchDocuments()
    error.value = ''
  } catch (e) {
    error.value = '加载文档列表失败'
  }
}

// 抽屉打开时才拉数据，避免每次进 App 都请求
watch(() => props.open, (v) => {
  if (v) void load()
})

async function onPickFile(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    await uploadFile(file)
    await load()
  } catch (e: any) {
    // 后端 413 / 400 的 detail 在 e.response.data.detail
    error.value = e?.response?.data?.detail ?? '上传失败'
  } finally {
    uploading.value = false
    input.value = ''        // ★ 必须清空，否则选同一个文件不触发 change
  }
}

async function onUploadText(): Promise<void> {
  uploading.value = true
  error.value = ''
  try {
    await uploadText(textBody.value, textTitle.value || undefined)
    textBody.value = ''
    textTitle.value = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '入库失败'
  } finally {
    uploading.value = false
  }
}

async function toggleDetail(id: string): Promise<void> {
  if (detail.value?.id === id) {
    detail.value = null;
    return
  }
  try {
    detail.value = await fetchDocument(id)
  } catch (e) {
    error.value = '加载文档详情失败'
  }
}

// 点删除按钮：只打开确认弹窗，不动数据
function onDelete(d: KbDocumentItem): void {
  deleteDialog.value = {open: true, doc: d}
}

// 弹窗里点"删除"才真正执行
async function onDeleteConfirm(): Promise<void> {
  const d = deleteDialog.value.doc
  deleteDialog.value.open = false
  if (!d) return
  try {
    await deleteDocument(d.id)
    if (detail.value?.id === d.id) detail.value = null
    await load()
  } catch (e) {
    error.value = '删除失败'
  }
}

async function onSearch(): Promise<void> {
  if (!q.value.trim()) return
  try {
    hits.value = (await searchKb(q.value, 5)).hits
    searched.value = true
  } catch (e) {
    error.value = '检索失败'
  }
}
</script>

<style scoped>
.kb-mask {
  position: fixed;
  inset: 0;
  z-index: 1500;
  background: rgba(17, 24, 39, 0.35);
  display: flex;
  justify-content: flex-end;
}

.kb-panel {
  width: 520px;
  max-width: 92vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 30px rgba(0, 0, 0, 0.12);
  overflow-y: auto;
  padding: 16px 18px 24px;
}

.kb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.kb-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.kb-close {
  border: none;
  background: none;
  font-size: 16px;
  color: #6b7280;
  cursor: pointer;
}

.kb-section {
  border-top: 1px solid #f0f1f3;
  padding: 14px 0;
}

.kb-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.kb-tabs button {
  padding: 5px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
}

.kb-tabs button.on {
  background: #edf3fe;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.kb-drop {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 84px;
  border: 1.5px dashed #d1d5db;
  border-radius: 12px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
}

.kb-drop:hover {
  border-color: #3b82f6;
  color: #1d4ed8;
  background: #f8fbff;
}

.kb-drop.busy {
  opacity: 0.6;
  cursor: progress;
}

.kb-input, .kb-textarea {
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 8px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.kb-input:focus, .kb-textarea:focus {
  border-color: #3b82f6;
}

.kb-textarea {
  resize: vertical;
}

.kb-error {
  margin: 6px 0 0;
  font-size: 13px;
  color: #b91c1c;
}

.kb-search {
  display: flex;
  gap: 8px;
}

.kb-search .kb-input {
  margin-bottom: 0;
}

.kb-hits {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
}

.kb-hits li {
  padding: 8px 10px;
  margin-bottom: 6px;
  background: #f9fafb;
  border-radius: 8px;
}

.hit-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 3px;
}

.hit-text {
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
  white-space: pre-wrap;
}

.kb-empty {
  margin: 10px 0 0;
  font-size: 13px;
  color: #9ca3af;
}

.kb-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #6b7280;
}

.kb-docs {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
}

.kb-docs > li {
  margin-bottom: 6px;
}

.doc-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 9px;
}

.doc-row:hover {
  background: #f6f8fa;
}

.doc-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.doc-title {
  font-size: 14px;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.doc-del {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
}

.doc-del:hover {
  background: #fee2e2;
  color: #ef4444;
}

.doc-chunks {
  list-style: none;
  margin: 4px 0 8px;
  padding: 0 10px;
}

.doc-chunks li {
  font-size: 12px;
  line-height: 1.6;
  color: #4b5563;
  padding: 6px 8px;
  margin-bottom: 4px;
  background: #f9fafb;
  border-radius: 7px;
  white-space: pre-wrap;
}

.seq {
  color: #9ca3af;
  margin-right: 6px;
  font-family: Consolas, monospace;
}
</style>