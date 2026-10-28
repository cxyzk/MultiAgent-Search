<template>
  <Teleport to="body">
    <div class="toast-wrap">
      <TransitionGroup name="toast">
        <div
            v-for="item in toast.state.items"
            :key="item.id"
            class="toast"
            :class="`toast-${item.kind}`"
        >
          {{ item.text }}
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { toast } from '../composables/useToast'
</script>

<style scoped>
.toast-wrap {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;              /* 高于弹窗（2000）/ 知识库面板（1500） */
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;       /* 不挡住下面的点击 */
}

.toast {
  padding: 9px 14px;
  border-radius: 10px;
  font-size: 13px;
  color: #fff;
  background: #000;                    /* 纯黑 */
  border-left: 3px solid transparent;  /* 预留色条位置，成功/失败时上色 */
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
}


.toast-error {
  border-left-color: #ef4444;
}

/* 出现 / 消失的过渡 */
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
