import './Games.css'
import { useNavigate } from 'react-router-dom'

const GAMES = [
  { id: 'coachdiff', path: '/games/coachdiff', img: '/coachdiff.png', alt: 'CoachDiff', available: true },
  { id: 'soon-1',    path: null,               img: '/soon.png',      alt: 'À venir',  available: false },
]

export default function Games() {
  const navigate = useNavigate()

  return (
    <div className="games-page">

      {/* ─── HERO ─── */}
      <section className="games-hero">
        <div className="games-hero-eyebrow">JUNGLEGAP GAMES</div>
        <h1 className="games-hero-title">Choisis ton mode de jeu</h1>
      </section>

      {/* ─── GRID ─── */}
      <section className="games-grid">
        {GAMES.map(g => (
          <button
            key={g.id}
            className={`game-card ${!g.available ? 'disabled' : ''}`}
            onClick={() => g.available && navigate(g.path)}
            disabled={!g.available}
          >
            <img className="game-card-img" src={g.img} alt={g.alt} loading="lazy" />
          </button>
        ))}
      </section>

    </div>
  )
}