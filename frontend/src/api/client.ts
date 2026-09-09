import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 20000,
  withCredentials: true,
  headers: { 'X-CSRF-Protection': '1' },
})

api.interceptors.request.use(config => {
  const groupId = localStorage.getItem('jerp-group-id')
  if (groupId) config.headers['X-Group-ID'] = groupId
  return config
})

api.interceptors.response.use(response => response, error => {
  const url = error.config?.url || ''
  if (error.response?.status === 401 && !['/auth/login', '/auth/signup', '/auth/me'].includes(url)) {
    window.dispatchEvent(new Event('jerp-unauthorized'))
  }
  return Promise.reject(error)
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item: { msg: string }) => item.msg).join(' / ')
    if (!error.response) return '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  }
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}
