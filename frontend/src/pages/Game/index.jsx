import './Game.css'
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV = '14.24.1'
const ROLE_ORDER = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
const ROLE_ICONS = { TOP: '🛡️', JUNGLE: '🌿', MID: '⚡', ADC: '🏹', SUPPORT: '💙' }

const ROLE_LABELS = {
  TOP: 'TOP', JUNGLE: 'JUNGLE',
  MIDDLE: 'MID', MID: 'MID',
  BOTTOM: 'ADC', ADC: 'ADC',
  UTILITY: 'SUPPORT', SUPPORT: 'SUPPORT'
}

// ─── DataDragon tags → rôle ───────────────────────────────────────────────────
function tagsToRole(tags = []) {
  if (tags.includes('Marksman'))                                           return 'ADC'
  if (tags.includes('Support') && !tags.includes('Fighter')
                               && !tags.includes('Mage'))                  return 'SUPPORT'
  if (tags.includes('Tank') || tags.includes('Fighter'))                   return 'TOP'
  if (tags.includes('Assassin') || tags.includes('Mage'))                  return 'MID'
  return null
}

// ─── Détection rôle par spells + tags champion ───────────────────────────────
// Spells : 3=Exhaust 4=Flash 6=Ghost 7=Heal 11=Smite 12=TP 14=Ignite 21=Barrier
function spellRole(spell1, spell2, tagRole) {
  const spells = [spell1, spell2]
  const isMarksman    = tagRole === 'ADC'
  const isSupportChamp = tagRole === 'SUPPORT'

  if (spells.includes(11)) return { role: 'JUNGLE',  confidence: 100 }
  if (spells.includes(3))  return { role: 'SUPPORT', confidence: 95  } // Exhaust → support (sauf Marksman)
  if (spells.includes(7)) {
    if (isMarksman)    return { role: 'ADC',     confidence: 99 } // Marksman + Heal = ADC certain
    if (isSupportChamp) return { role: 'SUPPORT', confidence: 90 } // Support champ + Heal = support
    return                      { role: 'ADC',     confidence: 70 } // Heal sans info = probablement ADC
  }
  if (spells.includes(14) && isSupportChamp) return { role: 'SUPPORT', confidence: 85 } // Ignite sur support champ
  if (spells.includes(12)) return { role: null, confidence: 0, hint: 'TP'  } // TP → TOP/MID/ADC
  if (spells.includes(14)) return { role: null, confidence: 0, hint: 'IGN' } // Ignite → TOP/MID
  return { role: null, confidence: 0 }
}

// ─── Timer live ──────────────────────────────────────────────────────────────
function useLiveTimer(init) {
  const [s, setS] = useState(init ?? 0)
  const ref = useRef(null)
  const currentRef = useRef(init ?? 0)

  useEffect(() => {
    if (init == null) return
    if (Math.abs(init - currentRef.current) > 5) {
      setS(init)
      currentRef.current = init
    }
    if (ref.current) return
    ref.current = setInterval(() => {
      currentRef.current += 1
      setS(x => x + 1)
    }, 1000)
    return () => { clearInterval(ref.current); ref.current = null }
  }, [init])

  return s
}

function fmt(s) { return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` }
const champIcon   = n => n ? `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${n}.png` : null
const champSplash = n => n ? `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${n}_0.jpg` : null

function normalizeRole(r) {
  if (!r) return null
  return ROLE_LABELS[r.toUpperCase()] || null
}

// ─── Composants ──────────────────────────────────────────────────────────────
function SplashCell({ player, side }) {
  const splash = champSplash(player?.championName)
  return (
    <div className="gp-splash-cell">
      {splash
        ? <img src={splash} alt={player?.championName} className="gp-splash-img"
            onError={e => { e.target.style.display = 'none' }} />
        : <div className="gp-splash-placeholder">{player?.championName?.slice(0, 2) ?? '?'}</div>
      }
      <div className={`gp-splash-overlay ${side === 'blue' ? 'gp-splash-fade-right' : 'gp-splash-fade-left'}`} />
    </div>
  )
}

function PlayerRow({ player, side }) {
  const role = player?.role || '?'
  return (
    <div className="gp-player-row">
      <div className="gp-player-pseudo">
        {player?.pro && <span className="gp-pro-badge">{player.pro.team}</span>}
        {player?.summonerName || '—'}
      </div>
      <div className="gp-player-name">{player?.championName || '???'}</div>
      <div className={`gp-player-role ${side}`}>
        <span>{ROLE_ICONS[role] ?? '❓'}</span>
        <span>{role}</span>
      </div>
    </div>
  )
}

function FbBtn({ player, side, selected, onSelect, disabled }) {
  const name = player?.championName
  const role = player?.role || '?'
  const isSel = selected === name
  return (
    <button className={`gp-fb-btn gp-fb-${side}${isSel ? ' selected' : ''}`}
      onClick={() => !disabled && onSelect(name)} disabled={disabled}>
      <div className="gp-fb-icon-wrap">
        {champIcon(name)
          ? <img src={champIcon(name)} alt={name} className="gp-fb-champ-icon"
              onError={e => { e.target.style.display = 'none' }} />
          : <span className="gp-fb-placeholder">{name?.slice(0, 2)}</span>}
      </div>
      <div className="gp-fb-info">
        <span className="gp-fb-champ-name">{name || '???'}</span>
        <span className="gp-fb-player">{ROLE_ICONS[role] || ''} {player?.summonerName || '—'}</span>
      </div>
      {isSel && <span className="gp-check">✓</span>}
    </button>
  )
}

// ─── Page principale ─────────────────────────────────────────────────────────
export default function Game() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, updateCoins } = useAuthStore()

  const [game, setGame]               = useState(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [champMap, setChampMap]       = useState({})
  const [champTagMap, setChampTagMap] = useState({})
  const [selections, setSelections]   = useState({})
  const [amount, setAmount]           = useState('')
  const [submitting, setSubmitting]   = useState(false)
  const [betDone, setBetDone]         = useState(null)
  const [betError, setBetError]       = useState(null)

  const liveSeconds = useLiveTimer(game?.duration_seconds ?? 0)

  // Chargement DataDragon
  useEffect(() => {
    fetch(`https://ddragon.leagueoflegends.com/cdn/${DDV}/data/en_US/champion.json`)
      .then(r => r.json())
      .then(d => {
        const m = {}
        const tagMap = {}
        Object.values(d.data).forEach(c => {
          m[String(parseInt(c.key))] = c.id
          tagMap[c.id] = tagsToRole(c.tags)
        })
        setChampMap(m)
        setChampTagMap(tagMap)
      }).catch(() => {})
  }, [])

  const loadGame = useCallback(() => {
    api.get(`/games/${id}`)
      .then(r => { setGame(r.data); setLoading(false) })
      .catch(() => { setError('Partie introuvable'); setLoading(false) })
  }, [id])

  useEffect(() => { loadGame() }, [loadGame])
  useEffect(() => {
    if (!game || game.status === 'ended') return
    const iv = setInterval(loadGame, 30000)
    return () => clearInterval(iv)
  }, [game, loadGame])

  // ─── Assignation des rôles ─────────────────────────────────────────────────
  const processTeam = useCallback((team) => {
    if (!team || Object.keys(champMap).length === 0) return []

    // 1. Résoudre les noms + rôle Riot normalisé
    const players = team.map(p => ({
      ...p,
      championName: p.championName || champMap[String(p.championId)] || 'Unknown',
      role: normalizeRole(p.role),
    }))

    const assigned  = new Map()
    const usedRoles = new Set()

    // 2. Passe 1 — rôles certains par spells (Smite, Exhaust, Heal) + rôle Riot
    players.forEach((p, i) => {
      const tagRole                    = champTagMap[p.championName]
      const { role, confidence }       = spellRole(p.spell1Id, p.spell2Id, tagRole)
      const riotRole                   = p.role

      // Priorité 1 : rôle Riot explicite
      if (riotRole && ROLE_ORDER.includes(riotRole) && !usedRoles.has(riotRole)) {
        assigned.set(i, riotRole); usedRoles.add(riotRole); return
      }
      // Priorité 2 : spell à haute confiance
      // Exception : Exhaust sur un Marksman → on skip, sera traité après
      if (role === 'SUPPORT' && tagRole === 'ADC') return
      if (role && confidence >= 85 && !usedRoles.has(role)) {
        assigned.set(i, role); usedRoles.add(role)
      }
    })

    // 3. Passe 2 — Heal sur non-Marksman et Exhaust sur Marksman résolus ici
    players.forEach((p, i) => {
      if (assigned.has(i)) return
      const tagRole              = champTagMap[p.championName]
      const { role, confidence } = spellRole(p.spell1Id, p.spell2Id, tagRole)
      if (role && confidence >= 70 && !usedRoles.has(role)) {
        assigned.set(i, role); usedRoles.add(role)
      }
    })

    // 4. Passe 3 — TP et Ignite avec hint DataDragon
    players.forEach((p, i) => {
      if (assigned.has(i)) return
      const tagRole       = champTagMap[p.championName]
      const { hint }      = spellRole(p.spell1Id, p.spell2Id, tagRole)

      if (hint === 'TP') {
        const candidates = ['TOP', 'MID', 'ADC']
        const best = candidates.find(r => r === tagRole && !usedRoles.has(r))
                  || candidates.find(r => !usedRoles.has(r))
        if (best) { assigned.set(i, best); usedRoles.add(best) }
      } else if (hint === 'IGN') {
        const candidates = ['TOP', 'MID']
        const best = candidates.find(r => r === tagRole && !usedRoles.has(r))
                  || candidates.find(r => !usedRoles.has(r))
        if (best) { assigned.set(i, best); usedRoles.add(best) }
      }
    })

    // 5. Passe 4 — DataDragon tags pour les restants
    players.forEach((p, i) => {
      if (assigned.has(i)) return
      const tagRole = champTagMap[p.championName]
      if (tagRole && !usedRoles.has(tagRole)) {
        assigned.set(i, tagRole); usedRoles.add(tagRole)
      }
    })

    // 6. Passe 5 — rôles libres dans l'ordre ROLE_ORDER
    const freeRoles = ROLE_ORDER.filter(r => !usedRoles.has(r))
    let fi = 0
    players.forEach((_, i) => {
      if (!assigned.has(i) && fi < freeRoles.length) {
        assigned.set(i, freeRoles[fi++])
      }
    })

    return players
      .map((p, i) => ({ ...p, role: assigned.get(i) || 'MID' }))
      .sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role))

  }, [champMap, champTagMap])

  const blue = useMemo(() => processTeam(game?.blue_team), [game?.blue_team, processTeam])
  const red  = useMemo(() => processTeam(game?.red_team),  [game?.red_team,  processTeam])

  const betsOpen = game?.status !== 'ended'

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
    if (!selList.length)                   { setBetError('Choisis au moins une sélection'); return }
    if (!amount || parseInt(amount) < 1)   { setBetError('Montant invalide'); return }
    if (!user)                             { navigate('/login'); return }
    setSubmitting(true); setBetError(null); setBetDone(null)
    try {
      let last = null
      for (const s of selList) {
        const r = await api.post('/bets/place', {
          live_game_id:  game.id,
          bet_type_slug: s.type,
          bet_value:     s.value,
          amount:        parseInt(amount),
        })
        last = r.data
      }
      setBetDone(last)
      if (last?.coins_restants !== undefined) updateCoins(last.coins_restants)
      setSelections({}); setAmount('')
    } catch (e) {
      setBetError(e.response?.data?.detail || 'Erreur lors du pari')
    } finally { setSubmitting(false) }
  }

  if (loading || Object.keys(champMap).length === 0) return (
    <div className="gp-page">
      <div className="gp-loading"><div className="gp-spinner" /><span>Chargement de la faille...</span></div>
    </div>
  )

  if (error) return (
    <div className="gp-page">
      <div className="gp-error">
        <div className="gp-error-title">Partie introuvable</div>
        <div className="gp-error-sub">{error}</div>
        <button className="gp-back-btn" onClick={() => navigate('/')}>← Retour</button>
      </div>
    </div>
  )

  return (
    <div className="gp-page">
      <div className="gp-ambient">
        <div className="gp-ambient-blue" />
        <div className="gp-ambient-red" />
      </div>

      <div className="gp-topbar">
        <button className="gp-back" onClick={() => navigate('/')}>← Retour</button>
        <div className="gp-topbar-center">
          <div className="gp-live-pill"><span className="gp-live-dot" />LIVE</div>
          <span className="gp-queue">{game.queue_type || 'Ranked Solo'}</span>
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
            {blue.map((p) => <PlayerRow key={p.championId} player={p} side="blue" />)}
          </div>
          <div className="gp-col-splash gp-col-splash-blue">
            <div style={{ height: 37 }} />
            {blue.map((p) => <SplashCell key={p.championId} player={p} side="blue" />)}
          </div>
          <div className="gp-vs-col">
            <div className="gp-vs-ring"><span className="gp-vs-text">VS</span></div>
          </div>
          <div className="gp-col-splash gp-col-splash-red">
            <div style={{ height: 37 }} />
            {red.map((p) => <SplashCell key={p.championId} player={p} side="red" />)}
          </div>
          <div className="gp-col-info gp-col-info-red">
            <div className="gp-side-header red">RED SIDE<span className="gp-side-bar red-bar" /></div>
            {red.map((p) => <PlayerRow key={p.championId} player={p} side="red" />)}
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
              {['blue', 'red'].map(s => (
                <button key={s}
                  className={`gp-win-btn gp-win-${s}${selections.who_wins === s ? ' selected' : ''}`}
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
              {blue.map((p) => <FbBtn key={p.championId} player={p} side="blue"
                selected={selections.first_blood} onSelect={setFb} disabled={!betsOpen} />)}
            </div>
            <div className="gp-fb-section">
              <div className="gp-fb-section-label red-label">⬡ Red side</div>
              {red.map((p) => <FbBtn key={p.championId} player={p} side="red"
                selected={selections.first_blood} onSelect={setFb} disabled={!betsOpen} />)}
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
                : selList.map((s, i) => {
                    const isFb = s.type === 'first_blood'
                    return (
                      <div key={i} className="gp-slip-row">
                        {isFb && champIcon(s.value) &&
                          <img src={champIcon(s.value)} className="gp-slip-champ-icon" alt=""
                            onError={e => { e.target.style.display = 'none' }} />}
                        <span className="gp-slip-label">{isFb ? '🩸 First Blood' : '🏆 Victoire'}</span>
                        <span className="gp-slip-val" style={{
                          color: s.value === 'blue' ? '#378add' : s.value === 'red' ? '#ef4444' : '#00e5ff'
                        }}>{s.value}</span>
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
                {[100, 500, 1000].map(v => (
                  <button key={v} className="gp-preset"
                    onClick={() => setAmount(String(v))} disabled={!betsOpen}>{v}</button>
                ))}
                <button className="gp-preset gp-preset-max"
                  onClick={() => setAmount(String(user?.coins || 0))} disabled={!betsOpen}>MAX</button>
              </div>
            </div>
            {gain > 0 &&
              <div className="gp-gain">Gain potentiel <strong>{gain.toLocaleString()} coins</strong></div>}
            {betError && <div className="gp-bet-error">{betError}</div>}
            {betDone  && <div className="gp-bet-success">✓ Pari placé ! Solde : {betDone.coins_restants?.toLocaleString()} coins</div>}
            <button className="gp-place-btn" onClick={handleBet}
              disabled={!betsOpen || submitting || !selList.length || !amount}>
              {!betsOpen   ? '🔒 Paris fermés'
               : submitting ? 'Placement...'
               : `Parier ${amount ? parseInt(amount).toLocaleString() : '—'} coins`}
            </button>
            {user && <div className="gp-balance">Solde : {user.coins?.toLocaleString()} coins</div>}
          </div>
        </div>
      </div>
    </div>
  )
}