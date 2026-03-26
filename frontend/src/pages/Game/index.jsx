import './Game.css'
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV = '14.24.1'
const ROLE_ORDER  = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
const ROLE_ICONS  = { TOP:'🛡️', JUNGLE:'🌿', MID:'⚡', ADC:'🏹', SUPPORT:'💙' }
const ROLE_LABELS = { TOP:'TOP', JUNGLE:'JUNGLE', MID:'MID', ADC:'ADC', SUPPORT:'SUPPORT', BOTTOM:'ADC', UTILITY:'SUPPORT', MIDDLE:'MID' }

function useLiveTimer(init) {
  const [s, setS] = useState(init ?? 0)
  const ref = useRef(null)
  useEffect(() => {
    if (init == null) return
    setS(init)
    clearInterval(ref.current)
    ref.current = setInterval(() => setS(x => x + 1), 1000)
    return () => clearInterval(ref.current)
  }, [init])
  return s
}

function fmt(s) { return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}` }

const champIcon   = n => n ? `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${n}.png` : null
const champSplash = n => n ? `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${n}_0.jpg` : null

function normalizeRole(r) {
  if (!r) return null
  const up = r.toUpperCase()
  return ROLE_LABELS[up] || up
}

function SplashCell({ player, side }) {
  const name   = player?.championName
  const splash = champSplash(name)
  return (
    <div className="gp-splash-cell">
      {splash
        ? <img src={splash} alt={name} className="gp-splash-img" onError={e => { e.target.style.display = 'none' }} />
        : <div className="gp-splash-placeholder">{name?.slice(0,2) ?? '?'}</div>
      }
      <div className={`gp-splash-overlay ${side === 'blue' ? 'gp-splash-fade-right' : 'gp-splash-fade-left'}`} />
    </div>
  )
}

function PlayerRow({ player, side }) {
  const name   = player?.championName
  const pseudo = player?.summonerName || '—'
  const role   = player?.role || '?'
  const isPro  = !!player?.pro
  return (
    <div className="gp-player-row">
      <div className="gp-player-pseudo">
        {isPro && <span className="gp-pro-badge">{player.pro.team}</span>}
        {pseudo}
      </div>
      <div className="gp-player-name">{name || '???'}</div>
      <div className={`gp-player-role ${side}`}>
        <span>{ROLE_ICONS[role] ?? '❓'}</span>
        <span>{role}</span>
      </div>
    </div>
  )
}

function FbBtn({ player, side, selected, onSelect, disabled }) {
  const name   = player?.championName
  const icon   = champIcon(name)
  const pseudo = player?.summonerName || '—'
  const role   = player?.role || '?'
  const isSel  = selected === name
  return (
    <button
      className={`gp-fb-btn gp-fb-${side}${isSel ? ' selected' : ''}`}
      onClick={() => !disabled && onSelect(name)}
      disabled={disabled}
    >
      <div className="gp-fb-icon-wrap">
        {icon
          ? <img src={icon} alt={name} className="gp-fb-champ-icon" onError={e => { e.target.style.display='none' }} />
          : <span className="gp-fb-placeholder">{name?.slice(0,2)}</span>
        }
      </div>
      <div className="gp-fb-info">
        <span className="gp-fb-champ-name">{name || '???'}</span>
        <span className="gp-fb-player">{ROLE_ICONS[role] || ''} {pseudo}</span>
      </div>
      {isSel && <span className="gp-check">✓</span>}
    </button>
  )
}

export default function Game() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const { user, updateCoins } = useAuthStore()

  const [game,       setGame]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [champMap,   setChampMap]   = useState({})
  const [selections, setSelections] = useState({})
  const [amount,     setAmount]     = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [betDone,    setBetDone]    = useState(null)
  const [betError,   setBetError]   = useState(null)

  const liveSeconds = useLiveTimer(game?.duration_seconds ?? null)

  useEffect(() => {
    fetch(`https://ddragon.leagueoflegends.com/cdn/${DDV}/data/en_US/champion.json`)
      .then(r => r.json())
      .then(d => {
        const m = {}
        Object.values(d.data).forEach(c => { m[parseInt(c.key)] = c.id })
        setChampMap(m)
      }).catch(() => {})
  }, [])

  const loadGame = useCallback(() => {
    api.get(`/games/${id}`)
      .then(r => setGame(r.data))
      .catch(() => setError('Partie introuvable'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { loadGame() }, [loadGame])
  useEffect(() => {
    if (!game) return
    const iv = setInterval(loadGame, 30000)
    return () => clearInterval(iv)
  }, [game, loadGame])

  const enrich = useCallback(team => {
    const enriched = team.map(p => ({
      ...p,
      championName: p.championName || champMap[p.championId] || null,
      role: normalizeRole(p.role),
    }))
    return enriched.sort((a, b) => {
      const ai = ROLE_ORDER.indexOf(a.role ?? '')
      const bi = ROLE_ORDER.indexOf(b.role ?? '')
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }, [champMap])

  // ── Destructuration ici, APRÈS les hooks ──────────────────────────────────
  const blue_team = game?.blue_team ?? []
  const red_team  = game?.red_team  ?? []
  const queue     = game?.queue
  const pro       = game?.pro
  const status    = game?.status
  const betsOpen  = status !== 'ended'

  const blue = useMemo(() => enrich(blue_team), [blue_team, enrich])
  const red  = useMemo(() => enrich(red_team),  [red_team,  enrich])

  const toggleWin = val => {
    if (!betsOpen) return
    setSelections(prev => prev.who_wins === val
      ? (({ who_wins, ...r }) => r)(prev)
      : { ...prev, who_wins: val })
  }
  const setFb = name => {
    if (!betsOpen) return
    setSelections(prev => prev.first_blood === name
      ? (({ first_blood, ...r }) => r)(prev)
      : { ...prev, first_blood: name })
  }

  const selList = Object.entries(selections).map(([type, value]) => ({ type, value }))
  const odds    = Math.pow(2, selList.length)
  const gain    = amount ? Math.floor(parseInt(amount) * odds) : 0

  const handleBet = async () => {
    if (!selList.length)                 { setBetError('Choisis au moins une sélection'); return }
    if (!amount || parseInt(amount) < 1) { setBetError('Montant invalide'); return }
    if (!user)                           { navigate('/login'); return }
    setSubmitting(true); setBetError(null); setBetDone(null)
    try {
      let last = null
      for (const s of selList) {
        const r = await api.post('/bets/place', { live_game_id: game.id, bet_type_slug: s.type, bet_value: s.value, amount: parseInt(amount) })
        last = r.data
      }
      setBetDone(last)
      if (last?.coins_restants !== undefined) updateCoins(last.coins_restants)
      setSelections({}); setAmount('')
    } catch (e) {
      setBetError(e.response?.data?.detail || 'Erreur lors du pari')
    } finally { setSubmitting(false) }
  }

  if (loading) return <div className="gp-page"><div className="gp-loading"><div className="gp-spinner" /><span>Chargement...</span></div></div>
  if (error)   return <div className="gp-page"><div className="gp-error"><div className="gp-error-title">Partie introuvable</div><div className="gp-error-sub">{error}</div><button className="gp-back-btn" onClick={() => navigate('/')}>← Retour</button></div></div>

  return (
    <div className="gp-page">
      <div className="gp-ambient">
        <div className="gp-ambient-blue" />
        <div className="gp-ambient-red" />
        {pro?.team_logo_url && <img className="gp-ambient-logo" src={pro.team_logo_url} alt="" referrerPolicy="no-referrer" />}
      </div>

      <div className="gp-topbar">
        <button className="gp-back" onClick={() => navigate('/')}>← Retour</button>
        <div className="gp-topbar-center">
          <div className="gp-live-pill"><span className="gp-live-dot" />LIVE</div>
          <span className="gp-queue">{queue}</span>
          <span className="gp-timer">{fmt(liveSeconds)}</span>
        </div>
        <div className={`gp-bets-badge ${betsOpen ? 'open' : 'closed'}`}>
          {betsOpen ? '✓ Paris ouverts' : '🔒 Paris fermés'}
        </div>
      </div>

      <div className="gp-bento">
        <div className="gp-draft-block">
          <div className="gp-col-info gp-col-info-blue">
            <div className="gp-side-header blue"><span className="gp-side-bar blue-bar" />BLUE SIDE</div>
            {blue.map((p, i) => <PlayerRow key={i} player={p} side="blue" />)}
          </div>
          <div className="gp-col-splash gp-col-splash-blue">
            <div style={{ height: 37 }} />
            {blue.map((p, i) => <SplashCell key={i} player={p} side="blue" />)}
          </div>
          <div className="gp-vs-col">
            <div className="gp-vs-ring"><span className="gp-vs-text">VS</span></div>
          </div>
          <div className="gp-col-splash gp-col-splash-red">
            <div style={{ height: 37 }} />
            {red.map((p, i) => <SplashCell key={i} player={p} side="red" />)}
          </div>
          <div className="gp-col-info gp-col-info-red">
            <div className="gp-side-header red">RED SIDE<span className="gp-side-bar red-bar" /></div>
            {red.map((p, i) => <PlayerRow key={i} player={p} side="red" />)}
          </div>
        </div>

        <div className="gp-bets-row">
          <div className="gp-bet-block gp-bet-win">
            <div className="gp-bet-block-header">
              <span className="gp-bet-icon">🏆</span>
              <span className="gp-bet-title">Victoire</span>
              <span className="gp-bet-odd">×2</span>
            </div>
            <div className="gp-win-opts">
              {['blue','red'].map(s => (
                <button key={s} className={`gp-win-btn gp-win-${s}${selections.who_wins===s?' selected':''}`}
                  onClick={() => toggleWin(s)} disabled={!betsOpen}>
                  <span className={`gp-win-dot ${s}-dot`} />
                  <span>{s === 'blue' ? 'Blue side' : 'Red side'}</span>
                  {selections.who_wins === s && <span className="gp-check">✓</span>}
                </button>
              ))}
            </div>
          </div>

          <div className="gp-bet-block gp-bet-fb">
            <div className="gp-bet-block-header">
              <span className="gp-bet-icon">🩸</span>
              <span className="gp-bet-title">First Blood</span>
              <span className="gp-bet-odd">×2</span>
            </div>
            <div className="gp-fb-section">
              <div className="gp-fb-section-label blue-label">⬡ Blue side</div>
              {blue.map((p,i) => <FbBtn key={i} player={p} side="blue" selected={selections.first_blood} onSelect={setFb} disabled={!betsOpen} />)}
            </div>
            <div className="gp-fb-section">
              <div className="gp-fb-section-label red-label">⬡ Red side</div>
              {red.map((p,i) => <FbBtn key={i} player={p} side="red" selected={selections.first_blood} onSelect={setFb} disabled={!betsOpen} />)}
            </div>
          </div>

          <div className="gp-bet-block gp-slip">
            <div className="gp-bet-block-header">
              <span className="gp-bet-icon">🎯</span>
              <span className="gp-bet-title">Mon pari</span>
              {selList.length > 0 && <span className="gp-slip-count">{selList.length}</span>}
            </div>
            <div className="gp-slip-rows">
              {selList.length === 0
                ? <div className="gp-slip-empty">Aucune sélection</div>
                : selList.map((s,i) => {
                    const isFb = s.type === 'first_blood'
                    return (
                      <div key={i} className="gp-slip-row">
                        {isFb && champIcon(s.value) && <img src={champIcon(s.value)} className="gp-slip-champ-icon" alt="" onError={e=>{e.target.style.display='none'}} />}
                        <span className="gp-slip-label">{isFb ? '🩸 First Blood' : '🏆 Victoire'}</span>
                        <span className="gp-slip-val" style={{color:s.value==='blue'?'#378add':s.value==='red'?'#ef4444':'#00e5ff'}}>{s.value}</span>
                        <span className="gp-slip-x">×2</span>
                      </div>
                    )
                  })
              }
              {selList.length > 0 && (
                <div className="gp-slip-total">
                  <span>Cote combinée</span>
                  <span className="gp-slip-total-val">×{odds.toFixed(1)}</span>
                </div>
              )}
            </div>
            <div className="gp-amount-wrap">
              <input className="gp-amount-input" type="number" min="1" placeholder="Mise en coins..."
                value={amount} onChange={e => setAmount(e.target.value)} disabled={!betsOpen} />
              <div className="gp-presets">
                {[100,500,1000].map(v => (
                  <button key={v} className="gp-preset" onClick={() => setAmount(String(v))} disabled={!betsOpen}>{v}</button>
                ))}
                <button className="gp-preset gp-preset-max" onClick={() => setAmount(String(user?.coins||0))} disabled={!betsOpen}>MAX</button>
              </div>
            </div>
            {gain > 0 && <div className="gp-gain">Gain potentiel <strong>{gain.toLocaleString()} coins</strong></div>}
            {betError && <div className="gp-bet-error">{betError}</div>}
            {betDone  && <div className="gp-bet-success">✓ Pari placé ! Solde : {betDone.coins_restants?.toLocaleString()} coins</div>}
            <button className="gp-place-btn" onClick={handleBet}
              disabled={!betsOpen||submitting||!selList.length||!amount}>
              {!betsOpen ? '🔒 Paris fermés' : submitting ? 'Placement...' : `Parier ${amount ? parseInt(amount).toLocaleString() : '—'} coins`}
            </button>
            {user && <div className="gp-balance">Solde : {user.coins?.toLocaleString()} coins</div>}
          </div>
        </div>
      </div>
    </div>
  )
}