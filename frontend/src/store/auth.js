import { create } from 'zustand'

const useAuthStore = create((set) => ({
  user:  JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token') || null,

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

  updateCoins: (coins) => set(state => {
    const updatedUser = { ...state.user, coins }
    localStorage.setItem('user', JSON.stringify(updatedUser))
    return { user: updatedUser }
  }),

  updateUser: (fields) => set(state => {
    const updatedUser = { ...state.user, ...fields }
    localStorage.setItem('user', JSON.stringify(updatedUser))
    return { user: updatedUser }
  }),
}))

export default useAuthStore