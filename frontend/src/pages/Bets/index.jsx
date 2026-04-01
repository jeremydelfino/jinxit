import './Bets.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV      = '14.24.1'
const PER_PAGE = 8

const STATUS_CONFIG = {
  pending:   { label: 'En cours',  color: '#f59e0b', bg: '#f59e0b12', icon: '⏳' },
  won:       { label: 'Gagné',     color: '#65BD62', bg: '#65BD6212', icon: '✓'  },
  lost:      { label: 'Perdu',     color: '#ef4444', bg: '#ef444412', icon: '✗'  },
  cancelled: { label: 'Remboursé', color: '#6b7280', bg: '#6b728012', icon: '↩️' },
}

const LEAGUE_META = {
  lec:    { label: 'LEC',    color: '#00b4d8' },
  lck:    { label: 'LCK',    color: '#c89b3c' },
  lcs:    { label: 'LCS',    color: '#378add' },
  lpl:    { label: 'LPL',    color: '#ef4444' },
  lfl:    { label: 'LFL',    color: '#0099ff' },
  worlds: { label: 'Worlds', color: '#65BD62' },
  msi:    { label: 'MSI',    color: '#a855f7' },
}

const BET_TYPE_LABELS = {
  who_wins:              '🏆 Victoire',
  first_blood:           '🩸 First Blood',
  first_tower:           '🗼 1ère tour',
  first_dragon:          '🐉 1er dragon',
  first_baron:           '👁️ 1er Baron',
  game_duration_under25: '⚡ < 25 min',
  game_duration_25_35:   '⏱️ 25–35 min',
  game_duration_over35:  '🐢 > 35 min',
  player_positive_kda:   '📊 KDA positif',
  champion_kda_over25:   '⚔️ KDA > 2.5',
  champion_kda_over5:    '🔥 KDA > 5',
  champion_kda_over10:   '💀 KDA > 10',
  top_damage:            '💥 Top dégâts',
  jungle_gap:            '🌿 Jungle Gap',
  match_winner:          '🏆 Vainqueur',
  exact_score:           '🎯 Score exact',
}

const QUEUE_NAMES = {
  '420': 'Ranked Solo', '440': 'Ranked Flex', '400': 'Normal', '450': 'ARAM',
}

// ─── Helpers ──────────────────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (h > 24) return `il y a ${Math.floor(h / 24)}j`
  if (h > 0)  return `il y a ${h}h`
  if (m > 0)  return `il y a ${m}m`
  return "à l'instant"
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function champIcon(name) {
  if (!name) return null
  return `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${name}.png`
}

function betValueLabel(betValue) {
  if (!betValue) return '—'
  if (betValue === 'blue')      return '🟦 Blue side'
  if (betValue === 'red')       return '🟥 Red side'
  if (betValue === 'none')      return '⚖️ Aucun gap'
  if (betValue === 'confirmed') return '✓'
  return betValue
}

function parseBetLabel(betValue, team1Code, team2Code) {
  if (!betValue) return '—'
  if (betValue === 'team1') return team1Code
  if (betValue === 'team2') return team2Code
  const parts = betValue.split('_')
  if (parts.length === 2) {
    const winner = parts[0] === 'team1' ? team1Code : team2Code
    const loser  = parts[0] === 'team1' ? team2Code : team1Code
    const [a, b] = parts[1].split('-')
    return `${winner} ${a}—${b} ${loser}`
  }
  return betValue
}

// ─── groupBetsBySlip ─────────────────────────────────────────
// Groupe par slip_id si présent, sinon chaque pari est son propre ticket
function groupBetsBySlip(bets) {
  const groups = {}

  for (const bet of bets) {
    // slip_id = clé du groupe → même soumission
    // Pas de slip_id (anciens paris) → chaque pari est isolé
    const key = bet.slip_id ?? `solo_${bet.id}`
    if (!groups[key]) groups[key] = []
    groups[key].push(bet)
  }

  return Object.values(groups)
    .map(group => {
      const isCombined = group.length > 1
      const statuses   = group.map(b => b.status)

      let globalStatus = 'pending'
      if (statuses.every(s => s === 'won'))            globalStatus = 'won'
      else if (statuses.every(s => s === 'cancelled')) globalStatus = 'cancelled'
      else if (statuses.some(s => s === 'lost'))       globalStatus = 'lost'
      else if (statuses.some(s => s === 'pending'))    globalStatus = 'pending'
      else                                              globalStatus = 'cancelled'

      const totalAmount  = group.reduce((acc, b) => acc + b.amount, 0)
      const totalPayout  = group.reduce((acc, b) => acc + (b.payout || 0), 0)
      // Cote combinée seulement si vrai combiné, sinon cote simple
      const combinedOdds = isCombined
        ? group.reduce((acc, b) => acc * (b.odds || 2), 1)
        : group[0].odds || 2

      return {
        key:          group[0].slip_id ?? `solo_${group[0].id}`,
        live_game_id: group[0].live_game_id,
        game_status:  group[0].game_status,
        game:         group[0].game,
        bets:         group,
        isCombined,
        globalStatus,
        totalAmount,
        totalPayout,
        combinedOdds,
        created_at:   group[0].created_at,
      }
    })
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
}

function resolveGameCtx(ticket) {
  const game = ticket.game
  const pro  = game?.pro

  if (pro) {
    return {
      type:        'pro',
      name:        pro.name,
      sub:         pro.team,
      subColor:    pro.accent_color || '#65BD62',
      imgUrl:      pro.photo_url,
      initials:    pro.name.slice(0, 2).toUpperCase(),
      borderColor: pro.accent_color || '#65BD62',
      summonerName: pro.name,
      region:       pro.region || 'EUW',
      tag:          pro.tag_line || 'EUW',
    }
  }

  const betPlayer  = ticket.bets[0]?.game?.bet_player
  const sumName    = betPlayer?.summoner_name || null
  const champName  = betPlayer?.champion_name || null
  const tagLine   = betPlayer?.tag_line || null
  const champIcon  = champName
    ? `https://ddragon.leagueoflegends.com/cdn/14.7.1/img/champion/${champName}.png`
    : null

  return {
    type:        'casual',
    name:        sumName || 'Joueur inconnu',
    sub:         null,   // ← supprimé : évite le doublon avec ticket-queue
    subColor:    '#6b7280',
    imgUrl:      champIcon,   // ← icône champion comme avatar
    initials:    sumName ? sumName.slice(0, 2).toUpperCase() : '?',
    borderColor: '#ffffff20',
    summonerName: sumName,
    region:       betPlayer?.region || 'EUW',
    tag:          tagLine,
  }
}

// ─── EsportsBetRow ────────────────────────────────────────────
function EsportsBetRow({ bet, onCancel, i }) {
  const status    = STATUS_CONFIG[bet.status] || STATUS_CONFIG.pending
  const lm        = LEAGUE_META[bet.league_slug?.toLowerCase()] || {}
  const lc        = lm.color || '#65BD62'
  const isPending = bet.status === 'pending'
  const betLabel  = parseBetLabel(bet.bet_value, bet.team1_code, bet.team2_code)
  const betType   = BET_TYPE_LABELS[bet.bet_type] || bet.bet_type

  return (
    <div className="esbet-row" style={{ animationDelay: `${i * 0.04}s` }}>
      <div className="esbet-bar" style={{ background: status.color }} />
      <div className="esbet-ctx">
        <div className="esbet-league" style={{ color: lc }}>
          <span className="esbet-league-dot" style={{ background: lc }} />
          {bet.league_name || lm.label || bet.league_slug?.toUpperCase()}
        </div>
        <div className="esbet-teams">
          <img src={bet.team1_image} alt={bet.team1_code} className="esbet-team-logo" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          <span className="esbet-team-code">{bet.team1_code}</span>
          <span className="esbet-vs">vs</span>
          <span className="esbet-team-code">{bet.team2_code}</span>
          <img src={bet.team2_image} alt={bet.team2_code} className="esbet-team-logo" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
        </div>
        <div className="esbet-meta">
          <span className="esbet-bo">BO{bet.bo_format}</span>
          {bet.match_start_time && <span className="esbet-date">{formatDate(bet.match_start_time)}</span>}
        </div>
      </div>
      <div className="esbet-body">
        <div className="esbet-sel-type">{betType}</div>
        <div className="esbet-sel-value" style={{ color: lc }}>{betLabel}</div>
        <div className="esbet-odds-row">
          <span className="esbet-odds-lbl">Cote</span>
          <span className="esbet-odds-val">×{bet.odds?.toFixed(2)}</span>
        </div>
      </div>
      <div className="esbet-right">
        <div className="esbet-finances">
          <div className="esbet-fin-row">
            <span className="esbet-fin-lbl">Mise</span>
            <span className="esbet-fin-val">{bet.amount?.toLocaleString()} <span className="esbet-coin">coins</span></span>
          </div>
          <div className="esbet-fin-row">
            <span className="esbet-fin-lbl">
              {bet.status === 'won' ? 'Gagné' : bet.status === 'cancelled' ? 'Remboursé' : 'Potentiel'}
            </span>
            <span className="esbet-fin-val" style={{ color: bet.status === 'won' ? '#65BD62' : '#6b7280' }}>
              {bet.status === 'won'
                ? `+${bet.payout?.toLocaleString()}`
                : bet.status === 'cancelled'
                  ? `+${bet.amount?.toLocaleString()}`
                  : `~${Math.floor((bet.amount || 0) * (bet.odds || 2))?.toLocaleString()}`
              } <span className="esbet-coin">coins</span>
            </span>
          </div>
        </div>
        <div className="esbet-actions">
          {isPending && (
            <button className="esbet-cancel-btn" onClick={() => onCancel(bet)}>Annuler</button>
          )}
          <div className="esbet-status-badge" style={{ color: status.color, background: status.bg, borderColor: status.color + '28' }}>
            {status.icon} {status.label}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── CancelModal ──────────────────────────────────────────────
function CancelModal({ bet, onConfirm, onClose }) {
  const [loading, setLoading] = useState(false)
  const lc = LEAGUE_META[bet.league_slug?.toLowerCase()]?.color || '#65BD62'

  return (
    <div className="cancel-overlay" onClick={onClose}>
      <div className="cancel-modal" onClick={e => e.stopPropagation()}>
        <div className="cancel-modal-icon">🗑️</div>
        <div className="cancel-modal-title">Annuler ce pari ?</div>
        <div className="cancel-modal-sub">Tu seras remboursé intégralement.</div>
        <div className="cancel-modal-recap" style={{ borderColor: lc + '30', background: lc + '08' }}>
          <div className="cancel-recap-teams">
            <img src={bet.team1_image} alt="" onError={e => { e.target.style.display = 'none' }} />
            <span className="cancel-recap-code">{bet.team1_code}</span>
            <span className="cancel-recap-vs">vs</span>
            <span className="cancel-recap-code">{bet.team2_code}</span>
            <img src={bet.team2_image} alt="" onError={e => { e.target.style.display = 'none' }} />
          </div>
          <div className="cancel-recap-amount">
            <span className="cancel-recap-lbl">Mise à rembourser</span>
            <span className="cancel-recap-val" style={{ color: lc }}>{bet.amount?.toLocaleString()} coins</span>
          </div>
        </div>
        <div className="cancel-modal-btns">
          <button className="cancel-btn-secondary" onClick={onClose}>Garder</button>
          <button
            className="cancel-btn-primary"
            onClick={async () => { setLoading(true); await onConfirm(bet); setLoading(false) }}
            disabled={loading}
          >
            {loading ? <span className="cancel-spinner" /> : "Confirmer l'annulation"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────
export default function Bets() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [bets,        setBets]        = useState([])
  const [esportsBets, setEsportsBets] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [filter,      setFilter]      = useState('all')
  const [tab,         setTab]         = useState('games')
  const [page,        setPage]        = useState(1)
  const [cancelModal, setCancelModal] = useState(null)

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    Promise.all([api.get('/bets/my-bets'), api.get('/esports/bets/my-bets')])
      .then(([r1, r2]) => { setBets(r1.data); setEsportsBets(r2.data) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  useEffect(() => { setPage(1) }, [filter, tab])

  const tickets = groupBetsBySlip(bets)

  // ── Stats globales ────────────────────────────────────────
  const allWon       = [...tickets.filter(t => t.globalStatus === 'won'),       ...esportsBets.filter(b => b.status === 'won')]
  const allLost      = [...tickets.filter(t => t.globalStatus === 'lost'),      ...esportsBets.filter(b => b.status === 'lost')]
  const allPending   = [...tickets.filter(t => t.globalStatus === 'pending'),   ...esportsBets.filter(b => b.status === 'pending')]
  const allCancelled = [...tickets.filter(t => t.globalStatus === 'cancelled'), ...esportsBets.filter(b => b.status === 'cancelled')]
  const resolved     = allWon.length + allLost.length
  const winrate      = resolved > 0 ? Math.round((allWon.length / resolved) * 100) : 0

  // ── Filtres ───────────────────────────────────────────────
  const filteredGame   = filter === 'all' ? tickets    : tickets.filter(t => t.globalStatus === filter)
  const filteredEsport = filter === 'all' ? esportsBets : esportsBets.filter(b => b.status === filter)
  const currentList    = tab === 'esports' ? filteredEsport : filteredGame
  const totalPages     = Math.ceil(currentList.length / PER_PAGE)
  const paginated      = currentList.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const getVisiblePages = () => {
    const pages = []
    for (let p = Math.max(1, page - 1); p <= Math.min(totalPages, page + 1); p++) pages.push(p)
    return pages
  }

  const handleCancelEsportsBet = async (bet) => {
    try {
      await api.post(`/esports/bets/${bet.id}/cancel`)
      const r = await api.get('/esports/bets/my-bets')
      setEsportsBets(r.data)
      setCancelModal(null)
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur lors de l'annulation")
    }
  }

  return (
    <div className="bets-page">

      {/* ── Header ── */}
      <div className="bets-header">
        <div className="bets-header-inner">
          <div>
            <div className="bets-eyebrow">MES PARIS</div>
            <div className="bets-title">Historique</div>
            <div className="bets-sub">{tickets.length + esportsBets.length} tickets au total</div>
          </div>
          {user && (
            <div className="bets-balance">
              <div className="bets-balance-dot" />
              <div>
                <div className="bets-balance-val">{user.coins?.toLocaleString()}</div>
                <div className="bets-balance-lbl">coins</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bets-content">

        {/* ── Stats ── */}
        <div className="bets-stats">
          {[
            { label: 'Total',      val: tickets.length + esportsBets.length, color: '#6b7280' },
            { label: 'En cours',   val: allPending.length,   color: '#f59e0b' },
            { label: 'Gagnés',     val: allWon.length,       color: '#65BD62' },
            { label: 'Perdus',     val: allLost.length,      color: '#ef4444' },
            { label: 'Remboursés', val: allCancelled.length, color: '#6b7280' },
            { label: 'Winrate',    val: `${winrate}%`,       color: winrate >= 50 ? '#65BD62' : '#ef4444' },
          ].map(s => (
            <div key={s.label} className="bets-stat-card">
              <div className="bst-val" style={{ color: s.color }}>{s.val}</div>
              <div className="bst-label">{s.label}</div>
            </div>
          ))}
        </div>

        {/* ── Tabs ── */}
        <div className="bets-tabs">
          <button className={`bets-tab ${tab === 'esports' ? 'active' : ''}`} onClick={() => setTab('esports')}>
            <span className="bets-tab-icon">🏆</span>Paris officiels
            <span className="bets-tab-count">{esportsBets.length}</span>
          </button>
          <button className={`bets-tab ${tab === 'games' ? 'active' : ''}`} onClick={() => setTab('games')}>
            <span className="bets-tab-icon">🎮</span>Paris en game
            <span className="bets-tab-count">{tickets.length}</span>
          </button>
        </div>

        {/* ── Filtres ── */}
        <div className="bets-filters">
          {[
            { key: 'all',       label: 'Tous' },
            { key: 'pending',   label: 'En cours' },
            { key: 'won',       label: 'Gagnés' },
            { key: 'lost',      label: 'Perdus' },
            { key: 'cancelled', label: 'Remboursés' },
          ].map(f => {
            const src = tab === 'esports' ? esportsBets : tickets
            const count = f.key === 'all'
              ? currentList.length
              : src.filter(x => (x.status || x.globalStatus) === f.key).length
            return (
              <button key={f.key} className={`filter-btn ${filter === f.key ? 'active' : ''}`} onClick={() => setFilter(f.key)}>
                {f.label}<span className="filter-count">{count}</span>
              </button>
            )
          })}
          {!loading && currentList.length > 0 && (
            <div className="bets-result-count">
              {currentList.length} ticket{currentList.length > 1 ? 's' : ''}
              {totalPages > 1 && ` · page ${page}/${totalPages}`}
            </div>
          )}
        </div>

        {/* ── Contenu ── */}
        {loading ? (
          <div className="bets-loading"><div className="bets-spinner" /><span>Chargement…</span></div>
        ) : currentList.length === 0 ? (
          <div className="bets-empty">
            <div className="bets-empty-icon">{tab === 'esports' ? '🏆' : '🎮'}</div>
            <div className="bets-empty-title">Aucun ticket trouvé</div>
            <div className="bets-empty-sub">
              {filter === 'all'
                ? tab === 'esports'
                  ? "Tu n'as pas encore parié sur des matchs officiels."
                  : "Tu n'as pas encore placé de pari en game."
                : `Aucun ticket « ${STATUS_CONFIG[filter]?.label} ».`}
            </div>
            {filter === 'all' && (
              <button className="bets-cta" onClick={() => navigate(tab === 'esports' ? '/bet-on-pros' : '/')}>
                {tab === 'esports' ? 'Voir les matchs →' : 'Voir les parties en direct →'}
                <span className="bets-cta-shimmer" />
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="bets-list">
              {tab === 'esports' ? (
                paginated.map((bet, i) => (
                  <EsportsBetRow key={bet.id} bet={bet} i={i} onCancel={b => setCancelModal(b)} />
                ))
              ) : (
                paginated.map((ticket, i) => {
                  const status = STATUS_CONFIG[ticket.globalStatus] || STATUS_CONFIG.pending
                  const isLive = ticket.game_status === 'live'
                  const game   = ticket.game
                  const ctx    = resolveGameCtx(ticket)

                  return (
                    <div key={ticket.key} className="ticket-row" style={{ animationDelay: `${i * 0.04}s` }}>
                      <div className="ticket-bar" style={{ background: status.color }} />

                      {/* Contexte game */}
                      <div className="ticket-game-ctx">
                        <div className={`ticket-badge ${isLive ? 'live' : 'ended'}`}>
                          {isLive && <span className="ticket-badge-dot" />}
                          {isLive ? 'LIVE' : 'Terminé'}
                        </div>
                        <div className="ticket-ctx-player">
                          <div className="ticket-ctx-avatar" style={{ borderColor: ctx.borderColor }}>
                            {ctx.imgUrl
                              ? <img src={ctx.imgUrl} alt={ctx.name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                              : <span>{ctx.initials}</span>}
                          </div>
                          <div className="ticket-ctx-info">
                            <div
                            className="ticket-ctx-name"
                            style={{ cursor: ctx.summonerName && ctx.tag ? 'pointer' : 'default' }}
                            onClick={() => {
                              if (!ctx.summonerName || !ctx.tag) return   // ← bloque si tag absent
                              navigate(`/player/${ctx.region}/${encodeURIComponent(ctx.summonerName)}/${ctx.tag}`)
                            }}
                          >
                            {ctx.name}
                          </div>
                            {ctx.sub && (
                              <div className="ticket-ctx-sub" style={{ color: ctx.subColor }}>{ctx.sub}</div>
                            )}
                          </div>
                        </div>
                        <div className="ticket-ctx-meta">
                          <span className="ticket-queue">{QUEUE_NAMES[game?.queue] || 'Ranked'}</span>
                          <span className="ticket-date">{timeAgo(ticket.created_at)}</span>
                        </div>
                        {/* Badge combiné */}
                        {ticket.isCombined && (
                          <div className="ticket-combined-badge">
                            🎰 Combiné ×{ticket.bets.length}
                          </div>
                        )}
                      </div>

                      {/* Sélections */}
                      <div className="ticket-body">
                        {ticket.bets.map((bet, j) => {
                          const betStatus = STATUS_CONFIG[bet.status] || STATUS_CONFIG.pending
                          const betPlayer = bet.game?.bet_player
                          const champName = betPlayer?.champion_name
                          const icon      = champIcon(champName)
                          const side      = betPlayer?.side
                          const sideColor = side === 'blue' ? '#378add' : '#ef4444'

                          return (
                            <div key={j} className="ticket-sel">
                              <div className="ticket-champ-wrap">
                                {icon
                                  ? <img src={icon} alt={champName} className="ticket-champ-icon" onError={e => { e.target.style.display = 'none' }} />
                                  : <div className="ticket-champ-placeholder">?</div>}
                                {side && <div className="ticket-side-dot" style={{ background: sideColor }} />}
                              </div>
                              <div className="ticket-sel-info">
                                <div className="ticket-sel-type">{BET_TYPE_LABELS[bet.bet_type] || bet.bet_type}</div>
                                <div className="ticket-sel-detail" style={{ color: sideColor || '#e8eaf0', fontWeight: 600 }}>
                                  {betValueLabel(bet.bet_value)}
                                </div>
                              </div>
                              {ticket.isCombined && (
                                <div className="ticket-sel-status" style={{ color: betStatus.color }}>{betStatus.icon}</div>
                              )}
                              <span className="ticket-sel-odds">{bet.odds ? `×${Number(bet.odds).toFixed(2)}` : '×2'}</span>
                            </div>
                          )
                        })}
                      </div>

                      {/* Finances + actions */}
                      <div className="ticket-right">
                        <div className="ticket-finances">
                          <div className="ticket-fin-row">
                            <span className="ticket-fin-lbl">Mise</span>
                            <span className="ticket-fin-val">{ticket.totalAmount.toLocaleString()} <span className="ticket-coin-lbl">coins</span></span>
                          </div>
                          {ticket.isCombined && (
                            <div className="ticket-fin-row">
                              <span className="ticket-fin-lbl">Cote combinée</span>
                              <span className="ticket-fin-val" style={{ color: '#c89b3c' }}>×{ticket.combinedOdds.toFixed(2)}</span>
                            </div>
                          )}
                          <div className="ticket-fin-row">
                            <span className="ticket-fin-lbl">
                              {ticket.globalStatus === 'won' ? 'Gagné' : ticket.globalStatus === 'lost' ? 'Perdu' : ticket.globalStatus === 'cancelled' ? 'Remboursé' : 'Potentiel'}
                            </span>
                            <span className="ticket-fin-val" style={{
                              color: ticket.globalStatus === 'won' ? '#65BD62' : ticket.globalStatus === 'lost' ? '#ef4444' : '#6b7280'
                            }}>
                              {ticket.globalStatus === 'won'
                                ? `+${ticket.totalPayout.toLocaleString()}`
                                : ticket.globalStatus === 'lost'
                                  ? `-${ticket.totalAmount.toLocaleString()}`
                                  : ticket.globalStatus === 'cancelled'
                                    ? `+${ticket.totalAmount.toLocaleString()}`
                                    : `~${Math.floor(ticket.totalAmount * ticket.combinedOdds).toLocaleString()}`
                              } <span className="ticket-coin-lbl">coins</span>
                            </span>
                          </div>
                        </div>
                        <div className="ticket-actions">
                          {isLive && ticket.live_game_id && (
                            <button className="ticket-live-btn" onClick={() => navigate(`/game/${ticket.live_game_id}`)}>
                              <span className="ticket-live-dot" />Voir la partie
                              <span className="ticket-live-shimmer" />
                            </button>
                          )}
                          <div className="ticket-status-badge" style={{ color: status.color, background: status.bg, borderColor: status.color + '28' }}>
                            {status.icon} {status.label}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {totalPages > 1 && (
              <div className="bets-pagination">
                <button className="page-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>←</button>
                {page > 2 && (
                  <><button className="page-btn" onClick={() => setPage(1)}>1</button>{page > 3 && <span className="page-dots">…</span>}</>
                )}
                {getVisiblePages().map(p => (
                  <button key={p} className={`page-btn ${p === page ? 'active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                ))}
                {page < totalPages - 1 && (
                  <>{page < totalPages - 2 && <span className="page-dots">…</span>}<button className="page-btn" onClick={() => setPage(totalPages)}>{totalPages}</button></>
                )}
                <button className="page-btn" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>→</button>
              </div>
            )}
          </>
        )}
      </div>

      {cancelModal && (
        <CancelModal bet={cancelModal} onConfirm={handleCancelEsportsBet} onClose={() => setCancelModal(null)} />
      )}
    </div>
  )
}