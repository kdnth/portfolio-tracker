import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/axios'

export interface UserResponse {
  id: number
  username: string
  email: string
}

const TOKEN_KEY = 'token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const userId = ref<number | null>(null)
  const username = ref<string | null>(null)
  const email = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem(TOKEN_KEY, newToken)
  }

  function clearAuth() {
    token.value = null
    userId.value = null
    username.value = null
    email.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  async function register(usernameInput: string, emailInput: string, password: string) {
    const response = await apiClient.post('/auth/register', {
      username: usernameInput,
      email: emailInput,
      password,
    })
    setToken(response.data.access_token)
    await fetchCurrentUser()
  }

  async function login(identifier: string, password: string) {
    const response = await apiClient.post('/auth/login', {
      identifier,
      password,
    })
    setToken(response.data.access_token)
    await fetchCurrentUser()
  }

  async function fetchCurrentUser() {
    const response = await apiClient.get<UserResponse>('/users/me')
    userId.value = response.data.id
    username.value = response.data.username
    email.value = response.data.email
  }

  function logout() {
    clearAuth()
  }

  return {
    token,
    userId,
    username,
    email,
    isAuthenticated,
    register,
    login,
    logout,
    fetchCurrentUser
  }
})
