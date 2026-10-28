<template>
  <Teleport to="body">
    <div v-if="open" class="dlg-mask" @click.self="$emit('cancel')">
      <div class="dlg" role="dialog" aria-modal="true">
        <h3 class="dlg-title">
          <svg v-if="danger" class="dlg-warn" viewBox="0 0 24 24" width="16" height="16" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 9v4M12 17h.01"/>
            <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>
          </svg>
          {{ title }}
        </h3>
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

<style scoped>
.dlg-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dlg-warn {
  flex-shrink: 0;
  color: #dc2626;
}
</style>
