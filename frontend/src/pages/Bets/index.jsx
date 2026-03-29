import './Bets.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV      = '14.24.1'
const PER_PAGE = 8

const STATUS_CONFIG = {
  pending:   { label: 'En cours', color: '#f59e0b', bg: '#f59e0b12', icon: '⏳' },
  won:       { label: 'Gagné',    color: '#65BD62', bg: '#65BD6212', icon: '✓'  },
  lost:      { label: 'Perdu',    color: '#ef4444', bg: '#ef444412', icon: '✗'  },
  cancelled: { label: 'Annulé',   color: '#6b7280', bg: '#6b728012', icon: '—'  },
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
  who_wins:     'Victoire',
  first_blood:  'First Blood',
  match_winner: 'Vainqueur',
  exact_score:  'Score exact',
}

const QUEUE_NAMES = {
  '420': 'Ranked Solo',
  '440': 'Ranked Flex',
  '400': 'Normal',
  '450': 'ARAM',
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h    = Math.floor(diff / 3600000)
  const m    = Math.floor(diff / 60000)
  if (h > 24) return `il y a ${Math.floor(h / 24)}j`
  if (h > 0)  return `il y a ${h}h`
  if (m > 0)  return `il y a ${m}m`
  return "à l'instant"
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

function champIcon(name) {
  if (!name) return null
  return `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${name}.png`
}

function groupBetsByGame(bets) {
  const groups = {}
  for (const bet of bets) {
    const key = bet.live_game_id ?? `solo_${bet.id}`
    if (!groups[key]) groups[key] = []
    groups[key].push(bet)
  }
  return Object.values(groups)
    .map(group => {
      const statuses    = group.map(b => b.status)
      let globalStatus  = 'pending'
      if (statuses.every(s => s === 'won'))         globalStatus = 'won'
      else if (statuses.some(s => s === 'lost'))    globalStatus = 'lost'
      else if (statuses.some(s => s === 'pending')) globalStatus = 'pending'
      else globalStatus = 'cancelled'
      const totalAmount = group.reduce((acc, b) => acc + b.amount, 0)
      const totalPayout = group.reduce((acc, b) => acc + (b.payout || 0), 0)
      return {
        key:          group[0].live_game_id ?? `solo_${group[0].id}`,
        live_game_id: group[0].live_game_id,
        game_status:  group[0].game_status,
        game:         group[0].game,
        bets:         group,
        globalStatus,
        totalAmount,
        totalPayout,
        odds:         Math.pow(2, group.length),
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
      type: 'pro', name: pro.name, sub: pro.team,
      subColor: pro.accent_color || '#65BD62',
      imgUrl: pro.photo_url,
      initials: pro.name.slice(0, 2).toUpperCase(),
      borderColor: pro.accent_color || '#65BD62',
    }
  }
  const firstBet  = ticket.bets[0]
  const betPlayer = firstBet?.game?.bet_player
  const sumName   = betPlayer?.summoner_name || null
  return {
    type: 'casual', name: sumName || 'Joueur inconnu',
    sub: QUEUE_NAMES[game?.queue] || 'Ranked',
    subColor: '#6b7280', imgUrl: null,
    initials: sumName ? sumName.slice(0, 2).toUpperCase() : '?',
    borderColor: '#ffffff20',
    summonerName: sumName, region: betPlayer?.region, tag: betPlayer?.tag_line,
  }
}

function parseBetLabel(bet_value, team1_code, team2_code) {
  if (!bet_value) return '—'
  if (bet_value === 'team1') return team1_code
  if (bet_value === 'team2') return team2_code
  // exact_score : "team1_2-0"
  const parts = bet_value.split('_')
  if (parts.length === 2) {
    const winner = parts[0] === 'team1' ? team1_code : team2_code
    const loser  = parts[0] === 'team1' ? team2_code : team1_code
    const [a, b] = parts[1].split('-')
    return `${winner} ${a}—${b} ${loser}`
  }
  return bet_value
}

// ─── Ticket Esports ──────────────────────────────────────────
function EsportsBetRow({ bet, onCancel, i }) {
  const status  = STATUS_CONFIG[bet.status] || STATUS_CONFIG.pending
  const lm      = LEAGUE_META[bet.league_slug?.toLowerCase()] || {}
  const lc      = lm.color || '#65BD62'
  const isPending = bet.status === 'pending'

  const betLabel = parseBetLabel(bet.bet_value, bet.team1_code, bet.team2_code)
  const betType  = BET_TYPE_LABELS[bet.bet_type] || bet.bet_type

  return (
    <div className="esbet-row" style={{ animationDelay: `${i * 0.04}s` }}>
      <div className="esbet-bar" style={{ background: status.color }} />

      {/* ── Contexte match ── */}
      <div className="esbet-ctx">
        <div className="esbet-league" style={{ color: lc }}>
          <span className="esbet-league-dot" style={{ background: lc }} />
          {bet.league_name || lm.label || bet.league_slug?.toUpperCase()}
        </div>
        <div className="esbet-teams">
          <img
            src={bet.team1_image} alt={bet.team1_code}
            className="esbet-team-logo"
            referrerPolicy="no-referrer"
            onError={e => { e.target.style.display = 'none' }}
          />
          <span className="esbet-team-code">{bet.team1_code}</span>
          <span className="esbet-vs">vs</span>
          <span className="esbet-team-code">{bet.team2_code}</span>
          <img
            src={bet.team2_image} alt={bet.team2_code}
            className="esbet-team-logo"
            referrerPolicy="no-referrer"
            onError={e => { e.target.style.display = 'none' }}
          />
        </div>
        <div className="esbet-meta">
          <span className="esbet-bo">BO{bet.bo_format}</span>
          {bet.match_start_time && (
            <span className="esbet-date">{formatDate(bet.match_start_time)}</span>
          )}
        </div>
      </div>

      {/* ── Sélection ── */}
      <div className="esbet-body">
        <div className="esbet-sel-type">{betType}</div>
        <div className="esbet-sel-value" style={{ color: lc }}>{betLabel}</div>
        <div className="esbet-odds-row">
          <span className="esbet-odds-lbl">Cote</span>
          <span className="esbet-odds-val">×{bet.odds?.toFixed(2)}</span>
        </div>
      </div>

      {/* ── Finances + actions ── */}
      <div className="esbet-right">
        <div className="esbet-finances">
          <div className="esbet-fin-row">
            <span className="esbet-fin-lbl">Mise</span>
            <span className="esbet-fin-val">{bet.amount?.toLocaleString()} <span className="esbet-coin">coins</span></span>
          </div>
          <div className="esbet-fin-row">
            <span className="esbet-fin-lbl">
              {bet.status === 'won' ? 'Gagné' : bet.status === 'lost' ? 'Perdu' : 'Potentiel'}
            </span>
            <span className="esbet-fin-val" style={{
              color: bet.status === 'won'  ? '#65BD62'
                   : bet.status === 'lost' ? '#ef4444'
                   : '#6b7280'
            }}>
              {bet.status === 'won'
                ? `+${bet.payout?.toLocaleString()}`
                : bet.status === 'lost'
                  ? `-${bet.amount?.toLocaleString()}`
                  : `~${Math.floor((bet.amount || 0) * (bet.odds || 1)).toLocaleString()}`
              } <span className="esbet-coin">coins</span>
            </span>
          </div>
        </div>

        <div className="esbet-actions">
          {isPending && (
            <button className="esbet-cancel-btn" onClick={() => onCancel(bet)}>
              Annuler
            </button>
          )}
          <div className="esbet-status-badge" style={{ color: status.color, background: status.bg, borderColor: status.color + '28' }}>
            {status.icon} {status.label}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Modale confirmation annulation ──────────────────────────
function CancelModal({ bet, onConfirm, onClose }) {
  const [loading, setLoading] = useState(false)
  const lm = LEAGUE_META[bet.league_slug?.toLowerCase()] || {}
  const lc = lm.color || '#65BD62'

  const handleConfirm = async () => {
    setLoading(true)
    await onConfirm(bet.id)
    setLoading(false)
  }

  return (
    <div className="cancel-overlay" onClick={onClose}>
      <div className="cancel-modal" onClick={e => e.stopPropagation()}>
        <div className="cancel-modal-icon">⚠️</div>
        <div className="cancel-modal-title">Annuler ce pari ?</div>
        <div className="cancel-modal-sub">Tu seras remboursé intégralement.</div>

        <div className="cancel-modal-recap" style={{ borderColor: lc + '25', background: lc + '08' }}>
          <div className="cancel-recap-teams">
            <img src={bet.team1_image} alt={bet.team1_code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
            <span className="cancel-recap-code">{bet.team1_code}</span>
            <span className="cancel-recap-vs">vs</span>
            <span className="cancel-recap-code">{bet.team2_code}</span>
            <img src={bet.team2_image} alt={bet.team2_code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          </div>
          <div className="cancel-recap-amount">
            <span className="cancel-recap-lbl">Remboursement</span>
            <span className="cancel-recap-val" style={{ color: '#65BD62' }}>+{bet.amount?.toLocaleString()} coins</span>
          </div>
        </div>

        <div className="cancel-modal-btns">
          <button className="cancel-btn-secondary" onClick={onClose}>Garder le pari</button>
          <button className="cancel-btn-primary" onClick={handleConfirm} disabled={loading}>
            {loading ? <span className="cancel-spinner" /> : 'Confirmer l\'annulation'}
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

  const [bets,         setBets]         = useState([])
  const [esportsBets,  setEsportsBets]  = useState([])
  const [loading,      setLoading]      = useState(true)
  const [filter,       setFilter]       = useState('all')
  const [tab,          setTab]          = useState('esports') // 'esports' | 'games'
  const [page,         setPage]         = useState(1)
  const [cancelModal,  setCancelModal]  = useState(null)

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    Promise.all([
      api.get('/bets/my-bets'),
      api.get('/esports/bets/my-bets'),
    ]).then(([r1, r2]) => {
      setBets(r1.data)
      setEsportsBets(r2.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [user])

  useEffect(() => { setPage(1) }, [filter, tab])

  const handleCancelEsportsBet = async (betId) => {
    try {
      await api.post(`/esports/bets/${betId}/cancel`)
      setEsportsBets(prev => prev.map(b =>
        b.id === betId ? { ...b, status: 'cancelled' } : b
      ))
      setCancelModal(null)
    } catch (err) {
      alert(err.response?.data?.detail || 'Erreur lors de l\'annulation')
    }
  }

  // ── Stats globales ──────────────────────────────────────────
  const tickets        = groupBetsByGame(bets)
  const filteredGame   = filter === 'all' ? tickets : tickets.filter(t => t.globalStatus === filter)
  const filteredEsport = filter === 'all' ? esportsBets : esportsBets.filter(b => b.status === filter)

  const allWon     = [...tickets.filter(t => t.globalStatus === 'won'), ...esportsBets.filter(b => b.status === 'won')]
  const allLost    = [...tickets.filter(t => t.globalStatus === 'lost'), ...esportsBets.filter(b => b.status === 'lost')]
  const allPending = [...tickets.filter(t => t.globalStatus === 'pending'), ...esportsBets.filter(b => b.status === 'pending')]
  const totalGains = allWon.reduce((acc, b) => acc + (b.totalPayout || b.payout || 0), 0)
  const resolved   = allWon.length + allLost.length
  const winrate    = resolved > 0 ? Math.round((allWon.length / resolved) * 100) : 0

  const stats = {
    total:   tickets.length + esportsBets.length,
    pending: allPending.length,
    won:     allWon.length,
    lost:    allLost.length,
    gains:   totalGains,
    winrate,
  }

  // ── Pagination ──────────────────────────────────────────────
  const currentList  = tab === 'esports' ? filteredEsport : filteredGame
  const totalPages   = Math.ceil(currentList.length / PER_PAGE)
  const paginated    = currentList.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const getVisiblePages = () => {
    const pages = []
    const start = Math.max(1, page - 1)
    const end   = Math.min(totalPages, page + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    return pages
  }

  return (
    <div className="bets-page">

      {/* ── HEADER ── */}
      <div className="bets-header">
        <div className="bets-header-inner">
          <div>
            <div className="bets-eyebrow">Jungle Gap</div>
            <div className="bets-title">Mes paris</div>
            <div className="bets-sub">Historique de tous tes tickets</div>
          </div>
          <div className="bets-balance">
            <span className="bets-balance-dot" />
            <span className="bets-balance-val">{user?.coins?.toLocaleString()}</span>
            <span className="bets-balance-lbl">coins</span>
          </div>
        </div>
      </div>

      <div className="bets-content">

        {/* ── STATS ── */}
        <div className="bets-stats">
          {[
            { val: stats.total,                       label: 'Total',    color: '#e8eaf0' },
            { val: stats.pending,                     label: 'En cours', color: '#f59e0b' },
            { val: stats.won,                         label: 'Gagnés',   color: '#65BD62' },
            { val: stats.lost,                        label: 'Perdus',   color: '#ef4444' },
            { val: `+${stats.gains.toLocaleString()}`, label: 'Gains',   color: '#e2b147' },
            { val: `${stats.winrate}%`,               label: 'Win rate', color: '#65BD62' },
          ].map((s, i) => (
            <div className="bets-stat-card" key={i}>
              <div className="bst-val" style={{ color: s.color }}>{s.val}</div>
              <div className="bst-label">{s.label}</div>
            </div>
          ))}
        </div>

        {/* ── TABS ── */}
        <div className="bets-tabs">
          <button
            className={`bets-tab ${tab === 'esports' ? 'active' : ''}`}
            onClick={() => setTab('esports')}
          >
            <span className="bets-tab-icon">🏆</span>
            Paris officiels
            <span className="bets-tab-count">{esportsBets.length}</span>
          </button>
          <button
            className={`bets-tab ${tab === 'games' ? 'active' : ''}`}
            onClick={() => setTab('games')}
          >
            <span className="bets-tab-icon">🎮</span>
            Paris en game
            <span className="bets-tab-count">{tickets.length}</span>
          </button>
        </div>

        {/* ── FILTRES ── */}
        <div className="bets-filters">
          {[
            { key: 'all',     label: 'Tous',     count: currentList.length },
            { key: 'pending', label: 'En cours', count: tab === 'esports' ? esportsBets.filter(b => b.status === 'pending').length : tickets.filter(t => t.globalStatus === 'pending').length },
            { key: 'won',     label: 'Gagnés',   count: tab === 'esports' ? esportsBets.filter(b => b.status === 'won').length    : tickets.filter(t => t.globalStatus === 'won').length    },
            { key: 'lost',    label: 'Perdus',   count: tab === 'esports' ? esportsBets.filter(b => b.status === 'lost').length   : tickets.filter(t => t.globalStatus === 'lost').length   },
          ].map(f => (
            <button key={f.key} className={`filter-btn ${filter === f.key ? 'active' : ''}`} onClick={() => setFilter(f.key)}>
              {f.label}
              <span className="filter-count">{f.count}</span>
            </button>
          ))}
          {!loading && currentList.length > 0 && (
            <div className="bets-result-count">
              {currentList.length} ticket{currentList.length > 1 ? 's' : ''}
              {totalPages > 1 && ` · page ${page}/${totalPages}`}
            </div>
          )}
        </div>

        {/* ── CONTENU ── */}
        {loading ? (
          <div className="bets-loading">
            <div className="bets-spinner" />
            <span>Chargement…</span>
          </div>
        ) : currentList.length === 0 ? (
          <div className="bets-empty">
            <div className="bets-empty-icon">{tab === 'esports' ? '🏆' : '🎮'}</div>
            <div className="bets-empty-title">Aucun ticket trouvé</div>
            <div className="bets-empty-sub">
              {filter === 'all'
                ? tab === 'esports' ? "Tu n'as pas encore parié sur des matchs officiels." : "Tu n'as pas encore placé de pari en game."
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
                  <EsportsBetRow
                    key={bet.id}
                    bet={bet}
                    i={i}
                    onCancel={b => setCancelModal(b)}
                  />
                ))
              ) : (
                paginated.map((ticket, i) => {
                  const status = STATUS_CONFIG[ticket.globalStatus] || STATUS_CONFIG.pending
                  const isLive = ticket.game_status === 'live'
                  const game   = ticket.game
                  const queue  = QUEUE_NAMES[game?.queue] || 'Ranked'
                  const ctx    = resolveGameCtx(ticket)

                  return (
                    <div key={ticket.key} className="ticket-row" style={{ animationDelay: `${i * 0.04}s` }}>
                      <div className="ticket-bar" style={{ background: status.color }} />
                      <div className="ticket-game-ctx">
                        <div className={`ticket-badge ${isLive ? 'live' : 'ended'}`}>
                          {isLive && <span className="ticket-badge-dot" />}
                          {isLive ? 'LIVE' : 'Terminé'}
                        </div>
                        <div className="ticket-ctx-player">
                          <div className="ticket-ctx-avatar" style={{ borderColor: ctx.borderColor }}>
                            {ctx.imgUrl ? (
                              <img src={ctx.imgUrl} alt={ctx.name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                            ) : <span>{ctx.initials}</span>}
                          </div>
                          <div className="ticket-ctx-info">
                            <div className="ticket-ctx-name"
                              style={ctx.type === 'casual' && ctx.summonerName ? { cursor: 'pointer' } : {}}
                              onClick={() => {
                                if (ctx.type === 'casual' && ctx.summonerName && ctx.region)
                                  navigate(`/player/${ctx.region}/${encodeURIComponent(ctx.summonerName)}/${ctx.tag || 'EUW'}`)
                              }}>
                              {ctx.name}
                            </div>
                            <div className="ticket-ctx-sub" style={{ color: ctx.subColor }}>{ctx.sub}</div>
                          </div>
                        </div>
                        <div className="ticket-ctx-meta">
                          <span className="ticket-queue">{queue}</span>
                          <span className="ticket-date">{timeAgo(ticket.created_at)}</span>
                        </div>
                      </div>
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
                                {icon ? (
                                  <img src={icon} alt={champName} className="ticket-champ-icon" onError={e => { e.target.style.display = 'none' }} />
                                ) : (
                                  <div className="ticket-champ-placeholder">?</div>
                                )}
                                {side && <div className="ticket-side-dot" style={{ background: sideColor }} />}
                              </div>
                              <div className="ticket-sel-info">
                                <div className="ticket-sel-type">{BET_TYPE_LABELS[bet.bet_type] || bet.bet_type}</div>
                                <div className="ticket-sel-detail">
                                  {bet.bet_type === 'who_wins' && (
                                    <span style={{ color: sideColor, fontWeight: 700 }}>
                                      {bet.bet_value === 'blue' ? 'Blue side' : 'Red side'}
                                    </span>
                                  )}
                                  {bet.bet_type === 'first_blood' && champName && (
                                    <span style={{ color: '#e8eaf0', fontWeight: 600 }}>{champName}</span>
                                  )}
                                </div>
                              </div>
                              {ticket.bets.length > 1 && (
                                <div className="ticket-sel-status" style={{ color: betStatus.color }}>{betStatus.icon}</div>
                              )}
                              <span className="ticket-sel-odds">×2</span>
                            </div>
                          )
                        })}
                      </div>
                      <div className="ticket-right">
                        <div className="ticket-finances">
                          <div className="ticket-fin-row">
                            <span className="ticket-fin-lbl">Mise</span>
                            <span className="ticket-fin-val">{ticket.totalAmount.toLocaleString()} <span className="ticket-coin-lbl">coins</span></span>
                          </div>
                          <div className="ticket-fin-row">
                            <span className="ticket-fin-lbl">
                              {ticket.globalStatus === 'won' ? 'Gagné' : ticket.globalStatus === 'lost' ? 'Perdu' : 'Potentiel'}
                            </span>
                            <span className="ticket-fin-val" style={{
                              color: ticket.globalStatus === 'won' ? '#65BD62' : ticket.globalStatus === 'lost' ? '#ef4444' : '#6b7280'
                            }}>
                              {ticket.globalStatus === 'won'
                                ? `+${ticket.totalPayout.toLocaleString()}`
                                : ticket.globalStatus === 'lost'
                                  ? `-${ticket.totalAmount.toLocaleString()}`
                                  : `~${Math.floor(ticket.totalAmount * ticket.odds).toLocaleString()}`
                              } <span className="ticket-coin-lbl">coins</span>
                            </span>
                          </div>
                        </div>
                        <div className="ticket-actions">
                          {isLive && ticket.live_game_id && (
                            <button className="ticket-live-btn" onClick={() => navigate(`/game/${ticket.live_game_id}`)}>
                              <span className="ticket-live-dot" />
                              Voir la partie
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
                {page > 2 && <><button className="page-btn" onClick={() => setPage(1)}>1</button>{page > 3 && <span className="page-dots">…</span>}</>}
                {getVisiblePages().map(p => (
                  <button key={p} className={`page-btn ${p === page ? 'active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                ))}
                {page < totalPages - 1 && <>{page < totalPages - 2 && <span className="page-dots">…</span>}<button className="page-btn" onClick={() => setPage(totalPages)}>{totalPages}</button></>}
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