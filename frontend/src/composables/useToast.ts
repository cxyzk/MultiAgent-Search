/**
 * 轻量全局 Toast：不引组件库，一个 reactive 队列 + 一个渲染组件。
 * 用法：toast.success('已删除') / toast.error('删除失败') / toast.info('...')
 */
import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  text: string
  kind: ToastKind
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 0

function show(text: string, kind: ToastKind, duration: number): void {
  const id = ++seq
  state.items.push({ id, text, kind })
  window.setTimeout(() => {
    const index = state.items.findIndex((item) => item.id === id)
    if (index >= 0) state.items.splice(index, 1)
  }, duration)
}

export const toast = {
  state,
  success: (text: string): void => show(text, 'success', 2000),
  error: (text: string): void => show(text, 'error', 3000),
  info: (text: string): void => show(text, 'info', 2000),
}
