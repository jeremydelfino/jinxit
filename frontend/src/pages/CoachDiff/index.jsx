import './CoachDiff.css'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import { startGame, getHistory } from '../../api/coachdiff'

const ENTRY_COST = 5

const OPPONENTS = [
  { code: 'KC', name: 'Karmine Corp', short: 'KC', diff: 'Facile',    level: 1, accent: '#1f8fff', tag: 'Drafts lisibles, laisse passer des erreurs' },
  { code: 'G2', name: 'G2 Esports',   short: 'G2', diff: 'Moyen',     level: 2, accent: '#e8b53a', tag: 'Méta solide, punit tes écarts' },
  { code: 'T1', name: 'T1',           short: 'T1', diff: 'Difficile', level: 3, accent: '#e3203a', tag: 'Drafts optimales, counters chirurgicaux' },
]

export default function CoachDiff() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [loading, setLoading]       = useState(true)
  const [starting, setStarting]     = useState(false)
  const [resumeGame, setResumeGame] = useState(null)
  const [error, setError]           = useState(null)
  const [logos, setLogos]           = useState({})
  const [selected, setSelected]     = useState(null)

  /* ─── Détection partie en cours ─── */
  useEffect(() => {
    if (!user) { setLoading(false); return }
    getHistory()
      .then(games => {
        const inProgress = games?.find(g => g.status === 'in_progress')
        if (inProgress) setResumeGame(inProgress)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  /* ─── Logos équipes (depuis la DB esports) ─── */
  useEffect(() => {
    let alive = true
    Promise.all(OPPONENTS.map(o =>
      api.get(`/esports/teams/${o.code}`)
        .then(r => [o.code, r.data?.logo_url || null])
        .catch(() => [o.code, null])
    )).then(pairs => { if (alive) setLogos(Object.fromEntries(pairs)) })
    return () => { alive = false }
  }, [])

  /* ─── Lancer ─── */
  const handleStart = async () => {
    if (starting || !selected) return
    setStarting(true); setError(null)
    try {
      const game = await startGame(selected)
      navigate(`/games/coachdiff/${game.id}`)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Impossible de lancer la partie')
      setStarting(false)
    }
  }

  const handleResume = () => navigate(`/games/coachdiff/${resumeGame.id}`)

  /* ─── Pas connecté ─── */
  if (!user) {
    return (
      <div className="cd-page">
        <div className="cd-locked">
          <div className="cd-locked-icon">🔒</div>
          <div className="cd-locked-title">Connecte-toi pour jouer</div>
          <button className="cd-btn-primary" onClick={() => navigate('/login')}>Se connecter</button>
        </div>
      </div>
    )
  }

  const coins  = user.coins ?? 0
  const canPay = coins >= ENTRY_COST

  return (
    <div className="cd-page">
      <div className="cd-glow" aria-hidden="true" />

      {/* ─── HERO ─── */}
      <header className="cd-hero">
        <div className="cd-eyebrow">COACHDIFF</div>
        <h1 className="cd-title">Choisis ton adversaire</h1>
      </header>

        {/* ─── BUT DU JEU ─── */}
        <div className="cd-howto">
          <div className="cd-howto-goal"><span>🎯</span> Drafte une meilleure compo que le bot</div>
          <div className="cd-howto-steps">
            <div className="cd-step"><span className="cd-step-ico">⚔️</span><span>Bans &amp; picks façon tournois</span></div>
            <span className="cd-step-arrow">→</span>
            <div className="cd-step"><span className="cd-step-ico">🧩</span><span>Assigne tes rôles</span></div>
            <span className="cd-step-arrow">→</span>
            <div className="cd-step"><span className="cd-step-ico">🏆</span><span>Meilleure draft /100 gagne</span></div>
          </div>
        </div>

      {/* ─── REPRENDRE ─── */}
      {resumeGame && (
        <button className="cd-resume" onClick={handleResume}>
          <span className="cd-resume-dot" />
          <span>Partie en cours — reprendre</span>
          <span className="cd-resume-arrow">→</span>
        </button>
      )}

      {/* ─── TEAMS ─── */}
      <div className="cd-teams">
        {OPPONENTS.map((o, i) => {
          const isSel = selected === o.code
          return (
            <button
              key={o.code}
              className={`cd-team ${isSel ? 'selected' : ''}`}
              style={{ '--accent': o.accent, animationDelay: `${0.06 * i}s` }}
              onClick={() => setSelected(o.code)}
            >
              <div className="cd-team-glow" />
              <div className="cd-team-logo">
                {logos[o.code]
                  ? <img src={logos[o.code]} alt={o.name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                  : <span className="cd-team-initials">{o.short}</span>}
              </div>
              <div className="cd-team-body">
                <div className="cd-team-name">{o.name}</div>
                <div className="cd-team-diff">
                  <div className="cd-pips">
                    {[1, 2, 3].map(n => <span key={n} className={`cd-pip ${n <= o.level ? 'on' : ''}`} />)}
                  </div>
                  <span className="cd-diff-label">{o.diff}</span>
                </div>
                <div className="cd-team-tag">{o.tag}</div>
              </div>
              {isSel && <div className="cd-team-check">✓</div>}
            </button>
          )
        })}
      </div>

      {/* ─── START ─── */}
      <div className="cd-launch">
        {error && <div className="cd-error-msg">{error}</div>}
        <button className="cd-start" disabled={!selected || !canPay || starting} onClick={handleStart}>
          {starting
            ? 'Lancement…'
            : !selected
              ? 'Sélectionne une équipe'
              : !canPay
                ? `Pas assez de coins (${ENTRY_COST} 🪙)`
                : <>Lancer la draft <span className="cd-cost">−{ENTRY_COST} 🪙</span></>}
        </button>
      </div>

    </div>
  )
}