// frontend/src/pages/Profile/index.jsx
import './Profile.css'
import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import TcgCard from '../../components/ui/TcgCard'
import TcgCardModal from '../../components/ui/TcgCardModal'
import { TIER_COLORS, APEX_TIERS } from '../Player/constants'
import { getTierImage } from '../Player/utils'
import BannerStickers from './components/BannerStickers'

const REGIONS = ['EUW','EUNE','NA','KR','BR','JP','TR','OCE']
const BET_TYPE_LABELS  = { who_wins: 'Victoire', first_blood: 'First Blood' }
const BET_VALUE_LABELS = { blue: 'Équipe Bleue', red: 'Équipe Rouge' }
const RARITY_RANK = { legendary: 0, epic: 1, rare: 2, common: 3 }

function computeStats(bets) {
  const won    = bets.filter(b => b.status === 'won')
  const lost   = bets.filter(b => b.status === 'lost')
  const gained = won.reduce((s, b) => s + (b.payout || 0), 0)
  const spent  = lost.reduce((s, b) => s + (b.amount || 0), 0)
  const resolved = won.length + lost.length
  const winrate  = resolved > 0 ? Math.round((won.length / resolved) * 100) : null
  let streak = 0
  for (const b of bets) {
    if (b.status === 'won') streak++
    else if (b.status === 'lost') break
  }
  return { gained, spent, winrate, streak, total: bets.length, profit: gained - spent }
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const d = Math.floor(diff / 86400000), h = Math.floor(diff / 3600000), m = Math.floor(diff / 60000)
  if (d > 0) return `il y a ${d}j`
  if (h > 0) return `il y a ${h}h`
  if (m > 0) return `il y a ${m}m`
  return "à l'instant"
}

function formatRank(ra) {
  if (!ra?.tier) return 'Non classé'
  const tierCap = ra.tier.charAt(0) + ra.tier.slice(1).toLowerCase()
  if (APEX_TIERS.has(ra.tier)) return `${tierCap} · ${ra.lp ?? 0} LP`
  return `${tierCap} ${ra.rank ?? ''} · ${ra.lp ?? 0} LP`
}

function ProfileSocials({ social }) {
  if (!social) return null
  const { discord, twitch, x_handle, instagram_handle } = social
  const items = []
  if (discord?.id) items.push({ key: 'discord', color: '#5865F2', url: `https://discord.com/users/${discord.id}`, label: discord.username, svg: <path d="M20.317 4.369A19.79 19.79 0 0 0 16.558 3.2a.07.07 0 0 0-.073.035 13.66 13.66 0 0 0-.61 1.252 18.27 18.27 0 0 0-5.487 0 12.6 12.6 0 0 0-.617-1.252.07.07 0 0 0-.074-.035 19.74 19.74 0 0 0-3.76 1.169.07.07 0 0 0-.031.027C2.533 8.045 1.876 11.612 2.198 15.135a.082.082 0 0 0 .031.056 19.9 19.9 0 0 0 5.993 3.029.07.07 0 0 0 .077-.027 14.2 14.2 0 0 0 1.226-1.994.07.07 0 0 0-.038-.098 13.1 13.1 0 0 1-1.872-.892.07.07 0 0 1-.007-.117c.126-.094.252-.192.372-.291a.07.07 0 0 1 .073-.01c3.927 1.793 8.18 1.793 12.061 0a.07.07 0 0 1 .074.009c.12.099.246.198.373.292a.07.07 0 0 1-.006.117c-.598.349-1.22.645-1.873.892a.07.07 0 0 0-.038.099c.36.698.772 1.362 1.225 1.993a.07.07 0 0 0 .078.027 19.84 19.84 0 0 0 6.002-3.029.07.07 0 0 0 .031-.055c.5-4.073-.838-7.61-3.549-10.74a.06.06 0 0 0-.031-.028zM8.02 12.99c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.211 0 2.176 1.095 2.157 2.42 0 1.333-.955 2.418-2.157 2.418zm7.974 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/> })
  if (twitch?.username) items.push({ key: 'twitch', color: '#9146FF', url: `https://twitch.tv/${twitch.username}`, label: twitch.username, svg: <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"/> })
  if (x_handle) items.push({ key: 'x', color: '#e8eaf0', url: `https://x.com/${x_handle.replace('@','')}`, label: x_handle, svg: <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/> })
  if (instagram_handle) items.push({ key: 'ig', color: '#E1306C', url: `https://instagram.com/${instagram_handle.replace('@','')}`, label: instagram_handle, svg: <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/> })
  if (!items.length) return null
  return (
    <div className="profile-hero-socials">
      {items.map(it => (
        <a key={it.key} href={it.url} target="_blank" rel="noopener noreferrer" className="profile-social-link" style={{ '--sc': it.color }} title={it.label}>
          <svg className="profile-hero-social-svg" viewBox="0 0 24 24" fill="currentColor" style={{ width: '100%', height: '100%' }}>{it.svg}</svg>
        </a>
      ))}
    </div>
  )
}

function AddRiotStepper({ onDone, onCancel }) {
  const [step,      setStep]      = useState(0)
  const [region,    setRegion]    = useState('EUW')
  const [riotId,    setRiotId]    = useState('')
  const [pending,   setPending]   = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error,     setError]     = useState('')

  const handleInit = async () => {
    setError(''); setLoading(true)
    const parts = riotId.trim().split('#')
    if (parts.length !== 2 || !parts[0] || !parts[1]) { setError('Format attendu : GameName#TAG'); setLoading(false); return }
    try {
      const { data } = await api.post('/profile/link-riot/init', { game_name: parts[0].trim(), tag_line: parts[1].trim(), region })
      setPending(data); setStep(1)
    } catch (err) { setError(err.response?.data?.detail || 'Riot ID introuvable') }
    finally { setLoading(false) }
  }

  const handleVerify = async () => {
    setError(''); setVerifying(true)
    try {
      const { data } = await api.post('/profile/link-riot/verify', { riot_account_id: pending.riot_account_id })
      onDone(data.riot_account)
    } catch (err) { setError(err.response?.data?.detail || 'Mauvaise icône, réessaie') }
    finally { setVerifying(false) }
  }

  return (
    <div className="add-riot-stepper">
      {step === 0 && <>
        <div className="add-riot-regions">
          {REGIONS.map(r => <button key={r} className={`add-riot-region-btn ${region === r ? 'active' : ''}`} onClick={() => { setRegion(r); setError('') }}>{r}</button>)}
        </div>
        <div className="add-riot-input-row">
          <input className="add-riot-input" placeholder="GameName#TAG" value={riotId} onChange={e => { setRiotId(e.target.value); setError('') }} />
          <button className="profile-btn-primary" onClick={handleInit} disabled={loading || !riotId.trim()}>
            {loading ? <span className="profile-spinner-sm" /> : 'Suivant →'}
          </button>
        </div>
        {error && <div className="add-riot-error">{error}</div>}
        <button className="add-riot-cancel" onClick={onCancel}>Annuler</button>
      </>}
      {step === 1 && pending && <>
        <div className="add-riot-verify-row">
          <img className="add-riot-verify-icon" src={pending.icon_url} alt={`icône ${pending.icon_id}`} />
          <div className="add-riot-verify-info">
            <div className="add-riot-verify-name">{pending.game_name}<span className="profile-riot-tag">#{pending.tag_line}</span></div>
            <div className="add-riot-verify-instruction">Équipe l'icône <strong>#{pending.icon_id}</strong> dans LoL puis clique Vérifier</div>
          </div>
        </div>
        {error && <div className="add-riot-error">{error}</div>}
        <div className="add-riot-verify-actions">
          <button className="add-riot-cancel" onClick={() => { setStep(0); setError('') }}>Retour</button>
          <button className="profile-btn-primary" onClick={handleVerify} disabled={verifying}>
            {verifying ? <span className="profile-spinner-sm" /> : '✓ Vérifier'}
          </button>
        </div>
      </>}
    </div>
  )
}

export default function Profile() {
  const navigate   = useNavigate()
  const { userId } = useParams()
  const fileRef    = useRef(null)
  const bannerRef  = useRef(null)
  const hasFetched = useRef(false)

  const { user, token, login, updateUser, fetchMe } = useAuthStore()

  const currentUserId = user?.id ?? null
  const isOwnProfile  = !userId || (currentUserId !== null && String(currentUserId) === String(userId))

  const [profile,        setProfile]        = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [bets,           setBets]           = useState([])
  const [betsLoading,    setBetsLoading]    = useState(false)
  const [userCards,      setUserCards]      = useState([])
  const [esportsTeams,   setEsportsTeams]   = useState([])
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const [showAddRiot,    setShowAddRiot]    = useState(false)
  const [rightTab,       setRightTab]       = useState('bets')
  const [zoomedCard,     setZoomedCard]     = useState(null)

  const loadProfile = () => {
    const own = !userId || (user && String(user.id) === String(userId))
    api.get(own ? '/profile/me' : `/profile/user/${userId}`)
      .then(r => setProfile(r.data))
      .catch(() => setProfile(null))
  }

  // Reset hasFetched si userId change (navigation entre profils)
  useEffect(() => {
    hasFetched.current = false
  }, [userId])

  // Chargement principal — une seule fois par userId
  useEffect(() => {
    if (hasFetched.current) return
    hasFetched.current = true

    const run = async () => {
      let resolvedId = currentUserId
      if (token && resolvedId === null) {
        await fetchMe()
        resolvedId = useAuthStore.getState().user?.id ?? null
      }

      const own = !userId || (resolvedId !== null && String(resolvedId) === String(userId))
      if (!token && own) { navigate('/login'); return }

      api.get(own ? '/profile/me' : `/profile/user/${userId}`)
        .then(r => setProfile(r.data))
        .catch(() => setProfile(null))
        .finally(() => setLoading(false))

      if (own && token) {
        setBetsLoading(true)
        api.get('/bets/my-bets').then(r => setBets(r.data)).catch(() => setBets([])).finally(() => setBetsLoading(false))
        api.get('/cards/my-cards').then(r => setUserCards(r.data)).catch(() => setUserCards([]))
      }
    }

    run()
  }, [userId])

  useEffect(() => {
    api.get('/esports/teams').then(r => setEsportsTeams(r.data)).catch(() => {})
  }, [])

  // ── Handlers ──

  // ── Handlers ──
  const handlePickTeam = async (team) => {
    const payload = { name: team.name, logo: team.logo_url || '', color: team.accent_color || '' }
    try {
      await api.post('/profile/set-team', payload)
      setProfile(p => ({ ...p, favorite_team: { name: payload.name, logo: payload.logo, color: payload.color } }))
    } catch (err) { console.error(err) }
    setShowTeamPicker(false)
  }

  const handleRemoveTeam = async () => {
    try {
      await api.post('/profile/set-team', { name: '', logo: '', color: '' })
      setProfile(p => ({ ...p, favorite_team: null }))
    } catch (err) { console.error(err) }
  }

  const handleAvatarUpload = async (e) => {
    const file = e.target.files[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    const tkn = localStorage.getItem('token')
    try {
      const res = await api.post(`/upload/avatar?authorization=Bearer ${tkn}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const newUrl = res.data.avatar_url || res.data.url
      setProfile(p => ({ ...p, avatar_url: newUrl }))
      login({ ...user, avatar_url: newUrl }, token)
    } catch (err) { console.error(err) }
  }

  const handleDeleteRiot = async (accountId) => {
    try {
      await api.delete(`/profile/riot-accounts/${accountId}`)
      setProfile(p => ({ ...p, riot_accounts: p.riot_accounts.filter(ra => ra.id !== accountId) }))
    } catch (err) { console.error(err) }
  }

  const handleSetPrimary = async (accountId) => {
    try {
      await api.post(`/profile/riot-accounts/${accountId}/set-primary`)
      setProfile(p => ({ ...p, riot_accounts: p.riot_accounts.map(ra => ({ ...ra, is_primary: ra.id === accountId })) }))
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

  // ── Guards ──
  if (loading) return (
    <div className="profile-page">
      <div className="profile-loading"><div className="profile-spinner" /><div className="profile-loading-text">Chargement du profil…</div></div>
    </div>
  )
  if (!profile) return (
    <div className="profile-page">
      <div className="profile-loading"><div className="profile-loading-text">Profil introuvable.</div></div>
    </div>
  )

  // ── Dérivés depuis profile ──
  const riotAccounts  = profile.riot_accounts || []
  const primaryAcc    = riotAccounts.find(ra => ra.is_primary) || riotAccounts[0] || null
  const otherAccs     = riotAccounts.filter(ra => ra.id !== primaryAcc?.id)
  const favTeam       = profile.favorite_team
  const accentColor   = favTeam?.color || '#65BD62'
  const avatarSrc     = profile.avatar_url || primaryAcc?.profile_icon_url || null
  const tierColor     = primaryAcc?.tier ? TIER_COLORS[primaryAcc.tier] : '#6b7280'
  const tierImg       = primaryAcc?.tier ? getTierImage(primaryAcc.tier) : null
  const equippedTitleId   = profile.equipped_title_id ?? null
  const equippedTitleText = profile.equipped_title_text ?? null
  const canAddMore    = isOwnProfile && riotAccounts.length < 3
  const displayName   = profile.username || '—'

  const stats = isOwnProfile
    ? computeStats(bets)
    : {
        gained:  profile.bet_stats?.total_won     ?? 0,
        spent:   profile.bet_stats?.total_wagered ?? 0,
        winrate: profile.bet_stats?.winrate       ?? null,
        streak:  profile.bet_stats?.streak        ?? 0,
        total:   profile.bet_stats?.total         ?? 0,
        profit:  (profile.bet_stats?.total_won ?? 0) - (profile.bet_stats?.total_wagered ?? 0),
      }

  const sortedUserCards = [...userCards].sort((a, b) => {
    const rA = RARITY_RANK[a.card.rarity] ?? 99
    const rB = RARITY_RANK[b.card.rarity] ?? 99
    return rA !== rB ? rA - rB : a.card.name.localeCompare(b.card.name)
  })

  return (
    <div className="profile-page">

      {/* ─── BANNER ─── */}
      <div className="profile-banner" ref={bannerRef} style={{ '--accent': accentColor }}>
        <div className="profile-banner-bg" style={{ background: `linear-gradient(135deg, ${accentColor}28 0%, ${accentColor}08 35%, #171717 75%)` }} />
        {favTeam?.logo && <img className="profile-banner-team-logo" src={favTeam.logo} alt={favTeam.name} referrerPolicy="no-referrer" />}
        <div className="profile-banner-glow" style={{ background: `radial-gradient(circle at 20% 50%, ${accentColor}25, transparent 60%)` }} />
        <div className="profile-banner-overlay" />

        <div className="profile-hero">
          <div className="profile-avatar-wrap">
            <div className="profile-avatar" style={{ borderColor: accentColor + '50' }}>
              {avatarSrc
                ? <img src={avatarSrc} alt={displayName} referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                : <div className="profile-avatar-fallback">{displayName.slice(0, 2).toUpperCase()}</div>
              }
            </div>
            {isOwnProfile && <>
              <button className="profile-avatar-edit" onClick={() => fileRef.current?.click()} title="Changer l'avatar">📷</button>
              <input ref={fileRef} type="file" accept="image/*" hidden onChange={handleAvatarUpload} />
            </>}
          </div>

          <div className="profile-hero-info">
            <div className="profile-hero-tag">PROFIL JUNGLE GAP</div>
            <h1 className="profile-hero-name">{displayName}</h1>
            {equippedTitleText && <div className="profile-hero-title">✦ {equippedTitleText}</div>}
            <ProfileSocials social={profile.social} />
            <div className="profile-hero-meta">
              {favTeam ? (
                <button className="profile-hero-team" style={{ '--tc': accentColor }} onClick={() => isOwnProfile && setShowTeamPicker(true)}>
                  {favTeam.logo && <img src={favTeam.logo} alt="" referrerPolicy="no-referrer" />}
                  <span>Fan de <strong>{favTeam.name}</strong></span>
                </button>
              ) : isOwnProfile ? (
                <button className="profile-hero-team profile-hero-team-empty" onClick={() => setShowTeamPicker(true)}>⚑ Choisir une équipe favorite</button>
              ) : null}
              {primaryAcc?.region && <div className="profile-hero-region"><span className="profile-hero-region-dot" />{primaryAcc.region}</div>}
            </div>
            {isOwnProfile && favTeam && <button className="profile-hero-team-remove" onClick={handleRemoveTeam}>✕ Retirer l'équipe</button>}
          </div>

          <BannerStickers userId={profile.id} isOwnProfile={isOwnProfile} bannerRef={bannerRef} />
        </div>
      </div>

      {/* ─── STAT STRIP ─── */}
      <div className="profile-stats-wrap">
        <div className="profile-stat-strip">
          <div className="pss-item">
            <div className="pss-val" style={{ color: stats.profit >= 0 ? '#65BD62' : '#ef4444' }}>{stats.profit >= 0 ? '+' : ''}{stats.profit.toLocaleString()}</div>
            <div className="pss-lbl">Profit net</div>
          </div>
          <div className="pss-divider" />
          <div className="pss-item">
            <div className="pss-val pss-val-accent">{stats.winrate !== null ? `${stats.winrate}%` : '—'}</div>
            <div className="pss-lbl">Winrate</div>
          </div>
          <div className="pss-divider" />
          <div className="pss-item">
            <div className="pss-val pss-val-gold">{stats.streak > 0 ? `🔥 ${stats.streak}` : '0'}</div>
            <div className="pss-lbl">Streak</div>
          </div>
          <div className="pss-divider" />
          <div className="pss-item">
            <div className="pss-val">{stats.total}</div>
            <div className="pss-lbl">Total paris</div>
          </div>
        </div>
      </div>

      {/* ─── COMPTE RIOT PRINCIPAL ─── */}
      {primaryAcc && (
        <div className="profile-main-riot" style={{ '--tier-color': tierColor }}>
          <div className="pmr-glow" style={{ background: `radial-gradient(circle at 80% 50%, ${tierColor}22, transparent 60%)` }} />
          <div className="pmr-left">
            <div className="pmr-icon-wrap">
              <div className="pmr-icon-glow" style={{ background: `radial-gradient(circle, ${tierColor}40, transparent 65%)` }} />
              {primaryAcc.profile_icon_url
                ? <img src={primaryAcc.profile_icon_url} alt="" className="pmr-icon" referrerPolicy="no-referrer" />
                : <div className="pmr-icon pmr-icon-placeholder">?</div>
              }
            </div>
            <div className="pmr-info">
              <div className="pmr-badge">COMPTE PRINCIPAL</div>
              <div className="pmr-name">{primaryAcc.summoner_name}<span className="pmr-tag">#{primaryAcc.tag_line}</span></div>
              <div className="pmr-region">{primaryAcc.region}</div>
            </div>
          </div>
          <div className="pmr-rank">
            {tierImg && <div className="pmr-rank-img"><img src={tierImg} alt={primaryAcc.tier} referrerPolicy="no-referrer" /></div>}
            <div className="pmr-rank-info">
              <div className="pmr-rank-tier" style={{ color: tierColor }}>{formatRank(primaryAcc)}</div>
              <div className="pmr-rank-queue">Solo / Duo</div>
            </div>
          </div>
          <div className="pmr-actions">
            <button className="pmr-btn pmr-btn-primary" onClick={() => goToPlayerPage(primaryAcc)}>Voir la page joueur →</button>
          </div>
        </div>
      )}

      {/* ─── COMPTES SECONDAIRES ─── */}
      {(otherAccs.length > 0 || canAddMore) && (
        <div className="profile-secondary-riots">
          <div className="psr-header">
            <span className="psr-label">Autres comptes liés</span>
            <span className="psr-count">{riotAccounts.length}/3</span>
          </div>
          <div className="psr-list">
            {otherAccs.map(ra => {
              const tc = ra.tier ? TIER_COLORS[ra.tier] : '#6b7280'
              const ti = ra.tier ? getTierImage(ra.tier) : null
              return (
                <div key={ra.id} className="psr-item">
                  <div className="psr-item-left">
                    {ra.profile_icon_url ? <img src={ra.profile_icon_url} alt="" className="psr-icon" referrerPolicy="no-referrer" /> : <div className="psr-icon psr-icon-placeholder">?</div>}
                    <div className="psr-item-info">
                      <div className="psr-item-name">{ra.summoner_name}<span className="psr-item-tag">#{ra.tag_line}</span></div>
                      <div className="psr-item-meta">
                        {ti && <img src={ti} alt="" className="psr-tier-mini" referrerPolicy="no-referrer" />}
                        <span style={{ color: tc }}>{formatRank(ra)}</span>
                        <span className="psr-item-region">· {ra.region}</span>
                      </div>
                    </div>
                  </div>
                  <div className="psr-item-actions">
                    <button className="psr-action" title="Voir page joueur" onClick={() => goToPlayerPage(ra)}>→</button>
                    {isOwnProfile && <>
                      <button className="psr-action" title="Définir comme principal" onClick={() => handleSetPrimary(ra.id)}>★</button>
                      <button className="psr-action danger" title="Supprimer" onClick={() => handleDeleteRiot(ra.id)}>✕</button>
                    </>}
                  </div>
                </div>
              )
            })}
            {isOwnProfile && showAddRiot && <AddRiotStepper onDone={handleRiotAdded} onCancel={() => setShowAddRiot(false)} />}
            {canAddMore && !showAddRiot && <button className="psr-add-btn" onClick={() => setShowAddRiot(true)}>+ Ajouter un compte Riot</button>}
          </div>
        </div>
      )}

      {riotAccounts.length === 0 && isOwnProfile && (
        <div className="profile-no-riot">
          <div className="profile-no-riot-icon">🎮</div>
          <div className="profile-no-riot-title">Aucun compte Riot lié</div>
          <div className="profile-no-riot-sub">Lie un compte pour afficher ton rank et accéder à ta page joueur</div>
          {showAddRiot
            ? <AddRiotStepper onDone={handleRiotAdded} onCancel={() => setShowAddRiot(false)} />
            : <button className="profile-btn-primary" onClick={() => setShowAddRiot(true)}>+ Lier un compte Riot</button>
          }
        </div>
      )}

      {/* ─── GRID ─── */}
      <div className="profile-grid">
        <div className="profile-col-left">
          <div className="profile-card">
            <div className="profile-card-label">Statistiques détaillées</div>
            <div className="profile-stats-grid">
              <div className="profile-stat"><div className="profile-stat-val green">+{stats.gained.toLocaleString()}</div><div className="profile-stat-lbl">Coins gagnés</div></div>
              <div className="profile-stat"><div className="profile-stat-val red">-{stats.spent.toLocaleString()}</div><div className="profile-stat-lbl">Coins perdus</div></div>
              <div className="profile-stat">
                <div className="profile-stat-val accent">{stats.winrate !== null ? `${stats.winrate}%` : '—'}</div>
                <div className="profile-stat-lbl">Win rate</div>
                {stats.winrate !== null && <div className="profile-stat-bar"><div className="profile-stat-bar-fill" style={{ width: `${stats.winrate}%`, background: stats.winrate >= 50 ? '#65BD62' : '#ef4444' }} /></div>}
              </div>
              <div className="profile-stat"><div className="profile-stat-val gold">{stats.streak > 0 ? `🔥 ${stats.streak}` : '0'}</div><div className="profile-stat-lbl">Streak actuel</div></div>
            </div>
          </div>
          {isOwnProfile && (
            <div className="profile-card profile-card-balance">
              <div className="profile-card-label">Solde actuel</div>
              <div className="profile-balance-val"><span className="profile-balance-icon">🪙</span><span>{user?.coins?.toLocaleString() ?? '—'}</span></div>
              <div className="profile-balance-sub">coins disponibles</div>
              <button className="profile-btn-secondary" onClick={() => navigate('/settings')} style={{ marginTop: 12, width: '100%' }}>⚙️ Paramètres du compte</button>
            </div>
          )}
        </div>

        <div className="profile-col-right">
          <div className="profile-card profile-card-tabs">
            <div className="profile-tabs">
              <button className={`profile-tab ${rightTab === 'bets' ? 'active' : ''}`} onClick={() => setRightTab('bets')}>
                🎯 Paris {bets.length > 0 && <span className="profile-tab-count">{bets.length}</span>}
              </button>
              <button className={`profile-tab ${rightTab === 'cards' ? 'active' : ''}`} onClick={() => setRightTab('cards')}>
                🃏 Collection {userCards.length > 0 && <span className="profile-tab-count">{userCards.length}</span>}
              </button>
            </div>

            {rightTab === 'bets' && (
              <div className="profile-bets-scroll">
                {betsLoading && <div className="profile-bets-empty">Chargement…</div>}
                {!betsLoading && !isOwnProfile && <div className="profile-bets-empty">Historique privé.</div>}
                {!betsLoading && isOwnProfile && bets.length === 0 && <div className="profile-bets-empty">Aucun pari pour le moment.</div>}
                {!betsLoading && isOwnProfile && bets.map(bet => {
                  const isWon = bet.status === 'won', isLost = bet.status === 'lost', isPending = bet.status === 'pending'
                  return (
                    <div key={bet.id} className={`profile-bet-row ${bet.status}`}>
                      <div className="profile-bet-champ">
                        {bet.game?.bet_player?.champion_icon
                          ? <img src={bet.game.bet_player.champion_icon} alt={bet.game.bet_player.champion_name} onError={e => { e.target.style.display = 'none' }} />
                          : <span className="profile-bet-champ-fallback">🎯</span>
                        }
                      </div>
                      <div className="profile-bet-info">
                        <div className="profile-bet-main">
                          <span className="profile-bet-type">{BET_TYPE_LABELS[bet.bet_type] || bet.bet_type}</span>
                          <span className="profile-bet-sep">·</span>
                          <span className="profile-bet-side">{BET_VALUE_LABELS[bet.bet_value] || bet.bet_value}</span>
                          {bet.game?.bet_player?.champion_name && <span className="profile-bet-champ-name">{bet.game.bet_player.champion_name}</span>}
                        </div>
                        <div className="profile-bet-sub">
                          {bet.game?.pro?.name && <span>{bet.game.pro.name}</span>}
                          {bet.game?.pro?.team && <span className="profile-bet-team">{bet.game.pro.team}</span>}
                          <span className="profile-bet-time">{timeAgo(bet.created_at)}</span>
                        </div>
                      </div>
                      <div className="profile-bet-result">
                        <div className={`profile-bet-amount ${isWon ? 'green' : isLost ? 'red' : 'muted'}`}>
                          {isWon && `+${(bet.payout || 0).toLocaleString()}`}
                          {isLost && `-${bet.amount.toLocaleString()}`}
                          {isPending && bet.amount.toLocaleString()}
                        </div>
                        <div className={`profile-bet-status-badge ${bet.status}`}>
                          {isWon && '✓ Gagné'}{isLost && '✗ Perdu'}{isPending && '⏳ En cours'}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {rightTab === 'cards' && (
              <div className="profile-tcg-scroll">
                {!isOwnProfile && <div className="profile-bets-empty">Collection privée.</div>}
                {isOwnProfile && userCards.length === 0 && <div className="profile-bets-empty"><div style={{ fontSize: 32, marginBottom: 8 }}>🃏</div>Aucune carte dans la collection.</div>}
                {isOwnProfile && userCards.length > 0 && (
                  <div className="profile-tcg-grid">
                    {sortedUserCards.map(uc => (
                      <div key={uc.id} style={{ cursor: 'pointer' }} onClick={() => setZoomedCard({ card: uc.card, quantity: uc.quantity, userCardId: uc.id })}>
                        <TcgCard card={uc.card} size="sm" minimal />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─── TEAM PICKER ─── */}
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
                    <div key={team.name} className={`profile-picker-team ${selected ? 'selected' : ''}`} style={{ '--tc': team.accent_color || '#65BD62' }} onClick={() => handlePickTeam(team)}>
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

      {/* ─── ZOOM CARTE ─── */}
      {zoomedCard && (
        <TcgCardModal
          card={zoomedCard.card}
          quantity={zoomedCard.quantity}
          userCardId={zoomedCard.userCardId}
          equippedTitleId={equippedTitleId}
          onTitleChange={(newId) => { updateUser?.({ equipped_title_id: newId }); loadProfile() }}
          onClose={() => setZoomedCard(null)}
        />
      )}
    </div>
  )
}