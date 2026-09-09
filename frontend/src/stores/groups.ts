import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { Group, Membership } from '../types'

export const useGroupStore = defineStore('groups', () => {
  const groups = ref<Group[]>([])
  const currentId = ref<number | null>(Number(localStorage.getItem('jerp-group-id')) || null)
  const current = computed(() => groups.value.find(group => group.id === currentId.value) || null)
  const pending = ref<Membership[]>([])
  async function load() {
    groups.value = (await api.get<Group[]>('/groups')).data
    if (!groups.value.some(group => group.id === currentId.value)) currentId.value = groups.value[0]?.id || null
    if (currentId.value) localStorage.setItem('jerp-group-id', String(currentId.value))
    else localStorage.removeItem('jerp-group-id')
  }
  function select(id: number) { currentId.value = id; localStorage.setItem('jerp-group-id', String(id)) }
  async function create(name: string) { const { data } = await api.post<Group>('/groups', { name }); await load(); select(data.id); return data }
  async function join(code: string) { return (await api.post('/groups/join', { code })).data }
  async function detail(id: number) { return (await api.get<Group>(`/groups/${id}`)).data }
  async function loadPending(groupId: number) { pending.value = (await api.get<Membership[]>(`/groups/${groupId}/pending`)).data }
  async function decide(groupId: number, membershipId: number, action: 'approve' | 'reject') { await api.post(`/groups/${groupId}/members/${membershipId}/${action}`); await loadPending(groupId) }
  async function remove(groupId: number, membershipId: number) { await api.delete(`/groups/${groupId}/members/${membershipId}`) }
  async function removeGroup(groupId: number) { await api.delete(`/groups/${groupId}`); await load() }
  function clear() { groups.value = []; pending.value = []; currentId.value = null; localStorage.removeItem('jerp-group-id') }
  return { groups, currentId, current, pending, load, select, create, join, detail, loadPending, decide, remove, removeGroup, clear }
})
