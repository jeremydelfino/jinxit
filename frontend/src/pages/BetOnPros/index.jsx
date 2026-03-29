import './BetOnPros.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const LEAGUE_META = {
  lec:    { label: 'LEC',    color: '#00b4d8' },
  lck:    { label: 'LCK',    color: '#c89b3c' },
  lcs:    { label: 'LCS',    color: '#378add' },
  lpl:    { label: 'LPL',    color: '#ef4444' },
  lfl:    { label: 'LFL',    color: '#0099ff' },
  worlds: { label: 'Worlds', color: '#65BD62' },
  msi:    { label: 'MSI',    color: '#a855f7' },
}

// Ordre d'affichage des ligues
const LEAGUE_ORDER = ['La Ligue Française', 'LCK', 'LCS', 'LPL', 'Worlds', 'MSI']
// LEC et LCK en premier
const PRIORITY_LEAGUES = ['League of Legends EMEA Championship', 'La Ligue Française de League of Legends', 'LEC', 'LCK']

const SCORE_OPTS = { 3: ['2-0', '2-1'], 5: ['3-0', '3-1', '3-2'], 1: ['1-0'] }

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

function getLeaguePriority(leagueName) {
  if (!leagueName) return 99
  const name = leagueName.toLowerCase()
  if (name.includes('emea') || name.includes('lec')) return 0
  if (name.includes('lck') || name.includes('korea')) return 1
  if (name.includes('lfl') || name.includes('française')) return 2
  if (name.includes('lcs')) return 3
  if (name.includes('lpl')) return 4
  if (name.includes('msi')) return 5
  if (name.includes('worlds') || name.includes('world championship')) return 6
  return 7
}

// ─── Modal redesignée ────────────────────────────────────────
function BetModal({ match, onClose, onBetPlaced }) {
  const { user } = useAuthStore()
  const [betType,  setBetType]  = useState('match_winner')
  const [betTeam,  setBetTeam]  = useState(null)
  const [betScore, setBetScore] = useState(null)
  const [amount,   setAmount]   = useState(100)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [success,  setSuccess]  = useState(false)

  const t1 = match.teams[0]
  const t2 = match.teams[1]
  const bo = match.bo
  const scoreOpts = SCORE_OPTS[bo] || SCORE_OPTS[3]
  const leagueMeta = LEAGUE_META[match.league?.slug?.toLowerCase()] || {}
  const lc = leagueMeta.color || '#65BD62'

  const getOdds = () => {
    if (!betTeam) return null
    if (betType === 'match_winner') return betTeam === 'team1' ? t1.odds : t2.odds
    if (betType === 'exact_score' && betScore) {
      const base = betTeam === 'team1' ? t1.odds : t2.odds
      const mult = match.score_multipliers?.[betScore] || 1.5
      return Math.min(8.0, parseFloat((base * mult).toFixed(2)))
    }
    return null
  }

  const odds         = getOdds()
  const potentialWin = odds ? Math.floor(amount * odds) : null
  const selectedTeam = betTeam === 'team1' ? t1 : betTeam === 'team2' ? t2 : null

  const buildBetValue = () => {
    if (betType === 'match_winner') return betTeam
    if (betType === 'exact_score')  return `${betTeam}_${betScore}`
    return null
  }

  const handleSubmit = async () => {
    if (!betTeam) return setError('Sélectionne une équipe')
    if (betType === 'exact_score' && !betScore) return setError('Sélectionne un score')
    if (amount < 10) return setError('Mise minimum 10 coins')
    if (amount > (user?.coins || 0)) return setError('Coins insuffisants')
    setError(''); setLoading(true)
    try {
      await api.post('/esports/bets/place', {
        match_id: match.match_id, bet_type: betType,
        bet_value: buildBetValue(), amount,
      })
      setSuccess(true)
      setTimeout(() => { onBetPlaced(); onClose() }, 1400)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors du pari')
    } finally { setLoading(false) }
  }

  return (
    <div className="bop-modal-overlay" onClick={onClose}>
      <div className="bop-modal" onClick={e => e.stopPropagation()}>

        {/* ── BAND HAUT colorée ── */}
        <div className="bop-modal-band" style={{ background: `linear-gradient(90deg, ${lc}30, transparent)` }}>
          <div className="bop-modal-band-league" style={{ color: lc }}>
            <span className="bop-modal-band-dot" style={{ background: lc }} />
            {match.league?.name}
            <span className="bop-modal-band-bo">· BO{bo}</span>
          </div>
          <button className="bop-modal-close" onClick={onClose}>✕</button>
        </div>

        {/* ── MATCHUP HERO — grands logos ── */}
        <div className="bop-modal-matchup">
          {/* Team 1 */}
          <div
            className={`bop-modal-team-hero ${betTeam === 'team1' ? 'selected' : ''}`}
            onClick={() => setBetTeam('team1')}
            style={{ '--tc': lc }}
          >
            <div className="bop-modal-team-logo-big">
              <img src={t1.image} alt={t1.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
            </div>
            <div className="bop-modal-team-code">{t1.code}</div>
            <div className="bop-modal-team-record">{t1.record?.wins ?? 0}W · {t1.record?.losses ?? 0}L</div>
            <div className="bop-modal-team-odds-pill" style={{
              background: betTeam === 'team1' ? lc + '20' : '#ffffff08',
              borderColor: betTeam === 'team1' ? lc + '50' : '#ffffff10',
              color: betTeam === 'team1' ? lc : '#e2b147',
            }}>×{t1.odds}</div>
            {betTeam === 'team1' && <div className="bop-modal-team-check" style={{ background: lc }}>✓</div>}
          </div>

          {/* Centre */}
          <div className="bop-modal-vs-block">
            <div className="bop-modal-vs-text">VS</div>
            <div className="bop-modal-vs-date">{formatDate(match.start_time)}</div>
          </div>

          {/* Team 2 */}
          <div
            className={`bop-modal-team-hero ${betTeam === 'team2' ? 'selected' : ''}`}
            onClick={() => setBetTeam('team2')}
            style={{ '--tc': lc }}
          >
            <div className="bop-modal-team-logo-big">
              <img src={t2.image} alt={t2.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
            </div>
            <div className="bop-modal-team-code">{t2.code}</div>
            <div className="bop-modal-team-record">{t2.record?.wins ?? 0}W · {t2.record?.losses ?? 0}L</div>
            <div className="bop-modal-team-odds-pill" style={{
              background: betTeam === 'team2' ? lc + '20' : '#ffffff08',
              borderColor: betTeam === 'team2' ? lc + '50' : '#ffffff10',
              color: betTeam === 'team2' ? lc : '#e2b147',
            }}>×{t2.odds}</div>
            {betTeam === 'team2' && <div className="bop-modal-team-check" style={{ background: lc }}>✓</div>}
          </div>
        </div>

        <div className="bop-modal-body">

          {/* ── TYPE PARI ── */}
          <div className="bop-modal-tabs">
            {[
              { key: 'match_winner', label: 'Vainqueur',   icon: '🏆' },
              { key: 'exact_score',  label: 'Score exact', icon: '📊' },
            ].map(bt => (
              <button key={bt.key}
                className={`bop-modal-tab ${betType === bt.key ? 'active' : ''}`}
                style={{ '--tc': lc }}
                onClick={() => { setBetType(bt.key); setBetScore(null) }}>
                <span>{bt.icon}</span> {bt.label}
              </button>
            ))}
          </div>

          {/* ── SCORE EXACT ── */}
          {betType === 'exact_score' && (
            <div className="bop-modal-scores-wrap">
              {betTeam ? (
                <div className="bop-modal-scores">
                  {scoreOpts.map(s => {
                    const [a, b]  = s.split('-')
                    const display = betTeam === 'team1' ? `${a} — ${b}` : `${b} — ${a}`
                    const mult    = match.score_multipliers?.[s] || 1.5
                    const active  = betScore === s
                    return (
                      <button key={s}
                        className={`bop-modal-score-opt ${active ? 'active' : ''}`}
                        style={{ '--tc': lc }}
                        onClick={() => setBetScore(s)}>
                        <span className="bop-score-display">{display}</span>
                        <span className="bop-score-mult" style={{ color: active ? lc : '#e2b147' }}>×{(t1.odds * mult).toFixed(2)}</span>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="bop-modal-hint">← Sélectionne d'abord une équipe</div>
              )}
            </div>
          )}

          {/* ── MISE ── */}
          <div className="bop-modal-stake-section">
            <div className="bop-modal-section-label">Mise</div>
            <div className="bop-modal-presets">
              {[50, 100, 250, 500, 1000].map(v => (
                <button key={v}
                  className={`bop-modal-preset-btn ${amount === v ? 'active' : ''}`}
                  style={{ '--tc': lc }}
                  onClick={() => setAmount(v)}>
                  {v}
                </button>
              ))}
            </div>
            <div className="bop-modal-input-row">
              <input
                className="bop-modal-input"
                type="number" min={10} max={user?.coins || 0}
                value={amount}
                onChange={e => setAmount(Math.max(10, parseInt(e.target.value) || 10))}
                style={{ '--tc': lc }}
              />
              <span className="bop-modal-input-label">coins</span>
              <span className="bop-modal-balance">/ {user?.coins?.toLocaleString()}</span>
            </div>
          </div>

          {/* ── RÉCAP GAIN ── */}
          {odds && selectedTeam ? (
            <div className="bop-modal-gain-recap" style={{ borderColor: lc + '25', background: lc + '08' }}>
              <div className="bop-modal-gain-left">
                <img src={selectedTeam.image} alt={selectedTeam.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                <div>
                  <div className="bop-modal-gain-team">{selectedTeam.code}</div>
                  {betScore && (
                    <div className="bop-modal-gain-score" style={{ color: lc }}>
                      {betTeam === 'team1' ? betScore : betScore.split('-').reverse().join('-')}
                    </div>
                  )}
                </div>
              </div>
              <div className="bop-modal-gain-right">
                <div className="bop-modal-gain-label">Gain potentiel</div>
                <div className="bop-modal-gain-amount" style={{ color: lc }}>
                  +{potentialWin?.toLocaleString()}
                  <span className="bop-modal-gain-coins">coins</span>
                </div>
                <div className="bop-modal-gain-odds">cote ×{odds}</div>
              </div>
            </div>
          ) : (
            <div className="bop-modal-gain-empty">
              Sélectionne une équipe pour voir le gain potentiel
            </div>
          )}

          {error && <div className="bop-modal-error">{error}</div>}

          {success ? (
            <div className="bop-modal-success">
              <span>✓</span> Pari enregistré !
            </div>
          ) : (
            <button
              className="bop-modal-confirm"
              onClick={handleSubmit}
              disabled={loading || !betTeam || (betType === 'exact_score' && !betScore)}
              style={{ '--tc': lc }}
            >
              {loading ? (
                <span className="bop-modal-spinner" />
              ) : (
                <>
                  <span>Confirmer le pari</span>
                  <span className="bop-modal-confirm-amount">{amount.toLocaleString()} coins</span>
                </>
              )}
              <span className="bop-modal-confirm-shimmer" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Match Card ───────────────────────────────────────────────
function MatchCard({ match, onBet }) {
  const t1         = match.teams[0]
  const t2         = match.teams[1]
  const state      = match.state
  const isLive     = state === 'inProgress'
  const isDone     = state === 'completed'
  const leagueMeta = LEAGUE_META[match.league?.slug?.toLowerCase()] || {}
  const lc         = leagueMeta.color || '#65BD62'
  const t1IsFav    = t1.odds <= t2.odds

  return (
    <div
      className={`bop-card ${isLive ? 'is-live' : ''} ${isDone ? 'is-done' : ''}`}
      onClick={!isDone ? () => onBet(match) : undefined}
      style={{ cursor: isDone ? 'default' : 'pointer' }}
    >
      <div className="bop-card-accent" style={{ background: isLive ? `linear-gradient(90deg, ${lc}, #65BD62)` : `linear-gradient(90deg, ${lc}60, transparent)` }} />

      <div className="bop-card-meta">
        <div className="bop-card-league" style={{ color: lc }}>
          <span className="bop-card-league-dot" style={{ background: lc }} />
          {match.league?.name}
          {match.block_name && <span className="bop-card-block">· {match.block_name}</span>}
        </div>
        <div className={`bop-card-status ${isLive ? 'live' : isDone ? 'done' : 'upcoming'}`}>
          {isLive && <span className="bop-card-live-dot" />}
          {isLive ? 'LIVE' : isDone ? 'Terminé' : timeUntil(match.start_time)}
        </div>
      </div>

      <div className="bop-card-matchup">
        <div className={`bop-card-team ${isDone && t1.outcome === 'win' ? 'won' : ''} ${isDone && t1.outcome === 'loss' ? 'lost' : ''}`}>
          <div className="bop-card-logo">
            <img src={t1.image} alt={t1.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          </div>
          <div className="bop-card-team-name">{t1.code}</div>
          {t1.record && <div className="bop-card-record">{t1.record.wins}W · {t1.record.losses}L</div>}
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
            <img src={t2.image} alt={t2.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          </div>
          <div className="bop-card-team-name">{t2.code}</div>
          {t2.record && <div className="bop-card-record">{t2.record.wins}W · {t2.record.losses}L</div>}
        </div>
      </div>

      {!isDone && (
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
      const leagueOk = leagueFilter === 'all' || m.league?.slug?.toLowerCase() === leagueFilter
      const stateOk  =
        stateFilter === 'all'      ||
        (stateFilter === 'upcoming' && m.state === 'unstarted') ||
        (stateFilter === 'live'     && m.state === 'inProgress') ||
        (stateFilter === 'done'     && m.state === 'completed')
      return leagueOk && stateOk
    })
    .sort((a, b) => {
      // Live en premier
      if (a.state === 'inProgress' && b.state !== 'inProgress') return -1
      if (b.state === 'inProgress' && a.state !== 'inProgress') return  1
      // Upcoming : plus proche en premier
      if (a.state === 'unstarted' && b.state === 'unstarted') {
        return new Date(a.start_time || 0) - new Date(b.start_time || 0)
      }
      // Completed : plus récent en premier
      return new Date(b.start_time || 0) - new Date(a.start_time || 0)
    })
    .slice(0, 40)

  // Grouper par ligue avec ordre prioritaire
  const grouped = {}
  for (const m of filtered) {
    const key = m.league?.name || 'Autre'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(m)
  }

  // Trier les ligues : LEC et LCK en premier
  const sortedLeagues = Object.entries(grouped).sort(([nameA], [nameB]) => {
    return getLeaguePriority(nameA) - getLeaguePriority(nameB)
  })

  const handleBetPlaced = () => {
    loadMatches()
    api.get('/coins/balance').then(r => setCoins(r.data.coins)).catch(() => {})
  }

  const liveCount     = matches.filter(m => m.state === 'inProgress').length
  const upcomingCount = matches.filter(m => m.state === 'unstarted').length

  return (
    <div className="bop-page">
      <div className="bop-header">
        <div className="bop-header-inner">
          <div>
            <div className="bop-eyebrow">Jungle Gap</div>
            <div className="bop-title">BetOnPros</div>
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
        <BetModal match={betModal} onClose={() => setBetModal(null)} onBetPlaced={handleBetPlaced} />
      )}
    </div>
  )
}