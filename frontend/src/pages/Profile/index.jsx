import './Profile.css'
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import TcgCard from '../../components/ui/TcgCard'

// Exactement le même pattern que backend/scripts/set_team_logos.py
const BASE = 'https://lol.fandom.com/wiki/Special:FilePath/'

const TEAMS = [
  { id: 't1',       name: 'T1',                  logo: BASE + 'T1logo_profile.png',                    color: '#c89b3c', region: 'LCK' },
  { id: 'geng',     name: 'Gen.G',                logo: BASE + 'Gen.Glogo_profile.png',                 color: '#b8952a', region: 'LCK' },
  { id: 'hle',      name: 'Hanwha Life Esports',  logo: BASE + 'Hanwha_Life_Esportslogo_profile.png',   color: '#e03030', region: 'LCK' },
  { id: 'kt',       name: 'KT Rolster',            logo: BASE + 'KT_Rolsterlogo_profile.png',            color: '#e03030', region: 'LCK' },
  { id: 'drx',      name: 'DRX',                  logo: BASE + 'DRXlogo_profile.png',                   color: '#3a7bd5', region: 'LCK' },
  { id: 'dplus',    name: 'Dplus KIA',             logo: BASE + 'Dplus_KIAlogo_profile.png',             color: '#00b4d8', region: 'LCK' },
  { id: 'ns',       name: 'Nongshim RedForce',     logo: BASE + 'Nongshim_RedForcelogo_profile.png',     color: '#e04040', region: 'LCK' },
  { id: 'fearx',    name: 'FEARX',                logo: BASE + 'FEARXlogo_profile.png',                 color: '#9b59b6', region: 'LCK' },
  { id: 'g2',       name: 'G2 Esports',            logo: BASE + 'G2_Esportslogo_profile.png',            color: '#ff6b35', region: 'LEC' },
  { id: 'fnc',      name: 'Fnatic',               logo: BASE + 'Fnaticlogo_profile.png',                color: '#ff7d00', region: 'LEC' },
  { id: 'kc',       name: 'Karmine Corp',          logo: BASE + 'Karmine_Corplogo_profile.png',          color: '#0099ff', region: 'LEC' },
  { id: 'mkoi',     name: 'Movistar KOI',          logo: BASE + 'Movistar_KOIlogo_profile.png',          color: '#00c896', region: 'LEC' },
  { id: 'gx',       name: 'GIANTX',               logo: BASE + 'GIANTXlogo_profile.png',                color: '#e63946', region: 'LEC' },
  { id: 'vitality', name: 'Team Vitality',         logo: BASE + 'Team_Vitalitylogo_profile.png',         color: '#f5c518', region: 'LEC' },
  { id: 'sk',       name: 'SK Gaming',             logo: BASE + 'SK_Gaminglogo_profile.png',             color: '#22c55e', region: 'LEC' },
  { id: 'heretics', name: 'Team Heretics',         logo: BASE + 'Team_Hereticslogo_profile.png',         color: '#7c3aed', region: 'LEC' },
  { id: 'navi',     name: 'Natus Vincere',         logo: BASE + 'Natus_Vincerelogo_profile.png',         color: '#f5c518', region: 'LEC' },
]

const RARITY = {
  common:    { color: '#9ca3af', label: 'Commune'    },
  rare:      { color: '#3b82f6', label: 'Rare'       },
  epic:      { color: '#a855f7', label: 'Épique'     },
  legendary: { color: '#c89b3c', label: 'Légendaire' },
}

const MOCK_BADGES = [
  { id: 1, icon: '🏆', label: 'Premier pari',  unlocked: true  },
  { id: 2, icon: '🔥', label: 'Win Streak x5', unlocked: true  },
  { id: 3, icon: '💎', label: 'Carte Épique',  unlocked: true  },
  { id: 4, icon: '🌙', label: 'Noctambule',    unlocked: false },
  { id: 5, icon: '👑', label: 'Légendaire',    unlocked: false },
  { id: 6, icon: '🎯', label: 'Précis x10',   unlocked: false },
]

const TX_ICONS = {
  daily_reward:   { icon: '🌅' },
  bet_placed:     { icon: '🎯' },
  bet_won:        { icon: '🏆' },
  bet_lost:       { icon: '💸' },
  signup_bonus:   { icon: '🎁' },
  crate_purchase: { icon: '📦' },
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const d = Math.floor(diff / 86400000)
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (d > 0) return `il y a ${d}j`
  if (h > 0) return `il y a ${h}h`
  return `il y a ${m}m`
}

export default function Profile() {
  const navigate = useNavigate()
  const { user, token, login } = useAuthStore()
  const fileRef = useRef(null)

  const [profile,        setProfile]        = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [editMode,       setEditMode]       = useState(false)
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const [history,        setHistory]        = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [userCards,      setUserCards]      = useState([])

  useEffect(() => {
    if (!user || !token) { navigate('/login'); return }
    api.get('/profile/me')
      .then(r => setProfile(r.data))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))

    setHistoryLoading(true)
    api.get('/coins/history')
      .then(r => setHistory(r.data))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false))

    api.get('/cards/my-cards')
      .then(r => setUserCards(r.data))
      .catch(() => setUserCards([]))
  }, [])

  const handlePickTeam = async (team) => {
    try {
      await api.post('/profile/set-team', { name: team.name, logo: team.logo, color: team.color })
      setProfile(p => ({ ...p, favorite_team: { name: team.name, logo: team.logo, color: team.color } }))
    } catch (err) {
      console.error('set-team failed', err)
    }
    setShowTeamPicker(false)
  }

  const handleAvatarUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    const tkn = localStorage.getItem('token')
    try {
      const res = await api.post(`/upload/avatar?authorization=Bearer ${tkn}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const newUrl = res.data.avatar_url || res.data.url
      setProfile(p => ({ ...p, avatar_url: newUrl }))
      login({ ...user, avatar_url: newUrl }, token)
    } catch (err) {
      console.error('Upload failed', err.response?.data)
    }
  }

  const goToPlayerPage = () => {
    const rp = profile?.riot_player
    if (!rp) return
    navigate(`/player/${rp.region}/${encodeURIComponent(rp.summoner_name)}/${encodeURIComponent(rp.tag_line)}`)
  }

  if (loading) return (
    <div className="profile-page">
      <div className="player-loading">
        <div className="player-spinner" />
        <div className="player-loading-text">Chargement du profil...</div>
      </div>
    </div>
  )

  const displayName = profile?.username || user?.username || '—'
  const riotLinked  = profile?.riot_linked
  const riotPlayer  = profile?.riot_player
  const favTeam     = profile?.favorite_team
  const accentColor = favTeam?.color || '#00e5ff'
  const lolIconUrl  = riotPlayer?.profile_icon_url || null
  const avatarSrc   = profile?.avatar_url || lolIconUrl

  return (
    <div className="profile-page">

      {/* ─── BANNER — identique Player/index.jsx ─── */}
      <div className="player-banner">
        <div className="player-banner-bg" style={favTeam
          ? { background: `linear-gradient(135deg, ${accentColor}20, #1a1919 60%)` }
          : { background: 'linear-gradient(135deg, #00e5ff08, #1a1919 60%)' }
        } />
        {favTeam?.logo && (
          <img
            className="player-banner-team-logo"
            src={favTeam.logo}
            alt={favTeam.name}
            referrerPolicy="no-referrer"
          />
        )}
        <div className="player-banner-overlay" />
      </div>

      {/* ─── HEADER FLOTTANT — identique Player/index.jsx ─── */}
      <div className="pro-float-card">
        <div className="pro-photo-card" style={!avatarSrc ? { display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#242424' } : {}}>
          {avatarSrc
            ? <img src={avatarSrc} alt="avatar" referrerPolicy="no-referrer"
                style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center' }}
                onError={e => { e.target.style.display = 'none' }} />
            : <div className="pro-photo-initials">{displayName.slice(0, 2).toUpperCase()}</div>
          }
          <div className="pro-photo-accent" style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}88)` }} />
          {editMode && (
            <>
              <button className="avatar-upload-btn" onClick={() => fileRef.current?.click()}>✎</button>
              <input type="file" ref={fileRef} accept="image/*,image/webp" style={{ display: 'none' }} onChange={handleAvatarUpload} />
            </>
          )}
        </div>

        <div className="pro-card-info">
          <div className="pro-card-name">
            {displayName}
            {favTeam && (
              <span className="pro-card-badge" style={{ background: accentColor + '15', color: accentColor, border: `1px solid ${accentColor}30` }}>
                ⚑ {favTeam.name}
              </span>
            )}
            {riotLinked && (
              <span className="pro-card-badge" style={{ background: '#00e5ff15', color: '#00e5ff', border: '1px solid #00e5ff30' }}>
                ⚔ Riot lié
              </span>
            )}
          </div>
          <div className="pro-card-badges">
            <span className="meta-badge" style={{ color: '#c89b3c', background: '#c89b3c15', borderColor: '#c89b3c30' }}>
              🪙 {profile?.coins?.toLocaleString() ?? '—'} coins
            </span>
            {riotPlayer?.tier && (
              <span className="meta-badge" style={{ color: '#9ca3af', background: '#ffffff08', borderColor: '#ffffff12' }}>
                {riotPlayer.tier} {riotPlayer.rank}
              </span>
            )}
          </div>
          <div className="profile-actions-row">
            {editMode
              ? <button className="live-btn" style={{ padding: '7px 16px', fontSize: '12px' }} onClick={() => setEditMode(false)}>✓ Enregistrer</button>
              : <button className="btn-edit-profile" onClick={() => setEditMode(true)}>✎ Modifier le profil</button>
            }
            {editMode && (
              <button className="btn-edit-profile" style={{ borderColor: accentColor + '40', color: accentColor }}
                onClick={() => setShowTeamPicker(true)}>
                {favTeam ? '⚑ Changer d\'équipe' : '⚑ Équipe favorite'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ══ BENTO ══ */}
      <div className="bento-grid">

        {/* Coins */}
        <div className="bento-card bento-coins">
          <div className="sidebar-section-label">Solde</div>
          <div className="coins-main">
            <span className="coin-dot" />
            <span className="coins-val">{profile?.coins?.toLocaleString() ?? '—'}</span>
          </div>
          <div className="jinxit-stats-grid" style={{ marginTop: 14 }}>
            <div className="jstat"><div className="jstat-val" style={{ color: '#22c55e' }}>—</div><div className="jstat-lbl">Gagnés</div></div>
            <div className="jstat"><div className="jstat-val" style={{ color: '#ef4444' }}>—</div><div className="jstat-lbl">Perdus</div></div>
            <div className="jstat"><div className="jstat-val" style={{ color: '#00e5ff' }}>—%</div><div className="jstat-lbl">Win rate</div></div>
            <div className="jstat"><div className="jstat-val" style={{ color: '#d946a8' }}>—</div><div className="jstat-lbl">Streak</div></div>
          </div>
        </div>

        {/* Compte Riot */}
        <div className="bento-card bento-riot">
          <div className="sidebar-section-label">Compte Riot</div>
          {riotLinked && riotPlayer ? (
            <>
              <div className="riot-linked">
                {lolIconUrl && (
                  <img src={lolIconUrl} alt="lol icon" className="riot-lol-icon"
                    referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                )}
                <div>
                  <div className="riot-name">{riotPlayer.summoner_name}<span className="riot-tag">#{riotPlayer.tag_line}</span></div>
                  <div className="riot-sub">{riotPlayer.region} · {riotPlayer.tier || 'Non classé'}</div>
                </div>
              </div>
              <button className="btn-player-page" onClick={goToPlayerPage}>
                Voir ma page joueur →
              </button>
            </>
          ) : (
            <>
              <div className="no-jinxit-text" style={{ marginTop: 8 }}>
                Lie ton compte Riot pour afficher ton icône LoL et accéder à ta page joueur.
              </div>
              <button className="no-jinxit-btn" style={{ marginTop: 'auto' }}>
                Lier mon compte →
              </button>
            </>
          )}
        </div>

        {/* Historique */}
        <div className="bento-card bento-history">
          <div className="sidebar-section-label">Historique des coins</div>
          <div className="history-scroll">
            {historyLoading && <div className="history-empty">Chargement...</div>}
            {!historyLoading && history.length === 0 && <div className="history-empty">Aucune transaction.</div>}
            {!historyLoading && history.map((tx, i) => {
              const meta = TX_ICONS[tx.type] || { icon: '💰' }
              const isPos = tx.amount > 0
              return (
                <div key={i} className="history-row">
                  <span className="history-icon">{meta.icon}</span>
                  <div className="history-info">
                    <div className="history-desc">{tx.description || tx.type}</div>
                    <div className="history-time">{timeAgo(tx.created_at)}</div>
                  </div>
                  <span className="history-amount" style={{ color: isPos ? '#22c55e' : '#ef4444' }}>
                    {isPos ? '+' : ''}{tx.amount}
                    <span className="coin-dot" style={{ background: isPos ? '#22c55e' : '#ef4444', marginLeft: 5 }} />
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Badges */}
        <div className="bento-card bento-badges">
          <div className="sidebar-section-label">
            Badges <span style={{ color: '#c89b3c', marginLeft: 6 }}>{MOCK_BADGES.filter(b => b.unlocked).length}/{MOCK_BADGES.length}</span>
          </div>
          <div className="badges-grid">
            {MOCK_BADGES.map(b => (
              <div key={b.id} className={`badge-chip ${b.unlocked ? '' : 'locked'}`} title={b.label}>
                <span className="badge-icon-big">{b.icon}</span>
                <span className="badge-lbl">{b.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Cartes */}
        <div className="bento-card bento-cards">
          <div className="sidebar-section-label">
            Mes Cartes <span style={{ color: '#c89b3c', marginLeft: 6 }}>{userCards.length}</span>
          </div>
          {userCards.length === 0 ? (
            <div className="cards-empty-state">
              <div style={{ fontSize: 40 }}>🃏</div>
              <div style={{ fontSize: 13, color: '#6b7280', marginTop: 8 }}>Aucune carte pour le moment</div>
              <button className="no-jinxit-btn" style={{ marginTop: 12, maxWidth: 200 }} onClick={() => navigate('/caisses')}>
                Ouvrir des caisses →
              </button>
            </div>
          ) : (
            <>
              <div className="tcg-grid">
                {userCards.map(uc => (
                  <TcgCard key={uc.id} card={uc.card} size="md" />
                ))}
              </div>
              <button className="no-jinxit-btn" style={{ marginTop: 16 }} onClick={() => navigate('/caisses')}>
                Ouvrir des caisses →
              </button>
            </>
          )}
        </div>

      </div>

      {/* ══ POPUP TEAM PICKER ══ */}
      {showTeamPicker && (
        <div className="picker-overlay" onClick={() => setShowTeamPicker(false)}>
          <div className="picker-modal" onClick={e => e.stopPropagation()}>
            <div className="picker-header">
              <span className="picker-title">Équipe favorite</span>
              <button className="picker-close" onClick={() => setShowTeamPicker(false)}>✕</button>
            </div>
            {['LCK', 'LEC'].map(region => (
              <div key={region} className="picker-section">
                <div className="sidebar-section-label" style={{ padding: '0 20px', marginBottom: 10 }}>{region}</div>
                <div className="picker-teams-grid">
                  {TEAMS.filter(t => t.region === region).map(team => (
                    <button
                      key={team.id}
                      className={`picker-team ${favTeam?.name === team.name ? 'selected' : ''}`}
                      style={{ '--tc': team.color }}
                      onClick={() => handlePickTeam(team)}
                    >
                      <img
                        src={team.logo}
                        alt={team.name}
                        className="picker-logo"
                        referrerPolicy="no-referrer"
                        onError={e => { e.target.style.display = 'none' }}
                      />
                      <span className="picker-team-name">{team.name}</span>
                      {favTeam?.name === team.name && <span className="picker-check">✓</span>}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}