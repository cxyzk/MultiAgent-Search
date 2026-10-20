<template>
  <Teleport to="body">
    <div v-if="open" class="dlg-mask" @click.self="$emit('cancel')">
      <div class="dlg" role="dialog" aria-modal="true">
        <h3 class="dlg-title">{{ title }}</h3>
        <p v-if="message" class="dlg-msg">{{ message }}</p>
        <div class="dlg-actions">
          <button class="btn ghost" @click="$emit('cancel')">取消</button>
          <button class="btn" :class="danger ? 'danger' : 'primary'" @click="$emit('confirm')">
            {{ confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import {watch, onUnmounted} from 'vue'

const props = defineProps<{
  open: boolean
  title: string
  message?: string
  confirmText?: string
  danger?: boolean
}>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
}

watch(() => props.open, (v) => {
  if (v) document.addEventListener('keydown', onKey)
  else document.removeEventListener('keydown', onKey)
})
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>
