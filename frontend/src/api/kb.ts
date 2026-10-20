import request from './index'

export interface KbDocumentItem {
    id: string
    title: string
    source: string | null
    created_at: string
    chunk_count: number        // 列表接口返回数量
}

export interface KbChunk {
    seq: number
    content: string
}

export interface KbDocumentDetail {
    id: string
    title: string
    source: string | null
    created_at: string
    chunks: KbChunk[]          // 详情接口返回数组
}

export interface KbUploadResult {
    id: string
    title: string
    chunks: number
}

export interface KbHit {
    chunk_id: number
    document_id: string
    title: string
    content: string
    score: number
}

export async function fetchDocuments(): Promise<KbDocumentItem[]> {
    const {data} = await request.get<KbDocumentItem[]>('/kb/documents')
    return data
}

export async function fetchDocument(docId: string): Promise<KbDocumentDetail> {
    const {data} = await request.get<KbDocumentDetail>(`/kb/documents/${docId}`)
    return data
}

export async function deleteDocument(docId: string): Promise<void> {
    await request.delete(`/kb/documents/${docId}`)
}

// ★ 上传必须是 FormData；不要手动设 Content-Type，浏览器要自己写 boundary
export async function uploadFile(file: File, title?: string): Promise<KbUploadResult> {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    const {data} = await request.post<KbUploadResult>('/kb/documents', form)
    return data
}

export async function uploadText(content: string, title?: string): Promise<KbUploadResult> {
    const form = new FormData()
    form.append('content', content)
    if (title) form.append('title', title)
    const {data} = await request.post<KbUploadResult>('/kb/documents', form)
    return data
}

export async function searchKb(query: string, topK = 5) {
    // ★ 这个接口是 POST + JSON，不是 GET
    const {data} = await request.post<{ query: string; hits: KbHit[] }>('/kb/search', {
        query,
        top_k: topK,
    })
    return data
}


