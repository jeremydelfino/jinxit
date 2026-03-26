import './Home.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import GameCard from '../../components/ui/GameCard'
import api from '../../api/client'

const REGIONS = [
  { value: 'EUW', label: 'EUW', color: '#378add' },
  { value: 'EUN', label: 'EUN', color: '#378add' },
  { value: 'NA',  label: 'NA',  color: '#22c55e' },
  { value: 'KR',  label: 'KR',  color: '#f59e0b' },
  { value: 'BR',  label: 'BR',  color: '#22c55e' },
  { value: 'JP',  label: 'JP',  color: '#ef4444' },
  { value: 'TR',  label: 'TR',  color: '#ef4444' },
]

const STATS = [
  { icon: '⚡', val: '1,247', label: 'Parties en direct',       color: '#00e5ff', bg: '#00e5ff12' },
  { icon: '🪙', val: '842K',  label: "Coins misés aujourd'hui", color: '#c89b3c', bg: '#c89b3c12' },
  { icon: '🎯', val: '3,891', label: 'Paris actifs',            color: '#d946a8', bg: '#d946a812' },
  { icon: '👥', val: '12,440',label: 'Joueurs inscrits',        color: '#22c55e', bg: '#22c55e12' },
]

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatGameForCard(game) {
  const blueTeam = game.blue_team ?? []
  const redTeam  = game.red_team  ?? []
  const players  = [...blueTeam, ...redTeam]
    .slice(0, 5)
    .map(p => p.summonerName?.slice(0, 2).toUpperCase() || '??')

  const blueKills = blueTeam.reduce((acc, p) => acc + (p.kills || 0), 0)
  const redKills  = redTeam.reduce((acc, p)  => acc + (p.kills || 0), 0)

  return {
    id:               game.id,
    riot_game_id:     game.riot_game_id,
    timer:            formatDuration(game.duration_seconds || 0),
    blueScore:        blueKills,
    redScore:         redKills,
    queue:            game.queue || 'Ranked Solo',
    region:           game.pro?.region || 'EUW',
    players,
    pro:              game.pro ? { ...game.pro } : null,
    blue_team:        blueTeam,
    red_team:         redTeam,
    duration_seconds: game.duration_seconds,
  }
}

export default function Home() {
  const navigate = useNavigate()
  const [search, setSearch]                   = useState('')
  const [region, setRegion]                   = useState('EUW')
  const [liveGames, setLiveGames]             = useState([])
  const [loading, setLoading]                 = useState(true)
  const [suggestions, setSuggestions]         = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)

  useEffect(() => {
    const fetchGames = async () => {
      try {
        const res = await api.get('/games/live')
        setLiveGames(res.data)
      } catch (e) {
        console.error('Erreur fetch games:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchGames()
    const interval = setInterval(fetchGames, 30 * 1000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (search.length < 2) { setSuggestions([]); return }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get(`/players/search/autocomplete?q=${encodeURIComponent(search)}`)
        setSuggestions(res.data)
        setShowSuggestions(true)
      } catch {}
    }, 200)
    return () => clearTimeout(timer)
  }, [search])

  const handleSearch = () => {
    if (!search.trim()) return
    const [name, tag] = search.split('#')
    navigate(`/player/${region}/${encodeURIComponent(name.trim())}/${(tag || region).trim()}`)
  }

  const handleSuggestionClick = (s) => {
    navigate(`/player/${s.region}/${encodeURIComponent(s.summoner_name)}/${s.tag_line}`)
    setShowSuggestions(false)
    setSearch('')
  }

  // ✅ Uniquement les games avec un pro joueur détecté
  const games = liveGames
    .filter(g => g.pro !== null)
    .map(formatGameForCard)

  return (
    <div className="home">
      <div className="bg-glow bg-glow-1" />
      <div className="bg-glow bg-glow-2" />
      <div className="bg-glow bg-glow-3" />

      {/* ─── HERO ─── */}
      <div className="hero">
        <div className="hero-eyebrow">Paris virtuels · League of Legends</div>
        <h1 className="hero-title">
          Parie sur les<br />
          <span className="accent">parties en direct</span>
        </h1>
        <p className="hero-sub">
          Recherche un joueur, regarde sa partie live<br />
          et mise tes coins virtuels
        </p>

        <div className="search-wrap" onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}>
          <div className="search-glow" />
          <input
            className="search-input"
            placeholder="Nom d'invocateur#TAG"
            value={search}
            onChange={e => { setSearch(e.target.value); setShowSuggestions(true) }}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          />
          <select
            className="search-region"
            value={region}
            onChange={e => setRegion(e.target.value)}
            style={{
              color:       REGIONS.find(r => r.value === region)?.color || '#e8eaf0',
              borderColor: (REGIONS.find(r => r.value === region)?.color || '#ffffff15') + '40',
              background:  (REGIONS.find(r => r.value === region)?.color || '#ffffff') + '12',
            }}
          >
            {REGIONS.map(r => (
              <option key={r.value} value={r.value} style={{ color: r.color, background: '#242424' }}>
                {r.label}
              </option>
            ))}
          </select>
          <button className="search-btn" onClick={handleSearch}>Rechercher</button>

          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions.map((s, i) => (
                <div key={i} className="suggestion-item" onMouseDown={() => handleSuggestionClick(s)}>
                  <div className="suggestion-icon">
                    {s.profile_icon_url ? (
                      <img src={s.profile_icon_url} alt="" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                    ) : s.summoner_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="suggestion-info">
                    <div className="suggestion-name">
                      {s.summoner_name}
                      <span className="suggestion-tag">#{s.tag_line}</span>
                    </div>
                    <div className="suggestion-meta">
                      {s.tier ? `${s.tier} ${s.rank}` : 'Non classé'} · {s.region}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── STATS ─── */}
      <div className="stats-bar">
        {STATS.map((s, i) => (
          <div className="stat-item" key={i}>
            <div className="stat-icon" style={{ background: s.bg }}>{s.icon}</div>
            <div>
              <div className="stat-val" style={{ color: s.color }}>{s.val}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ─── GAMES ─── */}
      <div className="section">
        <div className="section-header">
          <div className="section-title">
            Parties en cours
            <span className="live-pill"><span className="live-dot" />LIVE</span>
          </div>
          <span className="section-link">Voir tout →</span>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#4b5563', fontFamily: 'Inter, sans-serif', fontSize: '14px' }}>
            Chargement des parties en direct...
          </div>
        ) : games.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#4b5563', fontFamily: 'Inter, sans-serif', fontSize: '14px' }}>
            Aucune partie de pro en cours pour le moment.<br />
            <span style={{ fontSize: '12px', color: '#374151' }}>Le système vérifie automatiquement toutes les 3 minutes.</span>
          </div>
        ) : (
          <div className="games-grid">
            {games.map(game => (
              <GameCard
                key={game.id}
                game={game}
                onBet={g => navigate(`/game/${g.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}