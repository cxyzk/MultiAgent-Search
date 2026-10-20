<template>
  <Teleport to="body">
    <div v-if="open" class="dlg-mask" @click.self="$emit('cancel')">
      <div class="dlg" role="dialog" aria-modal="true">
        <h3 class="dlg-title">{{ title }}</h3>
        <input
            ref="inputEl"
            v-model="value"
            class="dlg-input"
            maxlength="60"
            @keyup.enter="submit"
            @keyup.esc="$emit('cancel')"
        />
        <div class="dlg-actions">
          <button class="btn ghost" @click="$emit('cancel')">取消</button>
          <button class="btn primary" :disabled="!value.trim()" @click="submit">
            {{ confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import {nextTick, ref, watch} from 'vue'

const props = defineProps<{
  open: boolean
  title: string
  initial?: string
  confirmText?: string
}>()
const emit = defineEmits<{ confirm: [value: string]; cancel: [] }>()

const value = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

watch(() => props.open, async (v) => {
  if (!v) return
  value.value = props.initial ?? ''      // ★ 每次打开都重置（否则会带着上次的输入）
  await nextTick()                        // ★ 等 v-if 把 DOM 挂上
  inputEl.value?.focus()
  inputEl.value?.select()                 // 全选，方便直接打新标题
})

function submit() {
  const v = value.value.trim()
  if (v) emit('confirm', v)
}
</script>
