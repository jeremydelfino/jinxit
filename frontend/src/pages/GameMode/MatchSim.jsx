import { useEffect, useMemo, useRef, useState } from 'react'
import { getChampIcon } from '../CoachDiffGame/utils'
import './MatchSim.css'

const ROLES = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
const BLUE = '#4C9BE8', RED = '#E2574E', GRAY = '#5F5E5A'

const HOMES = {
  blue: { TOP: [58, 168], JUNGLE: [112, 205], MID: [140, 180], ADC: [165, 262], SUPPORT: [140, 250] },
  red:  { TOP: [155, 58], JUNGLE: [208, 115], MID: [180, 140], ADC: [262, 155], SUPPORT: [245, 182] },
}
const LANE_PT = { top: [92, 92], mid: [160, 160], bot: [230, 230], baron: [115, 115], drake: [205, 205] }

const TOWERS = [
  ['blue', 'top', 0, 50, 200], ['blue', 'top', 1, 50, 140],
  ['blue', 'mid', 0, 108, 212], ['blue', 'mid', 1, 150, 170],
  ['blue', 'bot', 0, 120, 270], ['blue', 'bot', 1, 180, 270],
  ['blue', 'nexus', 0, 72, 250],
  ['red', 'top', 0, 120, 50], ['red', 'top', 1, 180, 50],
  ['red', 'mid', 0, 170, 150], ['red', 'mid', 1, 212, 108],
  ['red', 'bot', 0, 270, 200], ['red', 'bot', 1, 270, 120],
  ['red', 'nexus', 0, 250, 70],
]

const abbr = n => (n || '?').replace(/[^A-Za-z]/g, '').slice(0, 3).toUpperCase()
const fmt = s => { const m = Math.floor(s / 60), ss = Math.floor(s % 60); return `${m < 10 ? '0' : ''}${m}:${ss < 10 ? '0' : ''}${ss}` }

export default function MatchSim({ timeline, userSide, version, onDone }) {
  const tl = timeline
  const tokens = useMemo(() => {
    const out = []
    for (const side of ['blue', 'red']) {
      const lanes = tl?.draft?.[side] || {}
      ROLES.forEach(role => out.push({
        id: `${side}:${role}`, side, role,
        champ: lanes[role] || '?', home: HOMES[side][role],
      }))
    }
    return out
  }, [tl])

  const gEls = useRef({}), towEls = useRef({})
  const pos = useRef({}), tow = useRef([])
  const clkRef = useRef(0), idxRef = useRef(0)
  const runRef = useRef(true), speedRef = useRef(1)

  const [clk, setClk] = useState(0)
  const [score, setScore] = useState({ blue: 0, red: 0 })
  const [obj, setObj] = useState({ blue: { d: 0, b: 0 }, red: { d: 0, b: 0 } })
  const [feed, setFeed] = useState([])
  const [running, setRunning] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [ended, setEnded] = useState(false)

  const pushFeed = (side, txt) => setFeed(f => [{ side, txt, k: Math.random() }, ...f].slice(0, 6))

  function processEvent(e) {
    const t = e.type
    if (t === 'kill' || t === 'first_blood') {
      setScore(s => ({ ...s, [e.side]: s[e.side] + 1 }))
      const pt = LANE_PT[e.lane] || LANE_PT.mid
      const involved = [`${e.side}:${e.killer.role}`, ...(e.assists || []).map(r => `${e.side}:${r}`)]
      const loseSide = e.side === 'blue' ? 'red' : 'blue'
      const vid = `${loseSide}:${e.victim.role}`
      involved.forEach(id => { const p = pos.current[id]; if (p && p.alive) { p.tx = pt[0] + (Math.random() * 18 - 9); p.ty = pt[1] + (Math.random() * 18 - 9); p.hold = clkRef.current + 5 } })
      const v = pos.current[vid]
      if (v) { v.alive = false; v.respawn = clkRef.current + 7; const g = gEls.current[vid]; if (g) g.style.opacity = '0.3' }
      pushFeed(e.side, `${t === 'first_blood' ? 'First blood — ' : ''}${e.killer.champ} ⟶ ${e.victim.champ}`)
    } else if (t === 'tower') {
      const enemy = e.side === 'blue' ? 'red' : 'blue'
      const target = tow.current.find(x => x.alive && x.side === enemy && x.lane === e.lane)
        || tow.current.find(x => x.alive && x.side === enemy)
      if (target) { target.alive = false; const r = towEls.current[target.tid]; if (r) { r.setAttribute('fill', GRAY); r.setAttribute('opacity', '0.18'); r.setAttribute('stroke', 'none') } }
      pushFeed(e.side, `${e.side === 'blue' ? 'Blue' : 'Red'} détruit une tourelle`)
    } else if (t === 'drake') { setObj(o => ({ ...o, [e.side]: { ...o[e.side], d: o[e.side].d + 1 } })); pushFeed(e.side, `${e.side === 'blue' ? 'Blue' : 'Red'} prend le Dragon`) }
    else if (t === 'baron') { setObj(o => ({ ...o, [e.side]: { ...o[e.side], b: o[e.side].b + 1 } })); pushFeed(e.side, `${e.side === 'blue' ? 'Blue' : 'Red'} prend le Baron`) }
    else if (t === 'herald') pushFeed(e.side, `${e.side === 'blue' ? 'Blue' : 'Red'} prend le Héraut`)
    else if (t === 'ace') pushFeed(e.side, `${e.side === 'blue' ? 'Blue' : 'Red'} ACE`)
    else if (t === 'nexus') pushFeed(e.side, `Nexus tombé — victoire ${e.side === 'blue' ? 'Blue' : 'Red'}`)
  }

  function finish() {
    while (idxRef.current < tl.events.length) processEvent(tl.events[idxRef.current++])
    clkRef.current = tl.duration; setClk(tl.duration); setEnded(true); runRef.current = false; setRunning(false)
  }

  useEffect(() => {
    tokens.forEach(t => { pos.current[t.id] = { x: t.home[0], y: t.home[1], tx: t.home[0], ty: t.home[1], alive: true, respawn: 0, hold: 0, home: t.home } })
    tow.current = TOWERS.map(([side, lane, idx, x, y]) => ({ tid: `${side}-${lane}-${idx}`, side, lane, idx, x, y, alive: true }))
    const iv = setInterval(() => {
      if (!runRef.current) return
      clkRef.current += 1.4 * speedRef.current
      const now = clkRef.current
      while (idxRef.current < tl.events.length && tl.events[idxRef.current].t <= now) processEvent(tl.events[idxRef.current++])
      tokens.forEach(t => {
        const p = pos.current[t.id]; if (!p) return
        if (!p.alive) { if (now >= p.respawn) { p.alive = true; p.x = p.home[0]; p.y = p.home[1]; p.tx = p.home[0]; p.ty = p.home[1]; const g = gEls.current[t.id]; if (g) g.style.opacity = '1' } return }
        if (now > p.hold && Math.random() < 0.05) { p.tx = p.home[0] + (Math.random() * 18 - 9); p.ty = p.home[1] + (Math.random() * 18 - 9) }
        p.x += (p.tx - p.x) * 0.12; p.y += (p.ty - p.y) * 0.12
        const g = gEls.current[t.id]; if (g) g.setAttribute('transform', `translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`)
      })
      setClk(now)
      if (now >= tl.duration && !ended) finish()
    }, 70)
    return () => clearInterval(iv)
    // eslint-disable-next-line
  }, [tokens])

  const toggle = () => { const r = !runRef.current; runRef.current = r; setRunning(r) }
  const cycleSpeed = () => { const s = speed === 1 ? 2 : speed === 2 ? 4 : 1; speedRef.current = s; setSpeed(s) }

  const mvp = tl?.summary?.players?.[0]

  return (
    <div className="ms-wrap">
      <div className="ms-scorebar">
        <div className="ms-side ms-blue">
          <span className="ms-side-lbl">Blue {userSide === 'BLUE' && <i>· toi</i>}</span>
          <span className="ms-side-k">{score.blue}</span>
        </div>
        <span className="ms-clk">{fmt(clk)}</span>
        <div className="ms-side ms-red">
          <span className="ms-side-k">{score.red}</span>
          <span className="ms-side-lbl">Red {userSide === 'RED' && <i>· toi</i>}</span>
        </div>
      </div>

      <div className="ms-map-box">
        <svg viewBox="0 0 320 320" className="ms-map" role="img">
          <clipPath id="ms-frame"><rect x="3" y="3" width="314" height="314" rx="14" /></clipPath>
          <g clipPath="url(#ms-frame)">
            <rect x="3" y="3" width="314" height="314" fill="#0f2238" />
            <rect x="40" y="40" width="240" height="240" rx="20" fill="#C9A227" opacity="0.08" />
            <path d="M50 270 L50 50 L270 50" fill="none" stroke="#C9A227" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" opacity="0.75" />
            <path d="M50 270 L270 270 L270 50" fill="none" stroke="#C9A227" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" opacity="0.75" />
            <path d="M50 270 L270 50" fill="none" stroke="#C9A227" strokeWidth="11" strokeLinecap="round" opacity="0.75" />
            <line x1="78" y1="78" x2="242" y2="242" stroke="#2E6FB0" strokeWidth="16" strokeLinecap="round" opacity="0.5" />
            <circle cx="52" cy="268" r="34" fill={BLUE} opacity="0.16" stroke={BLUE} strokeWidth="1.5" />
            <circle cx="268" cy="52" r="34" fill={RED} opacity="0.16" stroke={RED} strokeWidth="1.5" />
            <circle cx="115" cy="115" r="10" fill="#0f2238" stroke="#7F77DD" strokeWidth="2" />
            <circle cx="205" cy="205" r="10" fill="#0f2238" stroke="#EF9F27" strokeWidth="2" />
          </g>
          {TOWERS.map(([side, lane, idx, x, y]) => (
            <rect key={`${side}-${lane}-${idx}`} ref={el => { if (el) towEls.current[`${side}-${lane}-${idx}`] = el }}
              x={x - 5} y={y - 5} width="10" height="10" rx="2.5"
              fill={side === 'blue' ? BLUE : RED} opacity="0.9" stroke="#0f2238" strokeWidth="1.5" />
          ))}
          {tokens.map(t => {
            const col = t.side === 'blue' ? BLUE : RED
            const icon = getChampIcon(t.champ, version)
            return (
              <g key={t.id} ref={el => { if (el) gEls.current[t.id] = el }} transform={`translate(${t.home[0]},${t.home[1]})`} style={{ transition: 'opacity .3s' }}>
                <clipPath id={`clip-${t.id}`}><circle r="11" /></clipPath>
                <circle r="13" fill="#16314c" stroke={col} strokeWidth="2.5" />
                <text textAnchor="middle" y="3" fontSize="8.5" fontWeight="600" fill="#eaf2fb">{abbr(t.champ)}</text>
                {icon && <image href={icon} x="-11" y="-11" width="22" height="22" clipPath={`url(#clip-${t.id})`} referrerPolicy="no-referrer" />}
              </g>
            )
          })}
        </svg>
      </div>

      <div className="ms-controls">
        <button className="ms-btn" onClick={toggle} disabled={ended}>{running ? 'Pause' : 'Reprendre'}</button>
        <button className="ms-btn" onClick={cycleSpeed} disabled={ended}>×{speed}</button>
        <button className="ms-btn" onClick={finish} disabled={ended}>Passer</button>
        <div className="ms-obj">
          <span><b style={{ color: '#EF9F27' }}>◆</b> {obj.blue.d}–{obj.red.d}</span>
          <span><b style={{ color: '#7F77DD' }}>✦</b> {obj.blue.b}–{obj.red.b}</span>
        </div>
      </div>

      <div className="ms-feed">
        {feed.map(f => (
          <div key={f.k} className="ms-feed-line">
            <span className="ms-dot" style={{ color: f.side === 'blue' ? BLUE : (f.side === 'red' ? RED : GRAY) }}>●</span>{f.txt}
          </div>
        ))}
      </div>

      {ended && (
        <div className="ms-end">
          <div className="ms-end-score">{score.blue} – {score.red}</div>
          <div className="ms-end-win">Victoire {tl.winner === 'blue' ? 'Blue' : 'Red'}</div>
          {mvp && <div className="ms-end-mvp">MVP · {mvp.champ} — {mvp.k}/{mvp.d}/{mvp.a}</div>}
          <button className="ms-btn ms-btn-primary" onClick={onDone}>Voir le résultat</button>
        </div>
      )}
    </div>
  )
}