/**
 * 轻触震动反馈（触觉）。
 *
 * - Android（Chrome / Firefox）：真实震动，navigator.vibrate(ms)
 * - iPhone（iOS Safari）：**没有** Web 触觉 API，静默跳过——不是 bug，是平台限制
 * - 桌面浏览器：一般不实现，同样静默跳过
 */
export function hapticTap(duration = 20): void {
  try {
    navigator.vibrate?.(duration)
  } catch {
    // 部分浏览器在后台/无权限时会抛错，忽略即可，不能影响点击行为
  }
}
