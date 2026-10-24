// 前端消息列表里的一条
export type MessageKind = 'user' | 'assistant' | 'step' | 'error'

// 知识库检索命中的片段来源（后端 kb_search 的 citations 字段）
export interface Citation {
  title: string
  chunk_id: number
  score: number
}

export interface UsageInfo {
  calls: number             // 本任务 LLM 调用次数
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cache_hit_tokens: number  // 上下文缓存命中（计费更低）
  llm_latency_ms: number    // 本任务累计 LLM 耗时（毫秒）
}

export interface ChatMessage {
  id: number
  kind: MessageKind
  text: string
  citations?: Citation[]   // 仅 assistant 消息可能带，渲染"参考片段"
  usage?: UsageInfo        // 仅 assistant 最终回答可能带，渲染用量小字
}

// 后端 sse 推送的事件：按 type 可辨识的联合类型，和后端协议一一对应
export type ServerEvent =
  | { type: 'progress'; round: number; tools: string[]; args?: string[]; task_id: string }
  | { type: 'tool_result'; tool: string; task_id: string }
  | { type: 'citations'; tool: string; items: Citation[]; task_id: string }
  | { type: 'result'; content: string; task_id: string; usage?: UsageInfo }
  | { type: 'error'; error: string; task_id: string }
  | { type: 'token'; delta: string; task_id: string }
