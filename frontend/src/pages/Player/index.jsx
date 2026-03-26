import './Player.css'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../../api/client'

const TIER_COLORS = {
  CHALLENGER: '#f4c430', GRANDMASTER: '#ef4444', MASTER: '#a78bfa',
  DIAMOND: '#378add', EMERALD: '#22c55e', PLATINUM: '#00e5ff',
  GOLD: '#c89b3c', SILVER: '#9ca3af', BRONZE: '#cd7f32', IRON: '#6b7280',
}

const QUEUE_NAMES = {
  420: 'Ranked Solo', 440: 'Ranked Flex', 400: 'Normal', 450: 'ARAM',
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (h > 24) return `il y a ${Math.floor(h / 24)}j`
  if (h > 0)  return `il y a ${h}h`
  return `il y a ${m}m`
}

function getChampionIcon(championName) {
  return `https://ddragon.leagueoflegends.com/cdn/14.10.1/img/champion/${championName}.png`
}

function groupByChampion(matches) {
  const map = {}
  matches.forEach(m => {
    if (!map[m.champion]) map[m.champion] = { games: 0, wins: 0, kills: 0, deaths: 0, assists: 0 }
    map[m.champion].games++
    if (m.win) map[m.champion].wins++
    map[m.champion].kills   += m.kills
    map[m.champion].deaths  += m.deaths
    map[m.champion].assists += m.assists
  })
  return Object.entries(map)
    .map(([name, s]) => ({
      name,
      games:   s.games,
      winrate: Math.round((s.wins / s.games) * 100),
      kda:     s.deaths === 0 ? 'Perfect' : ((s.kills + s.assists) / s.deaths).toFixed(1),
    }))
    .sort((a, b) => b.games - a.games)
    .slice(0, 5)
}

export default function Player() {
  const { region, name, tag } = useParams()
  const navigate = useNavigate()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    const fetchPlayer = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await api.get(`/players/${region}/${name}/${tag}`)
        setData(res.data)
      } catch (e) {
        setError(e.response?.data?.detail || 'Joueur introuvable')
      } finally {
        setLoading(false)
      }
    }
    fetchPlayer()
  }, [region, name, tag])

  if (loading) return (
    <div className="player-page">
      <div className="player-loading">
        <div className="player-spinner" />
        <div className="player-loading-text">Recherche de {decodeURIComponent(name)}#{tag}...</div>
      </div>
    </div>
  )

  if (error) return (
    <div className="player-page">
      <div className="player-error">
        <div className="player-error-title">Joueur introuvable</div>
        <div className="player-error-sub">{error}</div>
        <button className="player-error-btn" onClick={() => navigate('/')}>Retour à l'accueil</button>
      </div>
    </div>
  )

  const { player, live_game, match_history, jinxit_profile, pro_player } = data
  const tierColor   = TIER_COLORS[player.tier] || '#9ca3af'
  const accentColor = pro_player?.accent_color || '#00e5ff'
  const champStats  = groupByChampion(match_history || [])

  // Données live pour affichage dans la card (kills, champion joué...)
  const liveParticipant = live_game?.participants?.find(
    p => p.puuid === player.riot_puuid || p.summonerName === player.summoner_name
  )
  const blueKills = live_game?.participants?.filter(p => p.teamId === 100).reduce((a, p) => a + (p.kills || 0), 0) || 0
  const redKills  = live_game?.participants?.filter(p => p.teamId === 200).reduce((a, p) => a + (p.kills || 0), 0) || 0

  return (
    <div className="player-page">

      {/* ─── BANNER ─── */}
      <div className="player-banner">
        <div className="player-banner-bg" style={pro_player
          ? { background: `linear-gradient(135deg, ${accentColor}20, #1a1919 60%)` }
          : { background: 'linear-gradient(135deg, #00e5ff08, #1a1919 60%)' }
        } />
        {pro_player?.team_logo_url && (
          <img
            className="player-banner-team-logo"
            src={pro_player.team_logo_url}
            alt={pro_player.team}
            referrerPolicy="no-referrer"
          />
        )}
        <div className="player-banner-overlay" />
      </div>

      {/* ─── PRO CARD FIFA flottante ─── */}
      <div className="pro-float-card">
        <div className="pro-photo-card" style={!pro_player?.photo_url ? { display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#242424' } : {}}>
          {pro_player?.photo_url ? (
            <img src={pro_player.photo_url} alt={pro_player.name} referrerPolicy="no-referrer"
              style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
          ) : player.profile_icon_url ? (
            <img src={player.profile_icon_url} alt={player.summoner_name}
              style={{ width: '90px', height: '90px', borderRadius: '12px', objectFit: 'cover' }}
              referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          ) : (
            <div className="pro-photo-initials">{player.summoner_name?.slice(0, 2).toUpperCase()}</div>
          )}
          <div className="pro-photo-accent" style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}88)` }} />
        </div>

        <div className="pro-card-info">
          <div className="pro-card-name">
            {player.summoner_name}
            <span className="pro-card-tag">#{player.tag_line}</span>
            {pro_player && (
              <span className="pro-card-badge"
                style={{ background: accentColor + '15', color: accentColor, border: `1px solid ${accentColor}30` }}>
                {pro_player.name} · {pro_player.team}
              </span>
            )}
          </div>
          <div className="pro-card-badges">
            {player.tier && (
              <span className="meta-badge" style={{ color: tierColor, background: tierColor + '15', borderColor: tierColor + '30' }}>
                {player.tier} {player.rank} · {player.lp} LP
              </span>
            )}
            <span className="meta-badge" style={{ color: '#9ca3af', background: '#ffffff08', borderColor: '#ffffff12' }}>
              {player.region}
            </span>
            {pro_player?.role && (
              <span className="meta-badge" style={{ color: '#6b7280', background: '#ffffff06', borderColor: '#ffffff08' }}>
                {pro_player.role}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ─── MAIN LAYOUT ─── */}
      <div className="player-layout">
        <div className="left-col">

          {/* LIVE GAME */}
          {live_game ? (
            <div className="live-card">
              <div className="live-header">
                <div className="live-title">
                  <span className="live-dot" />
                  Partie en cours · {QUEUE_NAMES[live_game.gameQueueConfigId] || 'Ranked'} · {formatDuration(live_game.gameLength || 0)}
                </div>
                {/* ✅ Navigation via live_game.id (ID PostgreSQL) */}
                <button
                  className="live-btn"
                  style={{ background: `linear-gradient(135deg, ${accentColor}, ${accentColor}bb)` }}
                  onClick={() => navigate(`/game/${live_game.id}`)}
                >
                  Voir & Parier →
                </button>
              </div>
              <div className="live-body">
                <div className="live-score-block">
                  <div className="live-side">Blue side</div>
                  <div className="live-score" style={{ color: '#378add' }}>{blueKills}</div>
                </div>
                <div className="live-vs">vs</div>
                <div className="live-score-block" style={{ textAlign: 'right' }}>
                  <div className="live-side">Red side</div>
                  <div className="live-score" style={{ color: '#ef4444' }}>{redKills}</div>
                </div>
                <div className="live-divider" />
                <div className="live-player-stats">
                  {liveParticipant ? (
                    <>
                      <strong style={{ color: '#e8eaf0' }}>{liveParticipant.championName}</strong><br />
                      {liveParticipant.kills}/{liveParticipant.deaths}/{liveParticipant.assists} · {liveParticipant.totalMinionsKilled} CS
                    </>
                  ) : (
                    <span style={{ color: '#4b5563' }}>Données live...</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="no-game">
              <div className="no-game-icon">⚔️</div>
              <div>
                <div className="no-game-text">{player.summoner_name} n'est pas en game</div>
                <div className="no-game-sub">Dernière mise à jour il y a quelques instants</div>
              </div>
            </div>
          )}

          {/* CHAMPION STATS */}
          {champStats.length > 0 && (
            <div>
              <div className="section-label">Champions joués (10 dernières)</div>
              <div className="champ-grid">
                {champStats.map((c, i) => (
                  <div className="champ-card" key={i}>
                    <div className="champ-img">
                      <img src={getChampionIcon(c.name)} alt={c.name} referrerPolicy="no-referrer"
                        onError={e => { e.target.style.display = 'none' }} />
                    </div>
                    <div className="champ-name">{c.name}</div>
                    <div className="champ-kda">{c.kda} KDA</div>
                    <div className="champ-wr" style={{ color: c.winrate >= 60 ? '#22c55e' : c.winrate >= 50 ? '#c89b3c' : '#ef4444' }}>
                      {c.winrate}% · {c.games}G
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* MATCH HISTORY */}
          {match_history?.length > 0 && (
            <div>
              <div className="section-label">10 dernières parties</div>
              <div className="match-list">
                {match_history.map((m, i) => (
                  <div className="match-row" key={i}>
                    <div className="match-result-bar" style={{ background: m.win ? '#22c55e' : '#ef4444' }} />
                    <div className="match-champ">
                      <img src={getChampionIcon(m.champion)} alt={m.champion}
                        onError={e => { e.target.style.display = 'none' }} />
                    </div>
                    <div className="match-info">
                      <div className="match-name">{m.champion} · {m.role || 'MID'}</div>
                      <div className="match-meta">{m.win ? '✓ Victoire' : '✗ Défaite'} · {timeAgo(m.played_at)}</div>
                    </div>
                    <div className="match-right">
                      <div className="match-kda">{m.kills}/{m.deaths}/{m.assists}</div>
                      <div className="match-cs">{m.cs} CS · {formatDuration(m.duration)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ─── SIDEBAR ─── */}
        <div className="sidebar">
          {jinxit_profile ? (
            <div className="sidebar-card">
              <div className="sidebar-section-label">Profil Jinxit</div>
              <div className="jinxit-avatar" style={{ background: 'linear-gradient(135deg, #00e5ff20, #d946a820)', border: '2px solid #00e5ff30' }}>
                {jinxit_profile.avatar_url
                  ? <img src={jinxit_profile.avatar_url} alt="avatar" />
                  : jinxit_profile.username?.slice(0, 2).toUpperCase()}
              </div>
              <div className="jinxit-username">{jinxit_profile.username}</div>
              {jinxit_profile.equipped_title && (
                <div className="jinxit-title-badge">✦ {jinxit_profile.equipped_title}</div>
              )}
              <div className="jinxit-coins"><span className="coin-dot" />{jinxit_profile.coins?.toLocaleString()} coins</div>
              <div className="jinxit-stats-grid">
                <div className="jstat"><div className="jstat-val" style={{ color: '#22c55e' }}>—%</div><div className="jstat-lbl">Win rate</div></div>
                <div className="jstat"><div className="jstat-val" style={{ color: '#00e5ff' }}>—</div><div className="jstat-lbl">Paris gagnés</div></div>
                <div className="jstat"><div className="jstat-val" style={{ color: '#d946a8' }}>—</div><div className="jstat-lbl">Win streak</div></div>
                <div className="jstat"><div className="jstat-val" style={{ color: '#c89b3c' }}>—</div><div className="jstat-lbl">Cartes</div></div>
              </div>
            </div>
          ) : (
            <div className="sidebar-card">
              <div className="sidebar-section-label">Profil Jinxit</div>
              <div className="no-jinxit-text">Ce joueur n'a pas encore lié de compte Jinxit.</div>
              <button className="no-jinxit-btn" onClick={() => navigate('/register')}>Créer un compte →</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}