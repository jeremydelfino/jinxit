import api from './client'

export const startGame    = (opponent) => api.post('/coachdiff/start', opponent ? { opponent } : {}).then(r => r.data)
export const getGame      = (gameId)            => api.get(`/coachdiff/game/${gameId}`).then(r => r.data)
export const userAction   = (gameId, champion)  => api.post('/coachdiff/action', { game_id: gameId, champion }).then(r => r.data)
export const botTurn      = (gameId)            => api.post('/coachdiff/bot-turn', { game_id: gameId }).then(r => r.data)
export const assignRoles  = (gameId, roleMap)   => api.post('/coachdiff/assign-roles', { game_id: gameId, role_map: roleMap }).then(r => r.data)
export const getHistory   = ()                  => api.get('/coachdiff/history').then(r => r.data)