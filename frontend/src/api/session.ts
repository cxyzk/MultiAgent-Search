import request from './index'
import type {UsageInfo} from '../types/types'

export interface TaskSubmitResponse {
    task_id: string,
    session_id: string
}

export interface TaskOptions {
    deep_think?: boolean
    force_search?: boolean
}

export async function submitTask(query: string, sessionId: string,
                                 options: TaskOptions = {}): Promise<TaskSubmitResponse> {
    const {data} = await request.post<TaskSubmitResponse>('/task', {
        query,
        session_id: sessionId,
        ...options,
    })
    return data
}

export interface SessionMessage {
    role: 'user' | 'assistant'
    content: string
    created_at: string
    reasoning?: string | null
    usage?: UsageInfo | null
}

export async function fetchMessages(sessionId: string): Promise<SessionMessage[]> {
    const {data} = await request.get<SessionMessage[]>(`/session/${sessionId}/messages`)
    return data
}


export interface SessionItem {
    id: string
    title: string
    updated_at: string
}

export async function fetchSessions(): Promise<SessionItem[]> {
    const {data} = await request.get<SessionItem[]>('/session')
    return data
}

export async function deleteSession(sessionId: string): Promise<void> {
    await request.delete(`/session/${sessionId}`)
}

//重命名会话
export async function renameSession(sessionId: string, title: string): Promise<void> {
    await request.patch(`/session/${sessionId}`, {title})
}

export interface TaskItem {
    id: string
    status: 'running' | 'done' | 'error' | 'interrupted'
    query: string
    error: string | null
    created_at: string
    finished_at: string | null
}

export async function fetchTasks(sessionId: string): Promise<TaskItem[]> {
    const {data} = await request.get<TaskItem[]>(`/session/${sessionId}/tasks`)
    return data
}
