import { useState, useEffect } from 'react'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import './MatchModal.css'

// ─── Constantes ───────────────────────────────────────────────
const LEAGUE_META = {
  lec:    { label: 'LEC',    color: '#00b4d8' },
  lck:    { label: 'LCK',    color: '#c89b3c' },
  lcs:    { label: 'LCS',    color: '#378add' },
  lpl:    { label: 'LPL',    color: '#ef4444' },
  lfl:    { label: 'LFL',    color: '#0099ff' },
  worlds: { label: 'Worlds', color: '#65BD62' },
  msi:    { label: 'MSI',    color: '#a855f7' },
}

const ROLE_ORDER  = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
const ROLE_ICONS  = { TOP: '🛡️', JUNGLE: '🌿', MID: '⚡', ADC: '🏹', SUPPORT: '💙' }
const ROLE_LABELS = { TOP: 'TOP', JUNGLE: 'JUNGLE', MIDDLE: 'MID', MID: 'MID', BOTTOM: 'ADC', ADC: 'ADC', UTILITY: 'SUPPORT', SUPPORT: 'SUPPORT' }
const SCORE_OPTS  = { 3: ['2-0', '2-1'], 5: ['3-0', '3-1', '3-2'], 1: ['1-0'] }

// ─── Helpers ──────────────────────────────────────────────────
function normRole(r) { return r ? (ROLE_LABELS[r.toUpperCase()] ?? r.toUpperCase()) : 'FILL' }

function sortRoster(roster) {
  if (!roster) return []
  return [...roster].sort((a, b) => {
    const ra = ROLE_ORDER.indexOf(normRole(a.role))
    const rb = ROLE_ORDER.indexOf(normRole(b.role))
    return (ra === -1 ? 99 : ra) - (rb === -1 ? 99 : rb)
  })
}

function formatDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleDateString('fr-FR', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatRelativeDate(s) {
  if (!s) return ''
  const diff = (Date.now() - new Date(s).getTime()) / 86400000
  if (diff < 1)  return "aujourd'hui"
  if (diff < 2)  return 'hier'
  if (diff < 7)  return `il y a ${Math.floor(diff)}j`
  if (diff < 30) return `il y a ${Math.floor(diff / 7)}sem`
  return new Date(s).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}

function streakInfo(streak) {
  if (streak > 0) return { txt: `${streak}W`,           cls: 'win'  }
  if (streak < 0) return { txt: `${Math.abs(streak)}L`, cls: 'loss' }
  return { txt: '—', cls: 'neutral' }
}

// ─── Sous-composants ──────────────────────────────────────────
function FormBadges({ last5 }) {
  if (!last5) return <span className="mm-form-empty">—</span>
  return (
    <div className="mm-form-badges">
      {last5.split('').map((r, i) => (
        <span key={i}
          className={`mm-form-badge ${r === 'W' ? 'win' : 'loss'}`}
          style={{ animationDelay: `${i * 60}ms` }}>
          {r}
        </span>
      ))}
    </div>
  )
}

function PlayerCell({ player, side, delay }) {
  const role = normRole(player?.role)
  const initials = (player?.summoner_name || '??').slice(0, 2).toUpperCase()
  return (
    <div className={`mm-pl-cell mm-pl-${side}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="mm-pl-photo-wrap">
        <div className={`mm-pl-photo-glow ${side}`} />
        <div className={`mm-pl-photo ${side}`}>
          {player?.photo_url
            ? <img src={player.photo_url} alt={player.summoner_name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
            : <span>{initials}</span>}
        </div>
      </div>
      <div className="mm-pl-info">
        <div className="mm-pl-name">{player?.summoner_name || '—'}</div>
        <div className={`mm-pl-role ${side}`}>
          <span>{ROLE_ICONS[role] || '❓'}</span>
          <span>{role}</span>
        </div>
      </div>
    </div>
  )
}

function StatComparator({ t1, t2, lc }) {
  const t1WR    = Math.round((t1.season?.winrate ?? 50))
  const t2WR    = Math.round((t2.season?.winrate ?? 50))
  const t1Form  = Math.round((t1.form?.forme_score ?? 0.5) * 100)
  const t2Form  = Math.round((t2.form?.forme_score ?? 0.5) * 100)
  const t1Mom   = Math.max(0, Math.min(100, 50 + (t1.form?.streak ?? 0) * 10))
  const t2Mom   = Math.max(0, Math.min(100, 50 + (t2.form?.streak ?? 0) * 10))

  const rows = [
    { label: 'Winrate saison', t1: t1WR,   t2: t2WR,   suf: '%' },
    { label: 'Forme (5 dern.)', t1: t1Form, t2: t2Form, suf: '%' },
    { label: 'Momentum',        t1: t1Mom,  t2: t2Mom,  suf: '%' },
  ]

  return (
    <div className="mm-comp-rows">
      {rows.map((r, i) => (
        <div key={r.label} className="mm-comp-row" style={{ animationDelay: `${i * 80}ms` }}>
          <div className="mm-comp-label">{r.label}</div>
          <div className="mm-comp-bars">
            <div className="mm-comp-side mm-comp-left">
              <span className="mm-comp-val" style={{ color: r.t1 >= r.t2 ? lc : '#6b7280' }}>{r.t1}{r.suf}</span>
              <div className="mm-comp-bar-track left">
                <div className="mm-comp-bar-fill left"
                  style={{ width: `${r.t1}%`, background: r.t1 >= r.t2 ? `linear-gradient(270deg, ${lc}, ${lc}55)` : 'linear-gradient(270deg, #4b5563, #4b556355)' }} />
              </div>
            </div>
            <div className="mm-comp-side mm-comp-right">
              <div className="mm-comp-bar-track right">
                <div className="mm-comp-bar-fill right"
                  style={{ width: `${r.t2}%`, background: r.t2 > r.t1 ? `linear-gradient(90deg, ${lc}, ${lc}55)` : 'linear-gradient(90deg, #4b5563, #4b556355)' }} />
              </div>
              <span className="mm-comp-val" style={{ color: r.t2 > r.t1 ? lc : '#6b7280' }}>{r.t2}{r.suf}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Modal principale ─────────────────────────────────────────
export default function MatchModal({ matchId, onClose, onBetPlaced }) {
  const { user } = useAuthStore()

  const [detail,    setDetail]    = useState(null)
  const [loadDet,   setLoadDet]   = useState(true)
  const [errorLoad, setErrorLoad] = useState(null)

  const [tab,       setTab]       = useState('winner')
  const [selection, setSelection] = useState(null)
  const [amount,    setAmount]    = useState(100)
  const [submit,    setSubmit]    = useState(false)
  const [errSub,    setErrSub]    = useState('')
  const [success,   setSuccess]   = useState(false)

  // Charger détail
  useEffect(() => {
    if (!matchId) return
    setLoadDet(true); setErrorLoad(null)
    api.get(`/esports/match/${matchId}`)
      .then(r => setDetail(r.data))
      .catch(e => setErrorLoad(e.response?.data?.detail || 'Impossible de charger le match'))
      .finally(() => setLoadDet(false))
  }, [matchId])

  useEffect(() => { setSelection(null) }, [tab])

  // Bloquer scroll body
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // ESC
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (loadDet) {
    return (
      <div className="mm-fs">
        <div className="mm-ambient"><div className="mm-amb-blue" /><div className="mm-amb-red" /></div>
        <div className="mm-loading">
          <div className="mm-orb" />
          <div className="mm-orb mm-orb-2" />
          <div className="mm-orb mm-orb-3" />
          <span className="mm-loading-txt">Chargement du match…</span>
        </div>
      </div>
    )
  }

  if (errorLoad || !detail) {
    return (
      <div className="mm-fs">
        <div className="mm-ambient"><div className="mm-amb-blue" /><div className="mm-amb-red" /></div>
        <div className="mm-error-box">
          <div className="mm-error-ico">❌</div>
          <div className="mm-error-title">Erreur</div>
          <div className="mm-error-msg">{errorLoad || 'Match introuvable'}</div>
          <button className="mm-error-close" onClick={onClose}>Fermer</button>
        </div>
      </div>
    )
  }

  const t1 = detail.teams[0]
  const t2 = detail.teams[1]
  const bo = detail.bo
  const leagueMeta  = LEAGUE_META[detail.league?.slug?.toLowerCase()] || {}
  const lc          = leagueMeta.color || '#65BD62'
  const isCompleted = detail.state === 'completed'

  const t1Roster = sortRoster(t1.roster)
  const t2Roster = sortRoster(t2.roster)

  const potentialWin = selection ? Math.floor(amount * selection.odds) : 0
  const t1Streak  = streakInfo(t1.form?.streak ?? 0)
  const t2Streak  = streakInfo(t2.form?.streak ?? 0)
  const probT1Pct = Math.round((detail.odds.prob_team1 ?? 0.5) * 100)
  const probT2Pct = 100 - probT1Pct

  // ── Submit ──
  const handleSubmit = async () => {
    if (!selection) return setErrSub('Sélectionne un pari')
    if (amount < 10) return setErrSub('Mise minimum 10 coins')
    if (amount > (user?.coins || 0)) return setErrSub('Coins insuffisants')
    setErrSub(''); setSubmit(true)
    try {
      await api.post('/esports/bets/place', {
        match_id:  detail.match_id,
        bet_type:  selection.betType,
        bet_value: selection.betValue,
        amount,
      })
      setSuccess(true)
      setTimeout(() => { onBetPlaced && onBetPlaced(); onClose() }, 1500)
    } catch (err) {
      setErrSub(err.response?.data?.detail || 'Erreur lors du pari')
    } finally { setSubmit(false) }
  }

  // ── Tab renderers ──
  const renderWinnerTab = () => (
    <div className="mm-bet-grid-2">
      {[
        { key: 'team1', team: t1, odds: detail.odds.team1, side: 'blue' },
        { key: 'team2', team: t2, odds: detail.odds.team2, side: 'red' },
      ].map(opt => {
        const sel = selection?.betType === 'match_winner' && selection?.betValue === opt.key
        return (
          <button key={opt.key}
            className={`mm-bet-card ${opt.side} ${sel ? 'selected' : ''}`}
            onClick={() => setSelection({ betType: 'match_winner', betValue: opt.key, odds: opt.odds, label: `${opt.team.code} gagne` })}>
            <img className="mm-bet-card-logo" src={opt.team.image} alt={opt.team.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
            <div className="mm-bet-card-code">{opt.team.code}</div>
            <div className="mm-bet-card-odds">×{opt.odds}</div>
            {sel && <div className="mm-bet-card-check">✓</div>}
          </button>
        )
      })}
    </div>
  )

  const renderScoreTab = () => {
    const scoreOpts = SCORE_OPTS[bo] || SCORE_OPTS[3]
    return (
      <div className="mm-score-wrap">
        {[
          { key: 'team1', team: t1, baseOdds: detail.odds.team1, side: 'blue' },
          { key: 'team2', team: t2, baseOdds: detail.odds.team2, side: 'red' },
        ].map(s => (
          <div key={s.key} className={`mm-score-block ${s.side}`}>
            <div className="mm-score-team">
              <img src={s.team.image} alt={s.team.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              <span>{s.team.code} gagne</span>
            </div>
            <div className="mm-score-row">
              {scoreOpts.map(scr => {
                const mult      = detail.score_multipliers?.[scr] || 1.5
                const finalOdds = Math.min(15.0, parseFloat((s.baseOdds * mult).toFixed(2)))
                const betValue  = `${s.key}_${scr}`
                const sel       = selection?.betType === 'exact_score' && selection?.betValue === betValue
                const display   = s.key === 'team1' ? scr : scr.split('-').reverse().join('-')
                return (
                  <button key={scr}
                    className={`mm-score-opt ${s.side} ${sel ? 'selected' : ''}`}
                    onClick={() => setSelection({ betType: 'exact_score', betValue, odds: finalOdds, label: `${s.team.code} ${display}` })}>
                    <span className="mm-score-display">{display}</span>
                    <span className="mm-score-odds">×{finalOdds}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderHandicapTab = () => {
    const handicaps = detail.side_odds?.handicap || []
    if (handicaps.length === 0) return <div className="mm-bet-empty">⚖️ Pas de handicap disponible en BO{bo}.</div>
    return (
      <div className="mm-handicap-wrap">
        <div className="mm-handicap-intro">
          <span className="mm-handicap-intro-ico">💡</span>
          <span>Un handicap <strong>-1.5</strong> = l'équipe doit gagner avec au moins 2 maps d'écart. <strong>+1.5</strong> = elle ne doit pas perdre par plus de 1 map.</span>
        </div>
        {handicaps.map(h => {
          const isNeg = h.handicap.startsWith('-')
          return (
            <div key={h.handicap} className="mm-handicap-block">
              <div className="mm-handicap-label">
                <span className={`mm-handicap-tag ${isNeg ? 'neg' : 'pos'}`}>{h.handicap}</span>
                <span className="mm-handicap-desc">
                  {isNeg ? `Doit gagner avec ${Math.abs(parseFloat(h.handicap))} map(s) d'avance` : `Ne doit pas perdre par plus de ${parseFloat(h.handicap)} map(s)`}
                </span>
              </div>
              <div className="mm-bet-grid-2 mm-bet-grid-sm">
                {[
                  { key: 'team1', team: t1, odds: h.team1, side: 'blue' },
                  { key: 'team2', team: t2, odds: h.team2, side: 'red' },
                ].map(opt => {
                  const betValue = `${opt.key}_${h.handicap}`
                  const sel = selection?.betType === 'handicap_maps' && selection?.betValue === betValue
                  return (
                    <button key={opt.key}
                      className={`mm-bet-card ${opt.side} mm-bet-card-sm ${sel ? 'selected' : ''}`}
                      onClick={() => setSelection({ betType: 'handicap_maps', betValue, odds: opt.odds, label: `${opt.team.code} ${h.handicap}` })}>
                      <img className="mm-bet-card-logo" src={opt.team.image} alt={opt.team.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                      <div className="mm-bet-card-code">{opt.team.code} <span className="mm-bet-card-handicap">{h.handicap}</span></div>
                      <div className="mm-bet-card-odds">×{opt.odds}</div>
                      {sel && <div className="mm-bet-card-check">✓</div>}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const renderMapsTab = () => {
    const totals = detail.side_odds?.total_maps || {}
    const keys   = Object.keys(totals)
    if (keys.length === 0) return <div className="mm-bet-empty">📊 Pas de paris "total maps" pour un BO{bo}.</div>
    return (
      <div className="mm-totals-grid">
        {keys.map(key => {
          const [direction, threshold] = key.split('_')
          const betType  = direction === 'over' ? 'total_maps_over' : 'total_maps_under'
          const odds     = totals[key]
          const sel      = selection?.betType === betType && selection?.betValue === threshold
          const labelDir = direction === 'over' ? 'Plus de' : 'Moins de'
          return (
            <button key={key}
              className={`mm-totals-btn ${sel ? 'selected' : ''}`}
              style={{ '--tc': lc }}
              onClick={() => setSelection({ betType, betValue: threshold, odds, label: `${labelDir} ${threshold} maps` })}>
              <div className="mm-totals-arrow">{direction === 'over' ? '↑' : '↓'}</div>
              <div className="mm-totals-text">
                <span className="mm-totals-dir">{labelDir}</span>
                <span className="mm-totals-thr">{threshold} maps</span>
              </div>
              <div className="mm-totals-odds">×{odds}</div>
            </button>
          )
        })}
      </div>
    )
  }

  const renderMapByMapTab = () => {
    const mapWinners = detail.side_odds?.map_winners || []
    if (mapWinners.length === 0) return <div className="mm-bet-empty">🗺️ Pas de paris "map par map" en BO1.</div>
    return (
      <div className="mm-mbm-wrap">
        {mapWinners.map(m => (
          <div key={m.map} className="mm-mbm-block">
            <div className="mm-mbm-label">Map {m.map}</div>
            <div className="mm-bet-grid-2 mm-bet-grid-sm">
              {[
                { key: 'team1', team: t1, odds: m.team1, side: 'blue' },
                { key: 'team2', team: t2, odds: m.team2, side: 'red' },
              ].map(opt => {
                const betValue = `${opt.key}_map${m.map}`
                const sel      = selection?.betType === 'map_winner' && selection?.betValue === betValue
                return (
                  <button key={opt.key}
                    className={`mm-bet-card ${opt.side} mm-bet-card-sm ${sel ? 'selected' : ''}`}
                    onClick={() => setSelection({ betType: 'map_winner', betValue, odds: opt.odds, label: `${opt.team.code} map ${m.map}` })}>
                    <img className="mm-bet-card-logo" src={opt.team.image} alt={opt.team.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                    <div className="mm-bet-card-code">{opt.team.code}</div>
                    <div className="mm-bet-card-odds">×{opt.odds}</div>
                    {sel && <div className="mm-bet-card-check">✓</div>}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Onglets disponibles selon le format (handicap masqué en BO1)
  const tabs = [
    { k: 'winner',   l: 'Vainqueur', i: '🏆', show: true },
    { k: 'score',    l: 'Score',     i: '🎯', show: bo > 1 },
    { k: 'handicap', l: 'Handicap',  i: '⚖️', show: bo > 1 },
    { k: 'maps',     l: 'Maps',      i: '📊', show: bo > 1 },
    { k: 'mapByMap', l: 'Par map',   i: '🗺️', show: bo > 1 },
  ].filter(t => t.show)

  return (
    <div className="mm-fs">
      <div className="mm-ambient">
        <div className="mm-amb-blue" />
        <div className="mm-amb-red" />
      </div>

      {/* ─── TOPBAR ─── */}
      <div className="mm-topbar">
        <button className="mm-back" onClick={onClose}>← Retour</button>
        <div className="mm-topbar-c">
          <div className="mm-league-pill" style={{ color: lc, borderColor: lc + '40', background: lc + '10' }}>
            <span className="mm-league-dot" style={{ background: lc, boxShadow: `0 0 8px ${lc}` }} />
            <span>{detail.league?.name}</span>
            {detail.block_name && <span className="mm-league-block">· {detail.block_name}</span>}
          </div>
          <div className="mm-bo-pill">BO{bo}</div>
          <div className="mm-date-pill">{formatDate(detail.start_time)}</div>
        </div>
        <div className={`mm-state-badge ${isCompleted ? 'closed' : 'open'}`}>
          {isCompleted ? '🔒 Terminé' : '✓ Paris ouverts'}
        </div>
      </div>

      {/* ─── BENTO ─── */}
      <div className="mm-bento">

        {/* ══ DRAFT BLOCK : équipes face à face avec rosters ══ */}
        <div className="mm-draft-block">
          <div className="mm-col-info mm-col-info-blue">
            <div className="mm-side-header blue">
              <span className="mm-side-bar blue-bar" />BLUE SIDE
            </div>
            <div className="mm-team-hero blue">
              <img src={t1.image} alt={t1.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              <div className="mm-team-hero-code">{t1.code}</div>
              <div className="mm-team-hero-record">{t1.record?.wins ?? 0}—{t1.record?.losses ?? 0}</div>
            </div>
            {t1Roster.slice(0, 5).map((p, i) => <PlayerCell key={p.summoner_name + i} player={p} side="blue" delay={i * 80} />)}
          </div>

          <div className="mm-vs-col">
            <div className="mm-vs-ring">
              <span className="mm-vs-text">VS</span>
            </div>
            {isCompleted && (
              <div className="mm-vs-final" style={{ borderColor: lc + '50', color: lc }}>
                {t1.wins}—{t2.wins}
              </div>
            )}
          </div>

          <div className="mm-col-info mm-col-info-red">
            <div className="mm-side-header red">
              RED SIDE<span className="mm-side-bar red-bar" />
            </div>
            <div className="mm-team-hero red">
              <img src={t2.image} alt={t2.code} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              <div className="mm-team-hero-code">{t2.code}</div>
              <div className="mm-team-hero-record">{t2.record?.wins ?? 0}—{t2.record?.losses ?? 0}</div>
            </div>
            {t2Roster.slice(0, 5).map((p, i) => <PlayerCell key={p.summoner_name + i} player={p} side="red" delay={i * 80} />)}
          </div>
        </div>

        {/* ══ STATS LAYOUT ══ */}
        <div className="mm-stats-layout">

          {/* PROBA + COMPARATEUR */}
          <div className="mm-block mm-block-proba">
            <div className="mm-block-title">
              <span>🎲 Probabilités</span>
              <span className="mm-block-sub">par notre moteur</span>
            </div>
            <div className="mm-proba-bar">
              <div className="mm-proba-fill blue" style={{ width: `${probT1Pct}%` }}>
                <span className="mm-proba-pct">{probT1Pct}%</span>
              </div>
              <div className="mm-proba-fill red" style={{ width: `${probT2Pct}%` }}>
                <span className="mm-proba-pct">{probT2Pct}%</span>
              </div>
            </div>
            <div className="mm-proba-odds">
              <div className="mm-proba-odd blue">
                <span className="mm-proba-team">{t1.code}</span>
                <span className="mm-proba-val">×{detail.odds.team1}</span>
              </div>
              <div className="mm-proba-odd red">
                <span className="mm-proba-team">{t2.code}</span>
                <span className="mm-proba-val">×{detail.odds.team2}</span>
              </div>
            </div>

            <div className="mm-block-divider" />

            <div className="mm-block-subtitle">📊 Comparatif</div>
            <StatComparator t1={t1} t2={t2} lc={lc} />
          </div>

          {/* FORME + H2H */}
          <div className="mm-block mm-block-form">
            <div className="mm-block-title">
              <span>📈 Forme récente</span>
              <span className="mm-block-sub">5 derniers matchs</span>
            </div>
            <div className="mm-form-rows">
              <div className="mm-form-row">
                <span className="mm-form-team blue">{t1.code}</span>
                <FormBadges last5={t1.form?.last_5} />
                <span className={`mm-form-streak ${t1Streak.cls}`}>{t1Streak.txt}</span>
              </div>
              <div className="mm-form-row">
                <span className="mm-form-team red">{t2.code}</span>
                <FormBadges last5={t2.form?.last_5} />
                <span className={`mm-form-streak ${t2Streak.cls}`}>{t2Streak.txt}</span>
              </div>
            </div>

            <div className="mm-block-divider" />

            <div className="mm-block-subtitle">⚔️ Tête-à-tête</div>
            {detail.head_to_head?.total_matches > 0 ? (
              <>
                <div className="mm-h2h">
                  <div className="mm-h2h-side blue">
                    <div className="mm-h2h-num">{detail.head_to_head.team1_wins}</div>
                    <div className="mm-h2h-team">{t1.code}</div>
                  </div>
                  <div className="mm-h2h-vs">
                    <div className="mm-h2h-total">{detail.head_to_head.total_matches}</div>
                    <div className="mm-h2h-total-lbl">matchs</div>
                  </div>
                  <div className="mm-h2h-side red">
                    <div className="mm-h2h-num">{detail.head_to_head.team2_wins}</div>
                    <div className="mm-h2h-team">{t2.code}</div>
                  </div>
                </div>
                {detail.head_to_head.last_match && (
                  <div className="mm-h2h-last">
                    Dernier : <strong>{detail.head_to_head.last_match.winner === 'team1' ? t1.code : t2.code} {detail.head_to_head.last_match.score}</strong>
                    <span className="mm-h2h-date"> · {formatRelativeDate(detail.head_to_head.last_match.date)}</span>
                  </div>
                )}
              </>
            ) : (
              <div className="mm-h2h-empty">✨ Première rencontre</div>
            )}
          </div>

          {/* SAISON */}
          <div className="mm-block mm-block-season">
            <div className="mm-block-title">
              <span>🏅 Bilan saison</span>
            </div>
            <div className="mm-season-cards">
              <div className="mm-season-card blue">
                <div className="mm-season-card-team">{t1.code}</div>
                <div className="mm-season-card-wr" style={{ color: lc }}>{t1.season?.winrate ?? 50}%</div>
                <div className="mm-season-card-rec">{t1.season?.wins ?? 0}<span>W</span> — {t1.season?.losses ?? 0}<span>L</span></div>
              </div>
              <div className="mm-season-card red">
                <div className="mm-season-card-team">{t2.code}</div>
                <div className="mm-season-card-wr" style={{ color: lc }}>{t2.season?.winrate ?? 50}%</div>
                <div className="mm-season-card-rec">{t2.season?.wins ?? 0}<span>W</span> — {t2.season?.losses ?? 0}<span>L</span></div>
              </div>
            </div>
          </div>
        </div>

        {/* ══ ZONE PARIS ══ */}
        {!isCompleted && (
          <div className="mm-bets-zone">
            <div className="mm-bets-header">
              <span className="mm-bets-title">🎰 Placer un pari</span>
              <span className="mm-bets-sub">{detail.total_bets ?? 0} pari{(detail.total_bets ?? 0) > 1 ? 's' : ''} sur ce match</span>
            </div>

            <div className="mm-bet-tabs">
              {tabs.map(t => (
                <button key={t.k}
                  className={`mm-bet-tab ${tab === t.k ? 'active' : ''}`}
                  style={{ '--tc': lc }}
                  onClick={() => setTab(t.k)}>
                  <span className="mm-bet-tab-ico">{t.i}</span>
                  <span>{t.l}</span>
                </button>
              ))}
            </div>

            <div className="mm-bet-content" key={tab}>
              {tab === 'winner'   && renderWinnerTab()}
              {tab === 'score'    && renderScoreTab()}
              {tab === 'handicap' && renderHandicapTab()}
              {tab === 'maps'     && renderMapsTab()}
              {tab === 'mapByMap' && renderMapByMapTab()}
            </div>

            <div className="mm-bet-footer">
              <div className="mm-stake-block">
                <div className="mm-stake-label">Mise</div>
                <div className="mm-presets">
                  {[50, 100, 250, 500, 1000].map(v => (
                    <button key={v}
                      className={`mm-preset ${amount === v ? 'active' : ''}`}
                      style={{ '--tc': lc }}
                      onClick={() => setAmount(v)}>
                      {v.toLocaleString()}
                    </button>
                  ))}
                </div>
                <div className="mm-stake-row">
                  <input className="mm-stake-input" type="number" min={10} max={user?.coins || 0}
                    value={amount}
                    onChange={e => setAmount(Math.max(10, parseInt(e.target.value) || 10))}
                    style={{ '--tc': lc }} />
                  <span className="mm-stake-unit">coins</span>
                  <span className="mm-stake-balance">/ {user?.coins?.toLocaleString()}</span>
                </div>
              </div>

              <div className="mm-recap-block">
                {selection ? (
                  <div className="mm-recap" style={{ borderColor: lc + '50' }}>
                    <div className="mm-recap-pulse" style={{ background: lc }} />
                    <div className="mm-recap-left">
                      <div className="mm-recap-label">Pari</div>
                      <div className="mm-recap-bet">{selection.label}</div>
                      <div className="mm-recap-odds">cote ×{selection.odds}</div>
                    </div>
                    <div className="mm-recap-right">
                      <div className="mm-recap-label">Gain potentiel</div>
                      <div className="mm-recap-amount" style={{ color: lc }}>+{potentialWin.toLocaleString()}</div>
                      <div className="mm-recap-unit">coins</div>
                    </div>
                  </div>
                ) : (
                  <div className="mm-recap-empty">
                    <span className="mm-recap-empty-ico">↑</span>
                    Choisis un pari ci-dessus
                  </div>
                )}

                {errSub && <div className="mm-error">⚠️ {errSub}</div>}

                {success ? (
                  <div className="mm-success"><span>✓</span> Pari enregistré !</div>
                ) : (
                  <button className="mm-confirm" onClick={handleSubmit}
                    disabled={submit || !selection}
                    style={{ '--tc': lc }}>
                    {submit ? <span className="mm-spinner" /> : (
                      <>
                        <span className="mm-confirm-txt">Confirmer le pari</span>
                        <span className="mm-confirm-amount">{amount.toLocaleString()} coins</span>
                      </>
                    )}
                    <span className="mm-confirm-shimmer" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {isCompleted && (
          <div className="mm-completed" style={{ borderColor: lc + '50' }}>
            <span className="mm-completed-ico">🏆</span>
            <div>
              <div className="mm-completed-title">Match terminé</div>
              <div className="mm-completed-sub" style={{ color: lc }}>
                {t1.wins > t2.wins ? t1.code : t2.code} remporte {Math.max(t1.wins, t2.wins)}—{Math.min(t1.wins, t2.wins)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}