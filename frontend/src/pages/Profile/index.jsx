// frontend/src/pages/Profile/index.jsx
import './Profile.css'
import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import TcgCard from '../../components/ui/TcgCard'

const REGIONS = ['EUW','EUNE','NA','KR','BR','JP','TR','OCE']

const MOCK_BADGES = [
  { id: 1, icon: '🏆', label: 'Premier pari',  unlocked: true  },
  { id: 2, icon: '🔥', label: 'Win Streak x5', unlocked: true  },
  { id: 3, icon: '💎', label: 'Carte Épique',  unlocked: true  },
  { id: 4, icon: '🌙', label: 'Noctambule',    unlocked: false },
  { id: 5, icon: '👑', label: 'Légendaire',    unlocked: false },
  { id: 6, icon: '🎯', label: 'Précis x10',   unlocked: false },
]

const BET_TYPE_LABELS  = { who_wins: 'Victoire', first_blood: 'First Blood' }
const BET_VALUE_LABELS = { blue: 'Équipe Bleue', red: 'Équipe Rouge' }

function computeStats(bets) {
  const won    = bets.filter(b => b.status === 'won')
  const lost   = bets.filter(b => b.status === 'lost')
  const gained = won.reduce((s, b)  => s + (b.payout  || 0), 0)
  const spent  = lost.reduce((s, b) => s + (b.amount  || 0), 0)
  const resolved = won.length + lost.length
  const winrate  = resolved > 0 ? Math.round((won.length / resolved) * 100) : null
  let streak = 0
  for (const b of bets) {
    if (b.status === 'won') streak++
    else if (b.status === 'lost') break
  }
  return { gained, spent, winrate, streak, total: bets.length }
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const d = Math.floor(diff / 86400000)
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (d > 0) return `il y a ${d}j`
  if (h > 0) return `il y a ${h}h`
  if (m > 0) return `il y a ${m}m`
  return 'à l\'instant'
}

// ─── Mini-stepper ajout compte Riot ─────────────────────────
function AddRiotStepper({ onDone, onCancel }) {
  const [step,      setStep]      = useState(0)   // 0=form 1=verify
  const [region,    setRegion]    = useState('EUW')
  const [riotId,    setRiotId]    = useState('')
  const [pending,   setPending]   = useState(null) // { riot_account_id, icon_id, icon_url, ... }
  const [loading,   setLoading]   = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error,     setError]     = useState('')

  const handleInit = async () => {
    setError(''); setLoading(true)
    const parts = riotId.trim().split('#')
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      setError('Format attendu : GameName#TAG')
      setLoading(false)
      return
    }
    try {
      const { data } = await api.post('/profile/riot-accounts/init', {
        game_name: parts[0].trim(),
        tag_line:  parts[1].trim(),
        region,
      })
      setPending(data)
      setStep(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'Riot ID introuvable')
    } finally { setLoading(false) }
  }

  const handleVerify = async () => {
    setError(''); setVerifying(true)
    try {
      const { data } = await api.post('/profile/riot-accounts/verify', {
        riot_account_id: pending.riot_account_id,
      })
      onDone(data.riot_account)
    } catch (err) {
      setError(err.response?.data?.detail || 'Mauvaise icône, réessaie')
    } finally { setVerifying(false) }
  }

  return (
    <div className="add-riot-stepper">
      {step === 0 && (
        <>
          <div className="add-riot-regions">
            {REGIONS.map(r => (
              <button
                key={r}
                className={`add-riot-region-btn ${region === r ? 'active' : ''}`}
                onClick={() => { setRegion(r); setError('') }}
              >{r}</button>
            ))}
          </div>
          <div className="add-riot-input-row">
            <input
              className="add-riot-input"
              type="text"
              placeholder="GameName#TAG"
              value={riotId}
              onChange={e => { setRiotId(e.target.value); setError('') }}
            />
            <button
              className="profile-btn-primary"
              onClick={handleInit}
              disabled={loading || !riotId.trim()}
            >
              {loading ? <span className="profile-spinner-sm" /> : 'Suivant →'}
            </button>
          </div>
          {error && <div className="add-riot-error">{error}</div>}
          <button className="add-riot-cancel" onClick={onCancel}>Annuler</button>
        </>
      )}

      {step === 1 && pending && (
        <>
          <div className="add-riot-verify-row">
            <img
              className="add-riot-verify-icon"
              src={pending.icon_url}
              alt={`icône ${pending.icon_id}`}
            />
            <div className="add-riot-verify-info">
              <div className="add-riot-verify-name">
                {pending.game_name}<span className="profile-riot-tag">#{pending.tag_line}</span>
              </div>
              <div className="add-riot-verify-instruction">
                Équipe l'icône <strong>#{pending.icon_id}</strong> dans LoL puis clique Vérifier
              </div>
            </div>
          </div>
          {error && <div className="add-riot-error">{error}</div>}
          <div className="add-riot-verify-actions">
            <button className="add-riot-cancel" onClick={() => { setStep(0); setError('') }}>Retour</button>
            <button className="profile-btn-primary" onClick={handleVerify} disabled={verifying}>
              {verifying ? <span className="profile-spinner-sm" /> : '✓ Vérifier'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ─── Composant principal ─────────────────────────────────────
export default function Profile() {
  const navigate              = useNavigate()
  const { userId }            = useParams()
  const { user, token, login } = useAuthStore()
  const fileRef               = useRef(null)

  const isOwnProfile = !userId || (user && String(user.id) === String(userId))

  const [profile,        setProfile]        = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [editMode,       setEditMode]       = useState(false)
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const [bets,           setBets]           = useState([])
  const [betsLoading,    setBetsLoading]    = useState(false)
  const [userCards,      setUserCards]      = useState([])
  const [showAddRiot,    setShowAddRiot]    = useState(false)

  const loadProfile = () => {
    const endpoint = isOwnProfile ? '/profile/me' : `/profile/user/${userId}`
    api.get(endpoint)
      .then(r => setProfile(r.data))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!token) { navigate('/login'); return }
    loadProfile()
    if (isOwnProfile) {
      setBetsLoading(true)
      api.get('/bets/my-bets')
        .then(r => setBets(r.data))
        .catch(() => setBets([]))
        .finally(() => setBetsLoading(false))
      api.get('/cards/my-cards')
        .then(r => setUserCards(r.data))
        .catch(() => setUserCards([]))
    }
  }, [userId])


  const [esportsTeams, setEsportsTeams] = useState([])

  useEffect(() => {
    api.get('/esports/teams')
      .then(r => setEsportsTeams(r.data))
      .catch(() => {})
  }, [])

  const handlePickTeam = async (team) => {
    try {
      await api.post('/profile/set-team', { name: team.name, logo: team.logo, color: team.color })
      setProfile(p => ({ ...p, favorite_team: { name: team.name, logo: team.logo, color: team.color } }))
    } catch (err) { console.error(err) }
    setShowTeamPicker(false)
  }

  const handleAvatarUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const fd  = new FormData()
    fd.append('file', file)
    const tkn = localStorage.getItem('token')
    try {
      const res    = await api.post(`/upload/avatar?authorization=Bearer ${tkn}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const newUrl = res.data.avatar_url || res.data.url
      setProfile(p => ({ ...p, avatar_url: newUrl }))
      login({ ...user, avatar_url: newUrl }, token)
    } catch (err) { console.error(err) }
  }

  const handleDeleteRiot = async (accountId) => {
    try {
      await api.delete(`/profile/riot-accounts/${accountId}`)
      setProfile(p => ({
        ...p,
        riot_accounts: p.riot_accounts.filter(ra => ra.id !== accountId),
      }))
    } catch (err) { console.error(err) }
  }

  const handleSetPrimary = async (accountId) => {
    try {
      await api.post(`/profile/riot-accounts/${accountId}/set-primary`)
      setProfile(p => ({
        ...p,
        riot_accounts: p.riot_accounts.map(ra => ({ ...ra, is_primary: ra.id === accountId })),
      }))
    } catch (err) { console.error(err) }
  }

  const handleRiotAdded = (newAccount) => {
    setShowAddRiot(false)
    setProfile(p => ({ ...p, riot_accounts: [...(p.riot_accounts || []), newAccount], riot_linked: true }))
  }

  const goToPlayerPage = (ra) => {
    if (!ra) return
    navigate(`/player/${ra.region}/${encodeURIComponent(ra.summoner_name)}/${encodeURIComponent(ra.tag_line)}`)
  }

  if (loading) return (
    <div className="profile-page">
      <div className="profile-loading">
        <div className="profile-spinner" />
        <div className="profile-loading-text">Chargement du profil…</div>
      </div>
    </div>
  )

  if (!profile) return (
    <div className="profile-page">
      <div className="profile-loading">
        <div className="profile-loading-text">Profil introuvable.</div>
      </div>
    </div>
  )

  const displayName   = profile?.username || '—'
  const riotAccounts  = profile?.riot_accounts || []
  const primaryAcc    = riotAccounts.find(ra => ra.is_primary) || riotAccounts[0] || null
  const favTeam       = profile?.favorite_team
  const accentColor   = favTeam?.color || '#65BD62'
  const lolIconUrl    = primaryAcc?.profile_icon_url || null
  const avatarSrc     = profile?.avatar_url || lolIconUrl
  const stats         = computeStats(bets)
  const canAddMore    = isOwnProfile && riotAccounts.length < 3

  return (
    <div className="profile-page">

      {/* ─── BANNER ─── */}
      <div className="profile-banner">
        <div className="profile-banner-bg" style={favTeam
          ? { background: `linear-gradient(135deg, ${accentColor}22 0%, #171717 65%)` }
          : { background: 'linear-gradient(135deg, #65BD6210 0%, #171717 65%)' }
        } />
        {favTeam?.logo && (
          <img className="profile-banner-team-logo" src={favTeam.logo} alt={favTeam.name} referrerPolicy="no-referrer" />
        )}
        <div className="profile-banner-overlay" />
      </div>

      {/* ─── HERO ─── */}
      <div className="profile-hero">
        <div className="profile-avatar-wrap">
          <div className="profile-avatar">
            {avatarSrc
              ? <img src={avatarSrc} alt="avatar" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
              : <span className="profile-avatar-initials">{displayName.slice(0, 2).toUpperCase()}</span>
            }
            <div className="profile-avatar-accent" style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}66)` }} />
            {isOwnProfile && editMode && (
              <>
                <button className="profile-avatar-upload-btn" onClick={() => fileRef.current?.click()}>✎</button>
                <input type="file" ref={fileRef} accept="image/*,image/webp" style={{ display: 'none' }} onChange={handleAvatarUpload} />
              </>
            )}
          </div>
        </div>

        <div className="profile-hero-info">
          <div className="profile-hero-name">
            {displayName}
            {favTeam && (
              <span className="profile-chip" style={{ background: accentColor + '18', color: accentColor, borderColor: accentColor + '35' }}>
                ⚑ {favTeam.name}
              </span>
            )}
            {riotAccounts.length > 0 && (
              <span className="profile-chip" style={{ background: '#65BD6215', color: '#65BD62', borderColor: '#65BD6230' }}>
                ⚔ {riotAccounts.length} compte{riotAccounts.length > 1 ? 's' : ''} Riot
              </span>
            )}
          </div>

          <div className="profile-hero-meta">
            {isOwnProfile && (
              <span className="profile-meta-pill gold">🪙 {profile?.coins?.toLocaleString() ?? '—'} coins</span>
            )}
            {primaryAcc?.tier && (
              <span className="profile-meta-pill muted">{primaryAcc.tier} {primaryAcc.rank}</span>
            )}
            {stats.total > 0 && (
              <span className="profile-meta-pill muted">{stats.total} paris placés</span>
            )}
          </div>

          {isOwnProfile && (
            <div className="profile-hero-actions">
              {editMode ? (
                <>
                  <button className="profile-btn-primary" onClick={() => setEditMode(false)}>✓ Enregistrer</button>
                  <button className="profile-btn-secondary" style={{ borderColor: accentColor + '40', color: accentColor }} onClick={() => setShowTeamPicker(true)}>
                    {favTeam ? '⚑ Changer d\'équipe' : '⚑ Équipe favorite'}
                  </button>
                </>
              ) : (
                <button className="profile-btn-secondary" onClick={() => setEditMode(true)}>✎ Modifier le profil</button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── GRID ─── */}
      <div className="profile-grid">

        {/* ── COL GAUCHE ── */}
        <div className="profile-col-left">

          {/* Stats */}
          <div className="profile-card">
            <div className="profile-card-label">Statistiques</div>
            <div className="profile-stats-grid">
              <div className="profile-stat">
                <div className="profile-stat-val green">{isOwnProfile ? (stats.gained > 0 ? `+${stats.gained.toLocaleString()}` : '0') : '—'}</div>
                <div className="profile-stat-lbl">Coins gagnés</div>
              </div>
              <div className="profile-stat">
                <div className="profile-stat-val red">{isOwnProfile ? (stats.spent > 0 ? `-${stats.spent.toLocaleString()}` : '0') : '—'}</div>
                <div className="profile-stat-lbl">Coins perdus</div>
              </div>
              <div className="profile-stat">
                <div className="profile-stat-val accent">{isOwnProfile ? (stats.winrate !== null ? `${stats.winrate}%` : '—') : '—'}</div>
                <div className="profile-stat-lbl">Win rate</div>
              </div>
              <div className="profile-stat">
                <div className="profile-stat-val gold">{isOwnProfile ? (stats.streak > 0 ? `🔥 ${stats.streak}` : '0') : '—'}</div>
                <div className="profile-stat-lbl">Streak actuel</div>
              </div>
            </div>
          </div>

          {/* Comptes Riot */}
          <div className="profile-card">
            <div className="profile-card-label">
              Comptes Riot
              <span className="profile-card-label-count">{riotAccounts.length}/3</span>
            </div>

            {riotAccounts.length === 0 && (
              <div className="profile-empty-state">
                <div className="profile-empty-text">Aucun compte Riot lié.</div>
              </div>
            )}

            {riotAccounts.length > 0 && (
              <div className="riot-accounts-list">
                {riotAccounts.map(ra => (
                  <div key={ra.id} className={`riot-account-row ${ra.is_primary ? 'primary' : ''}`}>
                    <div className="riot-account-left">
                      {ra.profile_icon_url
                        ? <img src={ra.profile_icon_url} alt="icon" className="profile-riot-icon" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                        : <div className="riot-account-icon-placeholder">?</div>
                      }
                      <div>
                        <div className="profile-riot-name">
                          {ra.summoner_name}
                          <span className="profile-riot-tag">#{ra.tag_line}</span>
                          {ra.is_primary && <span className="riot-primary-badge">Principal</span>}
                        </div>
                        <div className="profile-riot-sub">{ra.region}{ra.tier ? ` · ${ra.tier} ${ra.rank}` : ' · Non classé'}</div>
                      </div>
                    </div>
                    <div className="riot-account-actions">
                      <button
                        className="riot-account-btn"
                        title="Voir la page joueur"
                        onClick={() => goToPlayerPage(ra)}
                      >→</button>
                      {isOwnProfile && !ra.is_primary && (
                        <button
                          className="riot-account-btn"
                          title="Définir comme principal"
                          onClick={() => handleSetPrimary(ra.id)}
                        >★</button>
                      )}
                      {isOwnProfile && (
                        <button
                          className="riot-account-btn danger"
                          title="Supprimer ce compte"
                          onClick={() => handleDeleteRiot(ra.id)}
                        >✕</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Formulaire ajout */}
            {isOwnProfile && showAddRiot && (
              <AddRiotStepper
                onDone={handleRiotAdded}
                onCancel={() => setShowAddRiot(false)}
              />
            )}

            {canAddMore && !showAddRiot && (
              <button className="profile-btn-secondary" style={{ marginTop: 12, width: '100%' }} onClick={() => setShowAddRiot(true)}>
                + Ajouter un compte Riot
              </button>
            )}
          </div>

          {/* Badges */}
          <div className="profile-card">
            <div className="profile-card-label">
              Badges <span className="profile-card-label-count">{MOCK_BADGES.filter(b => b.unlocked).length}/{MOCK_BADGES.length}</span>
            </div>
            <div className="profile-badges-grid">
              {MOCK_BADGES.map(b => (
                <div key={b.id} className={`profile-badge ${b.unlocked ? 'unlocked' : 'locked'}`} title={b.label}>
                  <span className="profile-badge-icon">{b.icon}</span>
                  <span className="profile-badge-lbl">{b.label}</span>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* ── COL DROITE ── */}
        <div className="profile-col-right">

          {/* Historique bets */}
          <div className="profile-card profile-card-bets">
            <div className="profile-card-label">
              Historique des paris
              {bets.length > 0 && <span className="profile-card-label-count">{bets.length}</span>}
            </div>
            <div className="profile-bets-scroll">
              {betsLoading && <div className="profile-bets-empty">Chargement…</div>}
              {!betsLoading && !isOwnProfile && <div className="profile-bets-empty">Historique privé.</div>}
              {!betsLoading && isOwnProfile && bets.length === 0 && <div className="profile-bets-empty">Aucun pari pour le moment.</div>}
              {!betsLoading && isOwnProfile && bets.map((bet) => {
                const isWon     = bet.status === 'won'
                const isLost    = bet.status === 'lost'
                const isPending = bet.status === 'pending'
                const champion  = bet.game?.bet_player?.champion_name
                const champIcon = bet.game?.bet_player?.champion_icon
                const proName   = bet.game?.pro?.name
                const teamName  = bet.game?.pro?.team
                const betLabel  = BET_TYPE_LABELS[bet.bet_type]  || bet.bet_type
                const sideLabel = BET_VALUE_LABELS[bet.bet_value] || bet.bet_value
                return (
                  <div key={bet.id} className={`profile-bet-row ${bet.status}`}>
                    <div className="profile-bet-champ">
                      {champIcon
                        ? <img src={champIcon} alt={champion} onError={e => { e.target.style.display = 'none' }} />
                        : <span className="profile-bet-champ-fallback">🎯</span>
                      }
                    </div>
                    <div className="profile-bet-info">
                      <div className="profile-bet-main">
                        <span className="profile-bet-type">{betLabel}</span>
                        <span className="profile-bet-sep">·</span>
                        <span className="profile-bet-side">{sideLabel}</span>
                        {champion && <span className="profile-bet-champ-name">{champion}</span>}
                      </div>
                      <div className="profile-bet-sub">
                        {proName  && <span>{proName}</span>}
                        {teamName && <span className="profile-bet-team">{teamName}</span>}
                        <span className="profile-bet-time">{timeAgo(bet.created_at)}</span>
                      </div>
                    </div>
                    <div className="profile-bet-result">
                      <div className={`profile-bet-amount ${isWon ? 'green' : isLost ? 'red' : 'muted'}`}>
                        {isWon     && `+${(bet.payout || 0).toLocaleString()}`}
                        {isLost    && `-${bet.amount.toLocaleString()}`}
                        {isPending && `${bet.amount.toLocaleString()}`}
                      </div>
                      <div className={`profile-bet-status-badge ${bet.status}`}>
                        {isWon  && '✓ Gagné'}
                        {isLost && '✗ Perdu'}
                        {isPending && '⏳ En cours'}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Cartes TCG */}
          {isOwnProfile && (
            <div className="profile-card">
              <div className="profile-card-label">
                Mes Cartes <span className="profile-card-label-count">{userCards.length}</span>
              </div>
              {userCards.length === 0 ? (
                <div className="profile-empty-state">
                  <div style={{ fontSize: 36 }}>🃏</div>
                  <div className="profile-empty-text" style={{ marginTop: 8 }}>Aucune carte pour le moment.</div>
                  <button className="profile-btn-secondary" style={{ marginTop: 12 }} onClick={() => navigate('/caisses')}>Ouvrir des caisses →</button>
                </div>
              ) : (
                <>
                  <div className="profile-tcg-grid">
                    {userCards.map(uc => <TcgCard key={uc.id} card={uc.card} size="md" />)}
                  </div>
                  <button className="profile-btn-secondary" style={{ marginTop: 16, width: '100%' }} onClick={() => navigate('/caisses')}>Ouvrir des caisses →</button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── TEAM PICKER ─── */}
      {showTeamPicker && (
        <div className="profile-picker-overlay" onClick={() => setShowTeamPicker(false)}>
          <div className="profile-picker-modal" onClick={e => e.stopPropagation()}>
            <div className="profile-picker-header">
              <span className="profile-picker-title">Équipe favorite</span>
              <button className="profile-picker-close" onClick={() => setShowTeamPicker(false)}>✕</button>
            </div>
            {['LCK', 'LEC'].map(region => (
              <div key={region} className="profile-picker-section">
                <div className="profile-card-label" style={{ padding: '0 20px', marginBottom: 10 }}>{region}</div>
                <div className="profile-picker-teams">
                  {esportsTeams
                    .filter(t => t.region === region)
                    .map(team => (
                      <button
                        key={team.code}
                        className={`profile-picker-team ${favTeam?.name === team.name ? 'selected' : ''}`}
                        style={{ '--tc': team.accent_color }}
                        onClick={() => handlePickTeam({
                          name:  team.name,
                          logo:  team.logo_url,   // ← logo HD depuis lolesports
                          color: team.accent_color,
                        })}
                      >
                        <img
                          src={team.logo_url}
                          alt={team.name}
                          className="profile-picker-logo"
                          referrerPolicy="no-referrer"
                          onError={e => { e.target.style.display = 'none' }}
                        />
                        <span className="profile-picker-team-name">{team.code}</span>
                        {favTeam?.name === team.name && <span className="profile-picker-check">✓</span>}
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