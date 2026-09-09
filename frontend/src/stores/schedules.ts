import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Schedule, ScheduleInput } from '../types'

export const useScheduleStore = defineStore('schedules', () => {
  const items = ref<Schedule[]>([])
  let requestId = 0
  async function load(start: string, end: string) {
    const current = ++requestId
    const results: Schedule[] = []
    for (let offset = 0; ; offset += 500) {
      const { data } = await api.get<Schedule[]>('/schedules', { params: { start, end, offset, limit: 500 } })
      if (current !== requestId) return
      results.push(...data)
      if (data.length < 500) break
    }
    items.value = results
  }
  async function save(data: ScheduleInput, id?: number) { return id ? api.put(`/schedules/${id}`, data) : api.post('/schedules', data) }
  async function remove(id: number) { await api.delete(`/schedules/${id}`) }
  function clear() { requestId++; items.value = [] }
  return { items, load, save, remove, clear }
})
