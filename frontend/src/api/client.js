import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'An unexpected error occurred'
    return Promise.reject(new Error(message))
  }
)

// ── Documents ──────────────────────────────────────────────────────────────

export const documentsApi = {
  upload: (files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return api.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (skip = 0, limit = 50) =>
    api.get('/documents', { params: { skip, limit } }),
  get: (id) => api.get(`/documents/${id}`),
  delete: (id) => api.delete(`/documents/${id}`),
}

// ── Chat ───────────────────────────────────────────────────────────────────

export const chatApi = {
  listConversations: () => api.get('/chat/conversations'),
  getConversation: (id) => api.get(`/chat/conversations/${id}`),
  createConversation: (title = 'New conversation') =>
    api.post('/chat/conversations', { title }),
  deleteConversation: (id) => api.delete(`/chat/conversations/${id}`),
  sendMessage: (message, conversationId = null) =>
    api.post('/chat/message', { message, conversation_id: conversationId }),
}

// ── Health ─────────────────────────────────────────────────────────────────

export const healthApi = {
  check: () => axios.get('/health'),
}

export default api
