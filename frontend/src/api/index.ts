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
