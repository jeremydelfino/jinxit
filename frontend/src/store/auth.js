import { create } from 'zustand'
import api from '../api/client'

function isTokenValid(token) {
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (!payload.exp) return true
    return payload.exp * 1000 > Date.now()
  } catch { return false }
}

function hydrate() {
  const token = localStorage.getItem('token')
  const user  = JSON.parse(localStorage.getItem('user') || 'null')
  if (!token || !isTokenValid(token)) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    return { user: null, token: null }
  }
  return { user, token }
}

const useAuthStore = create((set, get) => ({
  ...hydrate(),

  login: (user, token) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ user, token })
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ user: null, token: null })
  },

  // Appelé au démarrage si token présent mais user absent
  fetchMe: async () => {
    const { token, user } = get()
    if (!token || user) return   // rien à faire
    try {
      const { data } = await api.get('/profile/me')
      const u = { id: data.id, username: data.username, email: data.email, coins: data.coins, avatar_url: data.avatar_url, is_admin: data.is_admin }
      localStorage.setItem('user', JSON.stringify(u))
      set({ user: u })
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      set({ user: null, token: null })
    }
  },

  updateCoins: (coins) => set(state => {
    if (!state.user) return state
    const updatedUser = { ...state.user, coins }
    localStorage.setItem('user', JSON.stringify(updatedUser))
    return { user: updatedUser }
  }),

  updateUser: (fields) => set(state => {
    if (!state.user) return state
    const updatedUser = { ...state.user, ...fields }
    localStorage.setItem('user', JSON.stringify(updatedUser))
    return { user: updatedUser }
  }),
}))

export default useAuthStore