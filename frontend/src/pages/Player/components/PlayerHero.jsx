import './PlayerHero.css'
import { useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../../api/client'
import { getRankLabel } from '../utils'
import { TIER_COLORS, REGION_LABELS } from '../constants'
import BannerStickers from '../../Profile/components/BannerStickers/index.jsx'

export default function PlayerHero({
  player, pro_player,
  onRefresh, refreshing,
  isFav, onFavToggle, favLoading, canFav,
  junglegap_profile,
  onProfileChange,   // callback pour refetch quand on change la team favorite
}) {
  const navigate    = useNavigate()
  const bannerRef   = useRef(null)
  const tierColor   = TIER_COLORS[player.tier] || '#9ca3af'
  const accentColor = pro_player?.accent_color || '#65BD62'

  const isOwner = junglegap_profile?.is_owner
  const favTeam = junglegap_profile?.favorite_team

  /* ─── Team picker ─── */
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const [esportsTeams,   setEsportsTeams]   = useState([])

  useEffect(() => {
    if (!isOwner) return
    api.get('/esports/teams').then(r => setEsportsTeams(r.data)).catch(() => {})
  }, [isOwner])

  const handlePickTeam = async (team) => {
    try {
      await api.post('/profile/set-team', {
        name: team.name, logo: team.logo_url || '', color: team.accent_color || '',
      })
      onProfileChange?.()
    } catch (err) {
      console.error('set-team:', err.response?.data || err)
    }
    setShowTeamPicker(false)
  }

  const handleRemoveTeam = async () => {
    try {
      await api.post('/profile/set-team', { name: '', logo: '', color: '' })
      onProfileChange?.()
    } catch (err) { console.error(err) }
  }

  return (
    <div className="ph-wrap">
      {/* ─── BANNER (grand fond avec logo team du pro player) ─── */}
      <div className="ph-banner" ref={bannerRef}>
        <div
          className="ph-banner-bg"
          style={pro_player
            ? { background: `linear-gradient(135deg, ${accentColor}30 0%, #171717 80%)` }
            : { background: `linear-gradient(135deg, ${tierColor}28 0%, ${tierColor}10 30%, #171717 80%)` }
          }
        />
        {pro_player?.team_logo_url && (
          <img
            className="ph-banner-team-logo"
            src={pro_player.team_logo_url}
            alt={pro_player.team}
            referrerPolicy="no-referrer"
          />
        )}

        {/* ─── HERO ─── */}
        <div className="ph-hero">
          <div className="ph-hero-left">
            {/* Photo */}
            <div className="ph-photo">
              {pro_player?.photo_url ? (
                <img src={pro_player.photo_url} alt={pro_player.name} referrerPolicy="no-referrer" />
              ) : player.profile_icon_url ? (
                <img src={player.profile_icon_url} alt="icon" referrerPolicy="no-referrer" />
              ) : (
                <div className="ph-photo-initials">{player.summoner_name.slice(0, 2).toUpperCase()}</div>
              )}
              <div className="ph-photo-accent" style={{ background: pro_player ? accentColor : tierColor }} />
            </div>

            {/* Info */}
            <div className="ph-info">
              <div className="ph-name-row">
                <h1 className="ph-name">
                  {pro_player ? pro_player.name : player.summoner_name}
                  <span className="ph-tag">#{player.tag_line}</span>
                </h1>

                {pro_player && (
                  <span
                    className="ph-badge"
                    style={{
                      background: `${accentColor}20`,
                      color: accentColor,
                      borderColor: `${accentColor}55`,
                      boxShadow: `0 0 16px ${accentColor}30`,
                    }}
                  >
                    ⚡ PRO {pro_player.team && `· ${pro_player.team}`}
                  </span>
                )}
              </div>

              <div className="ph-meta">
                <span className="ph-meta-pill">{REGION_LABELS[player.region] || player.region}</span>
                {player.tier && (
                  <span className="ph-meta-pill ph-rank-pill" style={{ color: tierColor, borderColor: `${tierColor}55`, background: `${tierColor}10` }}>
                    {getRankLabel(player.tier, player.rank, player.lp)}
                  </span>
                )}

                {/* ─── Pilule team favorite (même style que Profile) ─── */}
                {favTeam ? (
                  <button
                    className="profile-hero-team"
                    style={{ '--tc': favTeam.color || '#65BD62' }}
                    onClick={() => isOwner && setShowTeamPicker(true)}
                  >
                    {favTeam.logo && <img src={favTeam.logo} alt="" referrerPolicy="no-referrer" />}
                    <span>Fan de <strong>{favTeam.name}</strong></span>
                  </button>
                ) : isOwner ? (
                  <button className="profile-hero-team profile-hero-team-empty" onClick={() => setShowTeamPicker(true)}>
                    ⚑ Choisir une équipe favorite
                  </button>
                ) : null}
              </div>

              <div className="ph-actions">
                <button
                  className={`ph-btn ph-btn-refresh${refreshing ? ' refreshing' : ''}`}
                  onClick={onRefresh}
                  disabled={refreshing}
                >
                  <span className="ph-btn-icon">↻</span>
                  {refreshing ? 'Actualisation…' : 'Actualiser'}
                </button>

                {canFav && (
                  <button
                    className={`ph-btn ph-btn-fav${isFav ? ' is-active' : ''}`}
                    onClick={onFavToggle}
                    disabled={favLoading}
                    title={isFav ? 'Retirer des favoris' : 'Ajouter aux favoris'}
                  >
                    <span className="ph-btn-icon">{isFav ? '❤' : '♡'}</span>
                    {isFav ? 'Favori' : 'Suivre'}
                  </button>
                )}

                <button className="ph-btn ph-btn-back" onClick={() => navigate('/')}>
                  ← Retour
                </button>

                {isOwner && favTeam && (
                  <button className="profile-hero-team-remove" onClick={handleRemoveTeam}>
                    ✕ Retirer l'équipe
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="ph-banner-overlay" />

        {/* ─── STICKERS ─── */}
        {junglegap_profile && (
          <BannerStickers
            userId={junglegap_profile.id}
            isOwnProfile={junglegap_profile.is_owner}
            bannerRef={bannerRef}
          />
        )}
      </div>

      {/* ─── TEAM PICKER MODAL ─── */}
      {showTeamPicker && (
        <div className="profile-picker-overlay" onClick={() => setShowTeamPicker(false)}>
          <div className="profile-picker-modal" onClick={e => e.stopPropagation()}>
            <div className="profile-picker-header">
              <div className="profile-picker-title">Choisis ton équipe favorite</div>
              <button className="profile-picker-close" onClick={() => setShowTeamPicker(false)}>✕</button>
            </div>
            <div className="profile-picker-section">
              <div className="profile-picker-teams">
                {esportsTeams.map(team => {
                  const selected = favTeam?.name === team.name
                  return (
                    <div
                      key={team.name}
                      className={`profile-picker-team ${selected ? 'selected' : ''}`}
                      style={{ '--tc': team.accent_color || '#65BD62' }}
                      onClick={() => handlePickTeam(team)}
                    >
                      {team.logo_url && <img className="profile-picker-logo" src={team.logo_url} alt={team.name} referrerPolicy="no-referrer" />}
                      <div className="profile-picker-team-name">{team.name}</div>
                      {selected && <div className="profile-picker-check">✓</div>}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}