import './BetOnPros.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import MatchModal from './MatchModal'

// ─── Métadonnées ligues ───────────────────────────────────────
const LEAGUE_META = {
  lec:    { label: 'LEC',    color: '#00b4d8' },
  lck:    { label: 'LCK',    color: '#c89b3c' },
  lcs:    { label: 'LCS',    color: '#378add' },
  lpl:    { label: 'LPL',    color: '#ef4444' },
  lfl:    { label: 'LFL',    color: '#0099ff' },
  worlds: { label: 'Worlds', color: '#65BD62' },
  msi:    { label: 'MSI',    color: '#a855f7' },
}

// ─── Helpers ──────────────────────────────────────────────────
function timeUntil(dateStr) {
  if (!dateStr) return ''
  const diff = new Date(dateStr).getTime() - Date.now()
  if (diff < 0) return 'En cours'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (h > 24) return `dans ${Math.floor(h / 24)}j`
  if (h > 0)  return `dans ${h}h${m > 0 ? `${m}m` : ''}`
  return `dans ${m}m`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })
}

function getLeaguePriorityBySlug(slug) {
  const order = { lec: 0, lck: 1, lfl: 2, lcs: 3, lpl: 4, msi: 5, worlds: 6 }
  return order[slug] ?? 99
}

function getLeaguePriority(leagueName) {
  if (!leagueName) return 99
  const name = leagueName.toLowerCase()
  if (name === 'lec' || name.includes('emea')) return 0
  if (name === 'lck' || name.includes('korea')) return 1
  if (name.includes('française') || name === 'lfl') return 2
  if (name.includes('lcs')) return 3
  if (name.includes('lpl')) return 4
  if (name.includes('msi')) return 5
  if (name.includes('worlds') || name.includes('world championship')) return 6
  return 7
}

// ─── Match Card ───────────────────────────────────────────────
function MatchCard({ match, onBet }) {
  const t1         = match.teams[0]
  const t2         = match.teams[1]
  const state      = match.state
  const isLive     = state === 'inProgress'
  const isDone     = state === 'completed'
  const isTbd      = match.is_tbd === true || match.is_playable === false
  const isLocked   = isDone || isTbd
  const leagueMeta = LEAGUE_META[match.league?.slug?.toLowerCase()] || {}
  const lc         = leagueMeta.color || '#65BD62'
  const t1IsFav    = t1.odds <= t2.odds

  const handleClick = () => {
    if (isLocked) return
    onBet(match)
  }

  return (
    <div
      className={`bop-card ${isLive ? 'is-live' : ''} ${isDone ? 'is-done' : ''} ${isTbd ? 'is-tbd' : ''}`}
      onClick={handleClick}
      style={{ cursor: isLocked ? 'default' : 'pointer' }}
    >
      <div className="bop-card-accent" style={{ background: isLive ? `linear-gradient(90deg, ${lc}, #65BD62)` : `linear-gradient(90deg, ${lc}60, transparent)` }} />

      <div className="bop-card-meta">
        <div className="bop-card-league" style={{ color: lc }}>
          <span className="bop-card-league-dot" style={{ background: lc }} />
          {match.league?.name}
          {match.block_name && <span className="bop-card-block">· {match.block_name}</span>}
        </div>
        <div className={`bop-card-status ${isTbd ? 'tbd' : isLive ? 'live' : isDone ? 'done' : 'upcoming'}`}>
          {isLive && <span className="bop-card-live-dot" />}
          {isTbd ? 'À déterminer' : isLive ? 'LIVE' : isDone ? 'Terminé' : timeUntil(match.start_time)}
        </div>
      </div>

      <div className="bop-card-matchup">
        <div className={`bop-card-team ${isDone && t1.outcome === 'win' ? 'won' : ''} ${isDone && t1.outcome === 'loss' ? 'lost' : ''}`}>
          <div className="bop-card-logo">
            {t1.image
              ? <img src={t1.image} alt={t1.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              : <div className="bop-card-logo-placeholder">?</div>}
          </div>
          <div className="bop-card-team-name">{t1.code || 'TBD'}</div>
          {t1.record && (t1.record.wins || t1.record.losses) ? (
            <div className="bop-card-record">{t1.record.wins}W · {t1.record.losses}L</div>
          ) : null}
        </div>

        <div className="bop-card-center">
          {isLive || isDone ? (
            <div className="bop-card-score">
              <span className={t1.wins > t2.wins ? 'leading' : ''}>{t1.wins}</span>
              <span className="bop-card-score-sep">—</span>
              <span className={t2.wins > t1.wins ? 'leading' : ''}>{t2.wins}</span>
            </div>
          ) : (
            <>
              <div className="bop-card-bo">BO{match.bo}</div>
              <div className="bop-card-time">{formatDate(match.start_time)}</div>
            </>
          )}
        </div>

        <div className={`bop-card-team right ${isDone && t2.outcome === 'win' ? 'won' : ''} ${isDone && t2.outcome === 'loss' ? 'lost' : ''}`}>
          <div className="bop-card-logo">
            {t2.image
              ? <img src={t2.image} alt={t2.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              : <div className="bop-card-logo-placeholder">?</div>}
          </div>
          <div className="bop-card-team-name">{t2.code || 'TBD'}</div>
          {t2.record && (t2.record.wins || t2.record.losses) ? (
            <div className="bop-card-record">{t2.record.wins}W · {t2.record.losses}L</div>
          ) : null}
        </div>
      </div>

      {!isDone && !isTbd && (
        <div className="bop-card-odds-row">
          <div className={`bop-card-odd ${t1IsFav ? 'fav' : ''}`}>
            <span className="bop-card-odd-code">{t1.code}</span>
            <span className="bop-card-odd-val">×{t1.odds}</span>
            {t1IsFav && <span className="bop-card-fav-tag">favori</span>}
          </div>
          <div className="bop-card-odds-divider" />
          <div className={`bop-card-odd right ${!t1IsFav ? 'fav' : ''}`}>
            {!t1IsFav && <span className="bop-card-fav-tag">favori</span>}
            <span className="bop-card-odd-val">×{t2.odds}</span>
            <span className="bop-card-odd-code">{t2.code}</span>
          </div>
        </div>
      )}

      {isDone ? (
        <div className="bop-card-result">
          🏆 {t1.outcome === 'win' ? t1.code : t2.code} remporte le match
          <span className="bop-card-result-score">({t1.wins}—{t2.wins})</span>
        </div>
      ) : isTbd ? (
        <div className="bop-card-tbd-banner">
          <span className="bop-card-tbd-icon">⏳</span>
          <span>Équipes pas encore qualifiées</span>
        </div>
      ) : (
        <div className="bop-card-footer">
          {match.total_bets > 0 && (
            <span className="bop-card-bets">{match.total_bets} pari{match.total_bets > 1 ? 's' : ''}</span>
          )}
          <span className="bop-card-cta">Parier →</span>
        </div>
      )}
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────
export default function BetOnPros() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [matches,      setMatches]      = useState([])
  const [loading,      setLoading]      = useState(true)
  const [leagueFilter, setLeagueFilter] = useState('all')
  const [stateFilter,  setStateFilter]  = useState('upcoming')
  const [betModal,     setBetModal]     = useState(null)
  const [coins,        setCoins]        = useState(user?.coins || 0)

  const loadMatches = () => {
    setLoading(true)
    api.get('/esports/schedule')
      .then(r => setMatches(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    loadMatches()
    setCoins(user?.coins || 0)
  }, [user])

  const filtered = matches
    .filter(m => {
      const leagueOk = leagueFilter === 'all'
        || m.league_slug === leagueFilter
        || m.league?.slug?.toLowerCase() === leagueFilter

      const stateOk =
        stateFilter === 'all'      ||
        (stateFilter === 'upcoming' && m.state === 'unstarted') ||
        (stateFilter === 'live'     && m.state === 'inProgress') ||
        (stateFilter === 'done'     && m.state === 'completed')

      return leagueOk && stateOk
    })
    .sort((a, b) => {
      // Priorité ligue d'abord
      const leaguePrioA = getLeaguePriorityBySlug(a.league_slug)
      const leaguePrioB = getLeaguePriorityBySlug(b.league_slug)
      if (leaguePrioA !== leaguePrioB) return leaguePrioA - leaguePrioB

      // Puis state
      const stateOrder = { inProgress: 0, unstarted: 1, completed: 2 }
      const stateA = stateOrder[a.state] ?? 3
      const stateB = stateOrder[b.state] ?? 3
      if (stateA !== stateB) return stateA - stateB

      // TBD en bas dans les "upcoming"
      const aTbd = a.is_tbd === true || a.is_playable === false
      const bTbd = b.is_tbd === true || b.is_playable === false
      if (aTbd !== bTbd) return aTbd ? 1 : -1

      if (a.state === 'unstarted') return new Date(a.start_time || 0) - new Date(b.start_time || 0)
      return new Date(b.start_time || 0) - new Date(a.start_time || 0)
    })

  // Grouper par ligue avec ordre prioritaire
  const grouped = {}
  for (const m of filtered) {
    const key = m.league?.name || 'Autre'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(m)
  }

  const sortedLeagues = Object.entries(grouped).sort(([nameA], [nameB]) => {
    return getLeaguePriority(nameA) - getLeaguePriority(nameB)
  })

  const handleBetPlaced = () => {
    loadMatches()
    api.get('/coins/balance').then(r => setCoins(r.data.coins)).catch(() => {})
  }

  const liveCount     = matches.filter(m => m.state === 'inProgress').length
  const upcomingCount = matches.filter(m => m.state === 'unstarted' && !(m.is_tbd === true || m.is_playable === false)).length

  return (
    <div className="bop-page">
      <div className="bop-header">
        <div className="bop-header-inner">
          <div>
            <div className="bop-eyebrow">Jungle Gap</div>
            <div className="bop-title">Ligues Professionnelles</div>
            <div className="bop-sub">Paris sur les matchs officiels LEC · LCK · LFL · LCS · LPL · Worlds</div>
          </div>
          <div className="bop-header-right">
            {liveCount > 0 && (
              <div className="bop-live-badge">
                <span className="bop-live-dot" />
                {liveCount} live
              </div>
            )}
            <div className="bop-balance">
              <span className="bop-balance-dot" />
              <span className="bop-balance-val">{coins.toLocaleString()}</span>
              <span className="bop-balance-lbl">coins</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bop-content">
        <div className="bop-filters">
          <div className="bop-state-pills">
            {[
              { key: 'upcoming', label: 'À venir',  count: upcomingCount },
              { key: 'live',     label: '● Live',    count: liveCount     },
              { key: 'done',     label: 'Terminés',  count: null          },
              { key: 'all',      label: 'Tous',      count: null          },
            ].map(f => (
              <button key={f.key}
                className={`bop-pill ${stateFilter === f.key ? 'active' : ''} ${f.key === 'live' ? 'live-pill' : ''}`}
                onClick={() => setStateFilter(f.key)}>
                {f.label}
                {f.count > 0 && <span className="bop-pill-count">{f.count}</span>}
              </button>
            ))}
          </div>
          <div className="bop-league-pills">
            <button className={`bop-league-pill ${leagueFilter === 'all' ? 'active' : ''}`}
              onClick={() => setLeagueFilter('all')}>Toutes</button>
            {Object.entries(LEAGUE_META).map(([slug, meta]) => (
              <button key={slug}
                className={`bop-league-pill ${leagueFilter === slug ? 'active' : ''}`}
                style={{ '--lc': meta.color }}
                onClick={() => setLeagueFilter(slug)}>
                {meta.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="bop-loading">
            <div className="bop-spinner-lg" />
            <span>Chargement des matchs…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bop-empty">
            <div className="bop-empty-icon">🏆</div>
            <div className="bop-empty-title">Aucun match trouvé</div>
            <div className="bop-empty-sub">Essaie un autre filtre ou reviens plus tard.</div>
          </div>
        ) : (
          sortedLeagues.map(([leagueName, leagueMatches]) => (
            <div key={leagueName} className="bop-section">
              <div className="bop-section-header">
                <span className="bop-section-title">{leagueName}</span>
                <span className="bop-section-count">{leagueMatches.length} match{leagueMatches.length > 1 ? 's' : ''}</span>
              </div>
              <div className="bop-grid">
                {leagueMatches.map(m => (
                  <MatchCard key={m.match_id} match={m} onBet={setBetModal} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
      {betModal && (
        <MatchModal
          matchId={betModal.match_id}
          onClose={() => setBetModal(null)}
          onBetPlaced={handleBetPlaced}
        />
      )}
    </div>
  )
}