import axios from 'axios'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, errorMessage } from '../api/client'
import type { CurrentUser } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const initialized = ref(false)
  const restoreError = ref('')
  let pendingRestore: Promise<void> | null = null
  let generation = 0

  // Remove legacy bearer credentials. Sessions are now exclusively HttpOnly cookies.
  sessionStorage.removeItem('jerp-token')

  async function restore(force = false) {
    if (pendingRestore) return pendingRestore
    if (initialized.value && !force) return
    const current = generation
    pendingRestore = (async () => {
      try {
        const { data } = await api.get<CurrentUser>('/auth/me')
        if (current === generation) {
          user.value = data
          initialized.value = true
          restoreError.value = ''
        }
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          clear()
        } else if (current === generation) {
          restoreError.value = errorMessage(error)
          initialized.value = false
        }
      } finally { pendingRestore = null }
    })()
    return pendingRestore
  }

  async function login(email: string, password: string, rememberMe: boolean) {
    const { data } = await api.post<CurrentUser>('/auth/login', { email, password, remember_me: rememberMe })
    generation++
    user.value = data
    initialized.value = true
    restoreError.value = ''
  }

  async function signup(name: string, email: string, password: string, passwordConfirm: string) {
    const { data } = await api.post<CurrentUser>('/auth/signup', {
      name, email, password, password_confirm: passwordConfirm,
    })
    generation++
    user.value = data
    initialized.value = true
    restoreError.value = ''
  }

  function clear() {
    generation++
    user.value = null
    initialized.value = true
  }

  async function logout() {
    await api.post('/auth/logout')
    clear()
  }

  return { user, initialized, restoreError, restore, login, signup, logout, clear }
})
