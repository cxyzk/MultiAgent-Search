import axios from 'axios'

const index = axios.create({
  baseURL: '/api',
  timeout: 10_000,
})

export interface TaskSubmitResponse {
    task_id:string,
    session_id:string
}

export async function submitTask(query:string,sessionId:string): Promise<TaskSubmitResponse>
{
    const { data }=await index.post<TaskSubmitResponse>('/task',{
        query,
        session_id:sessionId
    })
    return data
}


export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export async function fetchMessages(sessionId: string): Promise<SessionMessage[]> {
  const { data } = await index.get<SessionMessage[]>(`/session/${sessionId}/messages`)
  return data
}


export interface SessionItem {
  id: string
  title: string
  updated_at: string
}

export async function fetchSessions(): Promise<SessionItem[]> {
  const { data } = await index.get<SessionItem[]>('/session')
  return data
}