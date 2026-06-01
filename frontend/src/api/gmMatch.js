import api from './client'

export const matchStart   = ()         => api.post('/gm/season/match/start').then(r => r.data)
export const matchAction  = (champion) => api.post('/gm/season/match/action', { champion }).then(r => r.data)
export const matchBotTurn = ()         => api.post('/gm/season/match/bot-turn').then(r => r.data)
export const matchFinish  = (role_map) => api.post('/gm/season/match/finish', { role_map }).then(r => r.data)