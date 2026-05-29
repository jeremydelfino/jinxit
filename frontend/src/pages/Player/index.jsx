import './Player.css'
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

import { CHAMP_VERSION, APEX_TIERS } from './constants'

import PlayerHero       from './components/PlayerHero'
import RankCard         from './components/RankCard'
import StatsOverview    from './components/StatsOverview'
import LiveGameCard     from './components/LiveGameCard'
import MatchRow         from './components/MatchRow'
import JungleGapSidebar from './components/JungleGapSidebar'
import TeamRoster       from './components/TeamRoster'

export default function Player() {
  const { region, name, tag } = useParams()
  const navigate              = useNavigate()
  const { user }              = useAuthStore()

  const [data,        setData]        = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [refreshing,  setRefreshing]  = useState(false)
  const [isFav,       setIsFav]       = useState(false)
  const [favLoading,  setFavLoading]  = useState(false)
  const [champMap,    setChampMap]    = useState({})

  /* ─── DDragon mapping championId → name (pour live game) ─── */
  useEffect(() => {
    fetch(`https://ddragon.leagueoflegends.com/cdn/${CHAMP_VERSION}/data/en_US/champion.json`)
      .then(r => r.json())
      .then(d => {
        const m = {}
        Object.values(d.data).forEach(c => { m[String(parseInt(c.key))] = c.id })
        setChampMap(m)
      })
      .catch(() => {})
  }, [])

  /* ─── Fetch player data ─── */
  const loadPlayer = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError(null)
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
    } finally {
      setLoading(false)
    }
  }, [region, name, tag, user])

  useEffect(() => { loadPlayer() }, [loadPlayer])

  /* ─── Refresh forcé ─── */
  const handleRefresh = useCallback(async () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      await api.post(`/players/${region}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/refresh`)
      await loadPlayer(false)
    } catch (e) {
      console.error('Refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }, [region, name, tag, refreshing, loadPlayer])

  /* ─── Favoris ─── */
  const handleFavToggle = useCallback(async () => {
    if (!user || !data?.player?.id || favLoading) return
    setFavLoading(true)
    try {
      if (isFav) { await api.delete(`/favorites/${data.player.id}`); setIsFav(false) }
      else        { await api.post(`/favorites/${data.player.id}`);  setIsFav(true)  }
    } catch {}
    finally { setFavLoading(false) }
  }, [user, data?.player?.id, isFav, favLoading])

  /* ─── LOADING / ERROR ─── */
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

  /* ─── DATA ─── */
  const {
    player, live_game, match_history, overall_stats,
    junglegap_profile, pro_player,
  } = data

  const accentColor = pro_player?.accent_color || '#65BD62'

  return (
    <div className="player-page">

      {/* ═══ HERO ═══ */}
      <PlayerHero
        player={player}
        pro_player={pro_player}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        isFav={isFav}
        onFavToggle={handleFavToggle}
        favLoading={favLoading}
        canFav={!!user}
        junglegap_profile={junglegap_profile}
        onProfileChange={() => loadPlayer(false)}
      />

      {/* ═══ MAIN ═══ */}
      <div className="player-main">

        {pro_player?.team && (
          <TeamRoster
            teamCode={pro_player.team_code}
            teamName={pro_player.team}
            teamLogo={pro_player.team_logo_url}
            accentColor={accentColor}
            currentPlayerPuuid={player.riot_puuid}
            delay={0.05}
          />
        )}

        {/* ── Row 0 : Jungle Gap ── */}
        <div className="player-row player-row-jg">
          <JungleGapSidebar
            junglegap_profile={junglegap_profile}
            delay={0.05}
          />
        </div>

        {/* ── Row 1 : Rank + Stats Overview ── */}
        <div className="player-row player-row-rank">
          <RankCard
            tier={player.tier}
            rank={player.rank}
            lp={player.lp}
            queueLabel="Solo / Duo"
            delay={0.1}
          />
          <StatsOverview
            overall_stats={overall_stats}
            match_history={match_history}
            delay={0.15}
          />
        </div>

        {/* ── Row 2 : Live Game ── */}
        <div className="player-row">
          <div className="player-section-title">
            <span className="player-section-dot" style={{ background: live_game ? '#ef4444' : '#374151' }} />
            {live_game ? 'En partie' : 'Pas en partie'}
          </div>
          <LiveGameCard
            live_game={live_game}
            player={player}
            accentColor={accentColor}
            champMap={champMap}
            delay={0.2}
          />
        </div>

        {/* ── Row 3 : Match History ── */}
        {match_history?.length > 0 && (
          <div className="player-row">
            <div className="player-section-title">
              Historique des parties
              <span className="player-section-sub">{match_history.length} dernières parties</span>
            </div>
            <div className="player-match-list">
              {match_history.map((m, i) => (
                <MatchRow
                  key={m.match_id || i}
                  match={m}
                  playerPuuid={player.riot_puuid}
                  delay={0.25 + i * 0.04}
                />
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}