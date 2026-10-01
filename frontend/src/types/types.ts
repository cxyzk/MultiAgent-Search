// 前端消息列表里的一条
export type MessageKind = 'user' | 'assistant' | 'step' | 'error'

export interface ChatMessage {
  id: number
  kind: MessageKind
  text: string
}

// 后端 WS 推送的事件：按 type 可辨识的联合类型，和后端协议一一对应
export type ServerEvent =
  | { type: 'progress'; round: number; tools: string[]; task_id: string }
  | { type: 'tool_result'; tool: string; task_id: string }
  | { type: 'result'; content: string; task_id: string }
  | { type: 'error'; error: string; task_id: string }