export const SIDES = { BLUE: 'BLUE', RED: 'RED' }
export const SIDE_COLORS = { BLUE: '#4a8de8', RED: '#e84a4a' }
export const SIDE_LABELS = { BLUE: 'Côté Bleu', RED: 'Côté Rouge' }

export const LANES = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
export const LANE_LABELS = {
  TOP:     'Top',
  JUNGLE:  'Jungle',
  MID:     'Mid',
  ADC:     'ADC',
  SUPPORT: 'Support',
}
export const LANE_ICONS = {
  TOP:     '⚔️',
  JUNGLE:  '🌳',
  MID:     '✨',
  ADC:     '🏹',
  SUPPORT: '🛡️',
}

export const PHASE_LABELS = {
  BAN_1:       'Phase de bans 1',
  PICK_1:      'Phase de picks 1',
  BAN_2:       'Phase de bans 2',
  PICK_2:      'Phase de picks 2',
  ROLE_ASSIGN: 'Assignation des rôles',
  FINISHED:    'Partie terminée',
}

/* ─── Timer ─── */
export const TURN_DURATION_S    = 30   // durée d'un tour user
export const BOT_DELAY_MIN_MS   = 800  // délai mini avant action bot
export const BOT_DELAY_MAX_MS   = 1800 // délai max avant action bot
export const ROLE_ASSIGN_DURATION_S = 30   // temps max pour assigner les rôles
