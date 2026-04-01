import './Game.css'
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

const DDV = '14.24.1'
const ROLE_ORDER  = ['TOP','JUNGLE','MID','ADC','SUPPORT','FILL']
const ROLE_ICONS  = { TOP:'🛡️', JUNGLE:'🌿', MID:'⚡', ADC:'🏹', SUPPORT:'💙', FILL:'❓' }
const ROLE_LABELS = { TOP:'TOP', JUNGLE:'JUNGLE', MIDDLE:'MID', MID:'MID', BOTTOM:'ADC', ADC:'ADC', UTILITY:'SUPPORT', SUPPORT:'SUPPORT' }

const SIDE_BET_TYPES  = new Set(['who_wins','first_tower','first_dragon','first_baron','jungle_gap'])
const CHAMP_BET_TYPES = new Set(['first_blood','player_positive_kda','champion_kda_over25','champion_kda_over5','champion_kda_over10','top_damage'])
const DURATION_SLUGS  = ['game_duration_under25','game_duration_25_35','game_duration_over35']

const BET_META = {
  who_wins:              { icon:'🏆', label:'Victoire'      },
  first_blood:           { icon:'🩸', label:'First Blood'   },
  first_tower:           { icon:'🗼', label:'1ère tour'     },
  first_dragon:          { icon:'🐉', label:'1er dragon'    },
  first_baron:           { icon:'👁️', label:'1er Baron'     },
  game_duration_under25: { icon:'⚡', label:'< 25 min'      },
  game_duration_25_35:   { icon:'⏱️', label:'25–35 min'     },
  game_duration_over35:  { icon:'🐢', label:'> 35 min'      },
  player_positive_kda:   { icon:'📊', label:'KDA positif'   },
  champion_kda_over25:   { icon:'⚔️', label:'KDA > 2.5'     },
  champion_kda_over5:    { icon:'🔥', label:'KDA > 5'       },
  champion_kda_over10:   { icon:'💀', label:'KDA > 10'      },
  top_damage:            { icon:'💥', label:'Top dégâts'    },
  jungle_gap:            { icon:'🌿', label:'Jungle Gap'    },
}

// ─── Helpers ──────────────────────────────────────────────────
function normR(r) { return r ? (ROLE_LABELS[r.toUpperCase()] ?? r) : 'FILL' }

function useLiveTimer(init) {
  const [s, setS] = useState(init ?? 0)
  const ref = useRef(null)
  const cur = useRef(init ?? 0)
  useEffect(() => {
    if (init == null) return
    if (Math.abs(init - cur.current) > 5) { setS(init); cur.current = init }
    if (ref.current) return
    ref.current = setInterval(() => { cur.current += 1; setS(x => x + 1) }, 1000)
    return () => { clearInterval(ref.current); ref.current = null }
  }, [init])
  return s
}

const fmt   = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
const cIcon = n => (n && n !== 'Unknown') ? `https://ddragon.leagueoflegends.com/cdn/${DDV}/img/champion/${n}.png` : null
const cSpl  = n => (n && n !== 'Unknown') ? `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${n}_0.jpg` : null
const fmtO  = v => v ? `×${Number(v).toFixed(2)}` : null

function getOdds(od, slug, value) {
  if (!od) return null
  if (SIDE_BET_TYPES.has(slug)) return od[slug]?.[value] ?? null
  return od[slug] ?? null
}

// ─── Draft composants ─────────────────────────────────────────
function SplashCell({ player, side }) {
  const splash = cSpl(player?.championName)
  return (
    <div className="gp-splash-cell">
      {splash
        ? <img src={splash} alt={player?.championName} className="gp-splash-img" onError={e => { e.target.style.display = 'none' }} />
        : <div className="gp-splash-placeholder">{player?.championName?.slice(0, 2) ?? '?'}</div>}
      <div className={`gp-splash-overlay ${side === 'blue' ? 'gp-splash-fade-right' : 'gp-splash-fade-left'}`} />
    </div>
  )
}

function PlayerRow({ player, side }) {
  const role = player?.role || 'FILL'
  return (
    <div className="gp-player-row">
      <div className="gp-player-pseudo">
        {player?.pro && <span className="gp-pro-badge">{player.pro.team}</span>}
        {player?.summonerName || '—'}
      </div>
      <div className="gp-player-name">{player?.championName || '?'}</div>
      <div className={`gp-player-role ${side}`}>
        <span>{ROLE_ICONS[role] ?? '❓'}</span>
        <span>{role}</span>
      </div>
    </div>
  )
}

// ─── Picker modal ─────────────────────────────────────────────
function ChampPicker({ blue, red, title, selected, onSelect, onClose }) {
  return (
    <div className="gp-picker-overlay" onClick={onClose}>
      <div className="gp-picker" onClick={e => e.stopPropagation()}>
        <div className="gp-picker-header">
          <span>{title}</span>
          <button onClick={onClose}>✕</button>
        </div>
        <div className="gp-picker-sides">
          {[{ team: blue, side: 'blue' }, { team: red, side: 'red' }].map(({ team, side }) => (
            <div key={side} className="gp-picker-side">
              <div className={`gp-picker-label ${side}-label`}>{side === 'blue' ? '⬡ Blue side' : '⬡ Red side'}</div>
              {team.map((p, i) => {
                const name = p.championName
                const isSel = selected === name
                return (
                  <button key={i} className={`gp-picker-btn gp-picker-${side}${isSel ? ' sel' : ''}`} onClick={() => onSelect(name)}>
                    <div className="gp-picker-icon">
                      {cIcon(name)
                        ? <img src={cIcon(name)} alt="" onError={e => { e.target.style.display = 'none' }} />
                        : <span>{name?.slice(0, 2)}</span>}
                    </div>
                    <div className="gp-picker-info">
                      <span className="gp-picker-champ">{name || '?'}</span>
                      <span className="gp-picker-player">{ROLE_ICONS[p.role] || ''} {p.summonerName || '—'}</span>
                    </div>
                    {isSel && <span className="gp-check">✓</span>}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function slipLabel(type, value) {
  const m = BET_META[type]; if (!m) return value
  if (SIDE_BET_TYPES.has(type))      return `${m.icon} ${m.label} — ${value === 'blue' ? 'Blue' : value === 'red' ? 'Red' : value}`
  if (DURATION_SLUGS.includes(type)) return `${m.icon} ${m.label}`
  return `${m.icon} ${m.label} — ${value}`
}

// ─── Page ─────────────────────────────────────────────────────
export default function Game() {
  const { id }               = useParams()
  const navigate             = useNavigate()
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
  const [activeTab,  setActiveTab]  = useState('objectives')
  const [picker,     setPicker]     = useState(null)

  const liveSeconds = useLiveTimer(game?.duration_seconds ?? 0)
  const od = game?.odds_data ?? null

  // ── DDragon : uniquement pour résoudre championId → name ──
  useEffect(() => {
    fetch(`https://ddragon.leagueoflegends.com/cdn/${DDV}/data/en_US/champion.json`)
      .then(r => r.json())
      .then(d => {
        const m = {}
        Object.values(d.data).forEach(c => { m[String(parseInt(c.key))] = c.id })
        setChampMap(m)
      })
      .catch(() => {})
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

  // ── processTeam : uniquement normalisation + tri ──────────
  // Les rôles viennent du backend (role_detector.py via game_poller.py)
  const processTeam = useCallback((team) => {
    if (!team) return []
    return team
      .map(p => ({
        ...p,
        // Fallback championId → name si le backend n'a pas résolu le nom
        championName: (p.championName?.trim() && p.championName !== 'Unknown')
          ? p.championName.trim()
          : (p.championId ? champMap[String(p.championId)] : null) ?? null,
        // Rôle vient du backend, on normalise juste la casse
        role: normR(p.role),
      }))
      .sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role))
  }, [champMap])

  const blue   = useMemo(() => processTeam(game?.blue_team), [game?.blue_team, processTeam])
  const red    = useMemo(() => processTeam(game?.red_team),  [game?.red_team,  processTeam])
  const jgBlue = useMemo(() => blue.find(p => p.role === 'JUNGLE'), [blue])
  const jgRed  = useMemo(() => red.find(p => p.role === 'JUNGLE'),  [red])
  const betsOpen = game?.status !== 'ended'

  // ── Sélections ────────────────────────────────────────────
  const toggle = (slug, value) => {
    if (!betsOpen) return
    setSelections(prev => { const k = `${slug}::${value}`, n = { ...prev }; n[k] ? delete n[k] : n[k] = { slug, value }; return n })
  }
  const setDur = (slug) => {
    if (!betsOpen) return
    setSelections(prev => {
      const n = { ...prev }
      DURATION_SLUGS.forEach(s => Object.keys(n).filter(k => k.startsWith(s + '::')).forEach(k => delete n[k]))
      const k = `${slug}::confirmed`; n[k] ? delete n[k] : n[k] = { slug, value: 'confirmed' }; return n
    })
  }
  const isSel   = (slug, value) => !!selections[`${slug}::${value}`]
  const champOf = (slug) => Object.values(selections).find(s => s.slug === slug)?.value ?? null
  const durSel  = DURATION_SLUGS.find(s => !!selections[`${s}::confirmed`])

  const selList      = Object.values(selections).map(({ slug, value }) => ({ type: slug, value, odds: getOdds(od, slug, value) ?? 2.0 }))
  const combinedOdds = selList.reduce((a, s) => a * s.odds, 1)
  const gain         = amount ? Math.floor(parseInt(amount) * combinedOdds) : 0

  // ── Submit avec slip_id unique par soumission ─────────────
  const handleBet = async () => {
    if (!selList.length)             { setBetError('Choisis au moins une sélection'); return }
    if (!amount || parseInt(amount) < 1) { setBetError('Montant invalide'); return }
    if (!user)                       { navigate('/login'); return }
    setSubmitting(true); setBetError(null); setBetDone(null)
    const slipId = crypto.randomUUID()
    try {
      let last = null
      for (const s of selList) {
        const r = await api.post('/bets/place', {
          live_game_id: game.id, bet_type_slug: s.type,
          bet_value: s.value, amount: parseInt(amount), slip_id: slipId,
        })
        last = r.data
      }
      setBetDone(last)
      if (last?.coins_restants !== undefined) updateCoins(last.coins_restants)
      setSelections({}); setAmount('')
    } catch (e) {
      setBetError(e.response?.data?.detail || 'Erreur lors du pari')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !Object.keys(champMap).length) return <div className="gp-page"><div className="gp-loading"><div className="gp-spinner" /><span>Chargement de la faille...</span></div></div>
  if (error) return <div className="gp-page"><div className="gp-error"><div className="gp-error-title">Partie introuvable</div><button className="gp-back-btn" onClick={() => navigate('/')}>← Retour</button></div></div>

  const PickBtn = ({ slug, title }) => {
    const val = champOf(slug)
    return (
      <button className="gp-pick-btn" onClick={() => setPicker({ slug, title })} disabled={!betsOpen}>
        {val
          ? <><div className="gp-pick-icon">{cIcon(val) && <img src={cIcon(val)} alt="" onError={e => { e.target.style.display = 'none' }} />}</div><span className="gp-pick-val">{val}</span><button className="gp-pick-clear" onClick={e => { e.stopPropagation(); toggle(slug, val) }}>✕</button></>
          : <span>Choisir →</span>}
      </button>
    )
  }

  const tabs = {
    objectives: (
      <div className="gp-tc">
        <div className="gp-tc-section">
          <div className="gp-tc-label">🏆 Victoire</div>
          <div className="gp-side-row">
            {['blue', 'red'].map(s => (
              <button key={s} className={`gp-side-btn gp-side-${s}${isSel('who_wins', s) ? ' sel' : ''}`} onClick={() => toggle('who_wins', s)} disabled={!betsOpen}>
                <span className={`gp-dot ${s}-dot`} /><span>{s === 'blue' ? 'Blue side' : 'Red side'}</span>
                {od?.who_wins?.[s] && <span className="gp-chip">{fmtO(od.who_wins[s])}</span>}
                {isSel('who_wins', s) && <span className="gp-check">✓</span>}
              </button>
            ))}
          </div>
        </div>
        {[
          { slug: 'first_tower',  icon: '🗼', label: 'Première tour'  },
          { slug: 'first_dragon', icon: '🐉', label: 'Premier dragon' },
          { slug: 'first_baron',  icon: '👁️', label: 'Premier Baron'  },
        ].map(({ slug, icon, label }) => (
          <div key={slug} className="gp-tc-section">
            <div className="gp-tc-label">{icon} {label}</div>
            <div className="gp-side-row">
              {['blue', 'red'].map(s => (
                <button key={s} className={`gp-side-btn gp-side-${s}${isSel(slug, s) ? ' sel' : ''}`} onClick={() => toggle(slug, s)} disabled={!betsOpen}>
                  <span className={`gp-dot ${s}-dot`} /><span>{s === 'blue' ? 'Blue' : 'Red'}</span>
                  {od?.[slug]?.[s] && <span className="gp-chip">{fmtO(od[slug][s])}</span>}
                  {isSel(slug, s) && <span className="gp-check">✓</span>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    ),
    duration: (
      <div className="gp-tc">
        {[
          { slug: 'game_duration_under25', icon: '⚡', label: 'Moins de 25 min',    sub: 'Stompe rapide'   },
          { slug: 'game_duration_25_35',   icon: '⏱️', label: 'Entre 25 et 35 min', sub: 'Durée standard'  },
          { slug: 'game_duration_over35',  icon: '🐢', label: 'Plus de 35 min',     sub: 'Late game'       },
        ].map(({ slug, icon, label, sub }) => (
          <button key={slug} className={`gp-dur-card${durSel === slug ? ' sel' : ''}`} onClick={() => setDur(slug)} disabled={!betsOpen}>
            <span className="gp-dur-icon">{icon}</span>
            <div className="gp-dur-info"><div className="gp-dur-label">{label}</div><div className="gp-dur-sub">{sub}</div></div>
            {od?.[slug] && <span className="gp-chip">{fmtO(od[slug])}</span>}
            {durSel === slug && <span className="gp-check">✓</span>}
          </button>
        ))}
      </div>
    ),
    performance: (
      <div className="gp-tc">
        {[
          { slug: 'first_blood',         icon: '🩸', label: 'First Blood',  sub: 'Quel champion fera le 1er kill ?' },
          { slug: 'top_damage',          icon: '💥', label: 'Top dégâts',   sub: 'Meilleur dégât total de la game'  },
          { slug: 'player_positive_kda', icon: '📊', label: 'KDA positif',  sub: 'K+A supérieur aux deaths'         },
          { slug: 'champion_kda_over25', icon: '⚔️', label: 'KDA > 2.5',    sub: 'En fin de partie'                 },
          { slug: 'champion_kda_over5',  icon: '🔥', label: 'KDA > 5',      sub: 'En fin de partie'                 },
          { slug: 'champion_kda_over10', icon: '💀', label: 'KDA > 10',     sub: 'En fin de partie'                 },
        ].map(({ slug, icon, label, sub }) => (
          <div key={slug} className="gp-perf-row">
            <div className="gp-perf-left">
              <span className="gp-perf-icon">{icon}</span>
              <div><div className="gp-perf-name">{label}</div><div className="gp-perf-sub">{sub}</div></div>
              {od?.[slug] && <span className="gp-chip">{fmtO(od[slug])}</span>}
            </div>
            <PickBtn slug={slug} title={`${icon} ${label} — Choisir`} />
          </div>
        ))}
      </div>
    ),
  }

  return (
    <div className="gp-page">
      <div className="gp-ambient"><div className="gp-amb-blue" /><div className="gp-amb-red" /></div>

      <div className="gp-topbar">
        <button className="gp-back" onClick={() => navigate('/')}>← Retour</button>
        <div className="gp-topbar-c">
          <div className="gp-live-pill"><span className="gp-live-dot" />LIVE</div>
          <span className="gp-queue">{game.queue_type || 'Ranked Solo'}</span>
          <span className="gp-timer">{fmt(liveSeconds)}</span>
        </div>
        <div className={`gp-badge ${betsOpen ? 'open' : 'closed'}`}>{betsOpen ? '✓ Paris ouverts' : '🔒 Fermés'}</div>
      </div>

      <div className="gp-bento">
        <div className="gp-draft-block">
          <div className="gp-col-info gp-col-info-blue">
            <div className="gp-side-header blue"><span className="gp-side-bar blue-bar" />BLUE SIDE</div>
            {blue.map((p, i) => <PlayerRow key={p.championId ?? i} player={p} side="blue" />)}
          </div>
          <div className="gp-col-splash gp-col-splash-blue">
            <div style={{ height: 37 }} />
            {blue.map((p, i) => <SplashCell key={p.championId ?? i} player={p} side="blue" />)}
          </div>
          <div className="gp-vs-col"><div className="gp-vs-ring"><span className="gp-vs-text">VS</span></div></div>
          <div className="gp-col-splash gp-col-splash-red">
            <div style={{ height: 37 }} />
            {red.map((p, i) => <SplashCell key={p.championId ?? i} player={p} side="red" />)}
          </div>
          <div className="gp-col-info gp-col-info-red">
            <div className="gp-side-header red">RED SIDE<span className="gp-side-bar red-bar" /></div>
            {red.map((p, i) => <PlayerRow key={p.championId ?? i} player={p} side="red" />)}
          </div>
        </div>

        <div className="gp-bets-layout">
          <div className="gp-jg">
            <div className="gp-jg-glow" />
            <div className="gp-jg-left">
              <div className="gp-jg-badge">🌿 JUNGLE GAP</div>
              <div className="gp-jg-title">Y a-t-il un <span className="gp-jg-accent">Jungle Gap</span> ?</div>
              <div className="gp-jg-sub">Si un jungler écrase l'autre, c'est un gap. <strong style={{ color: '#378add' }}>Gap Blue</strong> = le jungler Blue domine.</div>
            </div>
            <div className="gp-jg-center">
              <div className="gp-jg-p">
                {jgBlue && cIcon(jgBlue.championName) && <img src={cIcon(jgBlue.championName)} alt="" className="gp-jg-icon" />}
                <span style={{ color: '#378add', fontWeight: 700, fontSize: 12 }}>{jgBlue?.summonerName || 'Blue JG'}</span>
              </div>
              <span className="gp-jg-vs">VS</span>
              <div className="gp-jg-p">
                {jgRed && cIcon(jgRed.championName) && <img src={cIcon(jgRed.championName)} alt="" className="gp-jg-icon" />}
                <span style={{ color: '#ef4444', fontWeight: 700, fontSize: 12 }}>{jgRed?.summonerName || 'Red JG'}</span>
              </div>
            </div>
            <div className="gp-jg-btns">
              <button className={`gp-jg-btn jg-blue${isSel('jungle_gap', 'blue') ? ' sel' : ''}`} onClick={() => toggle('jungle_gap', 'blue')} disabled={!betsOpen}>
                🟦 Gap Blue{od?.jungle_gap?.blue && <span className="gp-chip">{fmtO(od.jungle_gap.blue)}</span>}
              </button>
              <button className={`gp-jg-btn jg-none${isSel('jungle_gap', 'none') ? ' sel' : ''}`} onClick={() => toggle('jungle_gap', 'none')} disabled={!betsOpen}>⚖️ Aucun</button>
              <button className={`gp-jg-btn jg-red${isSel('jungle_gap', 'red') ? ' sel' : ''}`} onClick={() => toggle('jungle_gap', 'red')} disabled={!betsOpen}>
                🟥 Gap Red{od?.jungle_gap?.red && <span className="gp-chip">{fmtO(od.jungle_gap.red)}</span>}
              </button>
            </div>
          </div>

          <div className="gp-tabs-block">
            <div className="gp-tabs">
              {[{ k: 'objectives', l: '🎯 Objectifs' }, { k: 'duration', l: '⏱️ Durée' }, { k: 'performance', l: '⚔️ Performance' }].map(({ k, l }) => (
                <button key={k} className={`gp-tab${activeTab === k ? ' active' : ''}`} onClick={() => setActiveTab(k)}>{l}</button>
              ))}
            </div>
            <div className="gp-tab-panel">{tabs[activeTab]}</div>
          </div>

          <div className="gp-slip">
            <div className="gp-slip-head">
              <span>🎰 Mon pari</span>
              {selList.length > 0 && <span className="gp-slip-count">{selList.length}</span>}
              {selList.length > 0 && <span className="gp-slip-combo">×{combinedOdds.toFixed(2)}</span>}
            </div>
            <div className="gp-slip-body">
              {selList.length === 0
                ? <div className="gp-slip-empty">Aucune sélection</div>
                : selList.map((s, i) => (
                  <div key={i} className="gp-slip-row">
                    {CHAMP_BET_TYPES.has(s.type) && cIcon(s.value) && <img src={cIcon(s.value)} className="gp-slip-ci" alt="" onError={e => { e.target.style.display = 'none' }} />}
                    <span className="gp-slip-lbl">{slipLabel(s.type, s.value)}</span>
                    <span className="gp-slip-x">{fmtO(s.odds)}</span>
                    <button className="gp-slip-rm" onClick={() => setSelections(p => { const n = { ...p }; delete n[`${s.type}::${s.value}`]; return n })}>✕</button>
                  </div>
                ))
              }
            </div>
            <div className="gp-slip-foot">
              <div className="gp-amount-row">
                <input className="gp-amount" type="number" min="1" placeholder="Mise..." value={amount} onChange={e => setAmount(e.target.value)} disabled={!betsOpen} />
                <div className="gp-presets">
                  {[100, 500, 1000].map(v => <button key={v} className="gp-preset" onClick={() => setAmount(String(v))} disabled={!betsOpen}>{v}</button>)}
                  <button className="gp-preset gp-preset-max" onClick={() => setAmount(String(user?.coins || 0))} disabled={!betsOpen}>MAX</button>
                </div>
              </div>
              {gain > 0   && <div className="gp-gain">Gain potentiel <strong>{gain.toLocaleString()} coins</strong></div>}
              {betError   && <div className="gp-msg err">{betError}</div>}
              {betDone    && <div className="gp-msg ok">✓ Pari placé ! {betDone.coins_restants?.toLocaleString()} coins</div>}
              <button className="gp-place-btn" onClick={handleBet} disabled={!betsOpen || submitting || !selList.length || !amount}>
                {!betsOpen ? '🔒 Paris fermés' : submitting ? 'Placement...' : `Parier ${amount ? parseInt(amount).toLocaleString() : '—'} coins`}
              </button>
              {user && <div className="gp-balance">Solde : {user.coins?.toLocaleString()} coins</div>}
            </div>
          </div>
        </div>
      </div>

      {picker && (
        <ChampPicker blue={blue} red={red} title={picker.title} selected={champOf(picker.slug)}
          onSelect={v => { toggle(picker.slug, v); setPicker(null) }} onClose={() => setPicker(null)} />
      )}
    </div>
  )
}