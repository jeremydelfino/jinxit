import './Player.css'
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

const TIER_COLORS = {
  CHALLENGER: '#f4c430', GRANDMASTER: '#ef4444', MASTER: '#a78bfa',
  DIAMOND: '#378add', EMERALD: '#65BD62', PLATINUM: '#00b4d8',
  GOLD: '#e2b147', SILVER: '#9ca3af', BRONZE: '#cd7f32', IRON: '#6b7280',
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
  const h    = Math.floor(diff / 3600000)
  const m    = Math.floor(diff / 60000)
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
      kda:     s.deaths === 0 ? '∞' : ((s.kills + s.assists) / s.deaths).toFixed(2),
    }))
    .sort((a, b) => b.games - a.games)
    .slice(0, 5)
}

export default function Player() {
  const { region, name, tag } = useParams()
  const navigate              = useNavigate()
  const { user }              = useAuthStore()

  const [data,       setData]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [isFav,      setIsFav]      = useState(false)
  const [favLoading, setFavLoading] = useState(false)

  useEffect(() => {
    const fetchPlayer = async () => {
      setLoading(true); setError(null)
      try {
        const res = await api.get(`/players/${region}/${name}/${tag}`)
        setData(res.data)
        if (user && res.data?.player?.id) {
          try {
            const favRes = await api.get(`/favorites/check/${res.data.player.id}`)
            setIsFav(favRes.data.is_favorite)
          } catch {}
        }
      } catch (e) {
        setError(e.response?.data?.detail || 'Joueur introuvable')
      } finally { setLoading(false) }
    }
    fetchPlayer()
  }, [region, name, tag])

  const handleFavToggle = useCallback(async () => {
    if (!user || !data?.player?.id || favLoading) return
    setFavLoading(true)
    try {
      if (isFav) { await api.delete(`/favorites/${data.player.id}`); setIsFav(false) }
      else        { await api.post(`/favorites/${data.player.id}`);  setIsFav(true)  }
    } catch {}
    finally { setFavLoading(false) }
  }, [user, data?.player?.id, isFav, favLoading])

  if (loading) return (
    <div className="player-page">
      <div className="player-loading">
        <div className="player-spinner" />
        <div className="player-loading-text">Recherche de {decodeURIComponent(name)}#{tag}…</div>
      </div>
    </div>
  )

  if (error) return (
    <div className="player-page">
      <div className="player-error">
        <div className="player-error-icon">⚔</div>
        <div className="player-error-title">Joueur introuvable</div>
        <div className="player-error-sub">{error}</div>
        <button className="player-error-btn" onClick={() => navigate('/')}>Retour à l'accueil</button>
      </div>
    </div>
  )

  const { player, live_game, match_history, junglegap_profile, pro_player } = data
  const tierColor   = TIER_COLORS[player.tier] || '#9ca3af'
  const accentColor = pro_player?.accent_color || '#65BD62'
  const champStats  = groupByChampion(match_history || [])
  const betStats    = junglegap_profile?.bet_stats

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
          ? { background: `linear-gradient(135deg, ${accentColor}22 0%, #171717 65%)` }
          : { background: 'linear-gradient(135deg, #65BD6210 0%, #171717 65%)' }
        } />
        {pro_player?.team_logo_url && (
          <img className="player-banner-team-logo" src={pro_player.team_logo_url} alt={pro_player.team} referrerPolicy="no-referrer" />
        )}
        <div className="player-banner-overlay" />
      </div>

      {/* ─── HERO FLOTTANT ─── */}
      <div className="pro-float-card">
        <div className="pro-photo-card" style={!pro_player?.photo_url ? { display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1f1f1f' } : {}}>
          {pro_player?.photo_url ? (
            <img src={pro_player.photo_url} alt={pro_player.name} referrerPolicy="no-referrer"
              style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
          ) : player.profile_icon_url ? (
            <img src={player.profile_icon_url} alt={player.summoner_name}
              style={{ width: '88px', height: '88px', borderRadius: '12px', objectFit: 'cover' }}
              referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
          ) : (
            <div className="pro-photo-initials">{player.summoner_name?.slice(0, 2).toUpperCase()}</div>
          )}
          <div className="pro-photo-accent" style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}55)` }} />
        </div>

        <div className="pro-card-info">
          <div className="pro-card-name">
            {player.summoner_name}
            <span className="pro-card-tag">#{player.tag_line}</span>
            {pro_player && (
              <span className="pro-card-badge" style={{ background: accentColor + '15', color: accentColor, border: `1px solid ${accentColor}30` }}>
                {pro_player.name} · {pro_player.team}
              </span>
            )}
            {user && (
              <button
                className={`fav-btn ${isFav ? 'fav-btn--active' : ''} ${favLoading ? 'fav-btn--loading' : ''}`}
                onClick={handleFavToggle}
                title={isFav ? 'Retirer des favoris' : 'Ajouter aux favoris'}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill={isFav ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
                <span className="fav-btn-label">{favLoading ? '…' : isFav ? 'Favori' : 'Suivre'}</span>
              </button>
            )}
          </div>

          <div className="pro-card-badges">
            {player.tier && (
              <span className="meta-badge" style={{ color: tierColor, background: tierColor + '12', borderColor: tierColor + '28' }}>
                {player.tier} {player.rank} · {player.lp} LP
              </span>
            )}
            <span className="meta-badge muted">{player.region}</span>
            {pro_player?.role && <span className="meta-badge muted">{pro_player.role}</span>}
          </div>
        </div>
      </div>

      {/* ─── LAYOUT PRINCIPAL ─── */}
      <div className="player-layout">

        {/* ── COL GAUCHE ── */}
        <div className="left-col">

          {/* Live game */}
          {live_game ? (
            <div className="live-card">
              <div className="live-card-line" style={{ background: `linear-gradient(90deg, ${accentColor}, #65BD62)` }} />
              <div className="live-header">
                <div className="live-title">
                  <span className="live-dot" />
                  {QUEUE_NAMES[live_game.gameQueueConfigId] || 'Ranked'} · {formatDuration(live_game.gameLength || 0)}
                </div>
                <button className="live-btn" onClick={() => navigate(`/game/${live_game.id}`)}>
                  Voir & Parier →
                  <span className="live-btn-shimmer" />
                </button>
              </div>
              <div className="live-body">
                <div className="live-score-block">
                  <div className="live-side-label">Blue</div>
                  <div className="live-score blue">{blueKills}</div>
                </div>
                <div className="live-vs">vs</div>
                <div className="live-score-block right">
                  <div className="live-side-label">Red</div>
                  <div className="live-score red">{redKills}</div>
                </div>
                {liveParticipant && (
                  <>
                    <div className="live-divider" />
                    <div className="live-player-stats">
                      <span className="live-champ-name">{liveParticipant.championName}</span>
                      <span className="live-kda">{liveParticipant.kills}/{liveParticipant.deaths}/{liveParticipant.assists}</span>
                      <span className="live-cs">{liveParticipant.totalMinionsKilled} CS</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="no-game">
              <div className="no-game-icon">⚔</div>
              <div>
                <div className="no-game-text">{player.summoner_name} n'est pas en game</div>
                <div className="no-game-sub">Actualisé à l'instant</div>
              </div>
            </div>
          )}

          {/* Champion stats */}
          {champStats.length > 0 && (
            <div className="section-block">
              <div className="section-label">Champions joués <span className="section-label-sub">10 dernières parties</span></div>
              <div className="champ-grid">
                {champStats.map((c, i) => (
                  <div className="champ-card" key={i}>
                    <div className="champ-img">
                      <img src={getChampionIcon(c.name)} alt={c.name} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                    </div>
                    <div className="champ-name">{c.name}</div>
                    <div className="champ-kda">{c.kda} KDA</div>
                    <div className="champ-wr" style={{ color: c.winrate >= 60 ? '#65BD62' : c.winrate >= 50 ? '#e2b147' : '#ef4444' }}>
                      {c.winrate}% <span className="champ-games">{c.games}G</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Match history */}
          {match_history?.length > 0 && (
            <div className="section-block">
              <div className="section-label">Historique <span className="section-label-sub">10 dernières parties</span></div>
              <div className="match-list">
                {match_history.map((m, i) => (
                  <div className={`match-row ${m.win ? 'win' : 'loss'}`} key={i}>
                    <div className="match-result-pill">{m.win ? 'V' : 'D'}</div>
                    <div className="match-champ">
                      <img src={getChampionIcon(m.champion)} alt={m.champion} onError={e => { e.target.style.display = 'none' }} />
                    </div>
                    <div className="match-info">
                      <div className="match-name">{m.champion}{m.role ? ` · ${m.role}` : ''}</div>
                      <div className="match-meta">{timeAgo(m.played_at)} · {formatDuration(m.duration)}</div>
                    </div>
                    <div className="match-right">
                      <div className="match-kda">{m.kills}<span className="match-kda-sep">/</span>{m.deaths}<span className="match-kda-sep">/</span>{m.assists}</div>
                      <div className="match-cs">{m.cs} CS</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── SIDEBAR ── */}
        <div className="sidebar">
          {junglegap_profile ? (
            <div className="sidebar-card">
              <div className="sidebar-section-label">Profil Jungle Gap</div>

              <div className="jg-profile-header">
                <div className="jg-avatar">
                  {junglegap_profile.avatar_url
                    ? <img src={junglegap_profile.avatar_url} alt="avatar" referrerPolicy="no-referrer" />
                    : <span>{junglegap_profile.username?.slice(0, 2).toUpperCase()}</span>
                  }
                </div>
                <div>
                  <div className="jg-username">{junglegap_profile.username}</div>
                  {junglegap_profile.equipped_title && (
                    <div className="jg-title">✦ {junglegap_profile.equipped_title}</div>
                  )}
                </div>
              </div>

              <div className="jg-coins">
                <span className="jg-coin-dot" />
                <span className="jg-coin-val">{junglegap_profile.coins?.toLocaleString()}</span>
                <span className="jg-coin-lbl">coins</span>
              </div>

              <div className="jg-stats-grid">
                <div className="jg-stat">
                  <div className="jg-stat-val green">
                    {betStats?.winrate !== null && betStats?.winrate !== undefined ? `${betStats.winrate}%` : '—'}
                  </div>
                  <div className="jg-stat-lbl">Win rate</div>
                </div>
                <div className="jg-stat">
                  <div className="jg-stat-val accent">{betStats?.won ?? '—'}</div>
                  <div className="jg-stat-lbl">Paris gagnés</div>
                </div>
                <div className="jg-stat">
                  <div className="jg-stat-val gold">{betStats?.streak > 0 ? `🔥 ${betStats.streak}` : betStats?.streak ?? '—'}</div>
                  <div className="jg-stat-lbl">Streak</div>
                </div>
                <div className="jg-stat">
                  <div className="jg-stat-val muted">{betStats?.total ?? '—'}</div>
                  <div className="jg-stat-lbl">Total paris</div>
                </div>
              </div>

              <button
                className="jg-profile-btn"
                onClick={() => navigate(`/profile/${junglegap_profile.id}`)}
              >
                Voir le profil →
                <span className="jg-profile-btn-shimmer" />
              </button>
            </div>
          ) : (
            <div className="sidebar-card">
              <div className="sidebar-section-label">Profil Jungle Gap</div>
              <div className="jg-no-profile">
                <div className="jg-no-profile-icon">🎯</div>
                <div className="jg-no-profile-text">Ce joueur n'a pas encore lié de compte Jungle Gap.</div>
                <button className="jg-register-btn" onClick={() => navigate('/register')}>
                  Créer un compte →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}