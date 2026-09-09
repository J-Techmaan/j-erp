import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Document } from '../types'

export const useApprovalStore = defineStore('approvals', () => {
  const pending = ref<Document[]>([])
  async function load() { pending.value = (await api.get<Document[]>('/approvals/pending', { params: { limit: 100 } })).data }
  function clear() { pending.value = [] }
  return { pending, load, clear }
})
