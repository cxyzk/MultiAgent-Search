/** 每个标签页一个稳定 ID：SSE 连接和任务提交都用它，保证"只推给发起任务的那个标签页"。
 *
 * 用 sessionStorage 而不是 localStorage：
 * - sessionStorage 是标签页级 → 开两个标签页会得到两个 ID，各自只看自己的流
 * - localStorage 是所有标签共享 → 两个标签会拿同一个 ID，又变成互相收到
 *
 * sessionStorage 不可用时（隐私模式、受限 iframe）退回模块级变量：
 * 至少在同一次页面生命周期内稳定——否则每次调用都生成新 ID，
 * SSE 注册的 id 和任务带的 id 永远对不上，谁都收不到推送。
 */
let fallbackId = ''

function genId(): string {
    return typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function getClientId(): string {
    const KEY = 'client_id'
    try {
        let id = sessionStorage.getItem(KEY)
        if (!id) {
            id = genId()
            sessionStorage.setItem(KEY, id)
        }
        return id
    } catch {
        if (!fallbackId) fallbackId = genId()
        return fallbackId
    }
}
