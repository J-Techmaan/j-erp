import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Document, DocumentInput, DocumentStatus } from '../types'

export const useDocumentStore = defineStore('documents', () => {
  const items = ref<Document[]>([])
  const selected = ref<Document | null>(null)
  async function list(scope: string, status = '', offset = 0) {
    items.value = (await api.get<Document[]>('/documents', { params: { scope, status: status || undefined, offset, limit: 20 } })).data
  }
  async function get(id: number) { selected.value = (await api.get<Document>(`/documents/${id}`)).data; return selected.value }
  async function save(data: DocumentInput, id?: number) {
    selected.value = (id ? await api.put<Document>(`/documents/${id}`, data) : await api.post<Document>('/documents', data)).data
    return selected.value
  }
  async function action(id: number, name: 'submit' | 'approve' | 'reject' | 'cancel', revision: number, comment = '') {
    const payload = name === 'submit' ? { revision, message: comment } : name === 'cancel' ? { revision } : { revision, comment }
    selected.value = (await api.post<Document>(`/documents/${id}/${name}`, payload)).data
    return selected.value
  }
  async function recreate(id: number) { selected.value = (await api.post<Document>(`/documents/${id}/recreate`)).data; return selected.value }
  function clear() { items.value = []; selected.value = null }
  return { items, selected, list, get, save, action, recreate, clear }
})
