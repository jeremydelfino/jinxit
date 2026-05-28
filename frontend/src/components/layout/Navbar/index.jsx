import './Navbar.css'
import { useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import useAuthStore from '../../../store/auth'
import api from '../../../api/client'

/* ══════════════════════════════════════
   ICÔNES — SVG line (stroke = currentColor)
══════════════════════════════════════ */
const Icon = ({ d, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
)

const ICONS = {
  live:    <><circle cx="12" cy="12" r="3"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14M19.07 4.93a10 10 0 0 1 0 14.14M7.76 7.76a6 6 0 0 0 0 8.48M16.24 7.76a6 6 0 0 1 0 8.48"/></>,
  leagues: <><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22M18 2H6v7a6 6 0 0 0 12 0V2Z"/></>,
  games:   <><line x1="6" y1="11" x2="10" y2="11"/><line x1="8" y1="9" x2="8" y2="13"/><line x1="15" y1="12" x2="15.01" y2="12"/><line x1="18" y1="10" x2="18.01" y2="10"/><rect x="2" y="6" width="20" height="12" rx="2"/></>,
  bets:    <><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></>,
  ranking: <><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></>,
  collection: <><rect width="7" height="18" x="3" y="3" rx="1.5"/><path d="m12.5 4 6 1.5a1 1 0 0 1 .7 1.2l-3 13a1 1 0 0 1-1.2.7"/></>,
  bell:    <><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></>,
  gift:    <><rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/></>,
  user:    <><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
  settings:<><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/></>,
  logout:  <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>,
}

const NAV_ITEMS = [
  { path: '/',            key: 'live',       label: 'Live' },
  { path: '/betonpros',   key: 'leagues',    label: 'Ligues Pros' },
  { path: '/games',       key: 'games',      label: 'Jeux' },
  { path: '/bets',        key: 'bets',       label: 'Mes Prédictions' },
  { path: '/leaderboard', key: 'ranking',    label: 'Classement' },
  { path: '/lootbox',     key: 'collection', label: 'Collection' },
]

const MOBILE_ITEMS = [
  { path: '/',          key: 'live',       label: 'Live' },
  { path: '/betonpros', key: 'leagues',    label: 'Ligues Pros' },
  { path: '/bets',      key: 'bets',       label: 'Mes Prédictions' },
  { path: '/games',     key: 'games',      label: 'Jeux' },
  { path: '/lootbox',   key: 'collection', label: 'Collection' },
]

export default function Navbar() {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { user, logout, updateUser } = useAuthStore()

  const [scrolled,       setScrolled]       = useState(false)
  const [menuOpen,       setMenuOpen]       = useState(false)
  const [dailyAvailable, setDailyAvailable] = useState(false)
  const [dailyClaiming,  setDailyClaiming]  = useState(false)
  const [dailyFlash,     setDailyFlash]     = useState(false)

  /* ── NOTIFICATIONS ── */
  const [notifOpen,   setNotifOpen]   = useState(false)
  const [notifs,      setNotifs]      = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  /* ── Refs séparées desktop / mobile ── */
  const notifRefDesktop = useRef(null)
  const notifRefMobile  = useRef(null)
  const menuRefDesktop  = useRef(null)
  const menuRefMobile   = useRef(null)

  /* ── Scroll ── */
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handler)
    return () => window.removeEventListener('scroll', handler)
  }, [])

  /* ── Fermer dropdowns au clic extérieur (vérifie LES DEUX refs) ── */
  useEffect(() => {
    const handler = (e) => {
      const inNotif = (notifRefDesktop.current && notifRefDesktop.current.contains(e.target))
                   || (notifRefMobile.current  && notifRefMobile.current.contains(e.target))
      const inMenu  = (menuRefDesktop.current  && menuRefDesktop.current.contains(e.target))
                   || (menuRefMobile.current   && menuRefMobile.current.contains(e.target))
      if (!inNotif) setNotifOpen(false)
      if (!inMenu)  setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  /* ── Init ── */
  useEffect(() => {
    if (!user) return
    Promise.all([
      api.get('/profile/me'),
      api.get('/coins/balance'),
    ]).then(([profileRes, balanceRes]) => {
      updateUser({ coins: profileRes.data.coins, avatar_url: profileRes.data.avatar_url })
      setDailyAvailable(balanceRes.data.daily_disponible)
    }).catch(() => {})
    fetchNotifs()
  }, [])

  /* ── Polling notifs 60s ── */
  useEffect(() => {
    if (!user) return
    const interval = setInterval(fetchNotifs, 60_000)
    return () => clearInterval(interval)
  }, [user])

  const fetchNotifs = async () => {
    try {
      const res = await api.get('/favorites/notifications')
      setNotifs(res.data)
      setUnreadCount(res.data.filter(n => !n.read).length)
    } catch {}
  }

  const handleDaily = async () => {
    if (!dailyAvailable || dailyClaiming) return
    setDailyClaiming(true)
    try {
      const res = await api.post('/coins/daily')
      updateUser({ coins: res.data.coins_total })
      setDailyAvailable(false)
      setDailyFlash(true)
      setTimeout(() => setDailyFlash(false), 2000)
    } catch {}
    finally { setDailyClaiming(false) }
  }

  const handleNotifClick = async (notif) => {
    if (!notif.read) {
      try {
        await api.post(`/favorites/notifications/${notif.id}/read`)
        setNotifs(prev => prev.map(n => n.id === notif.id ? { ...n, read: true } : n))
        setUnreadCount(c => Math.max(0, c - 1))
      } catch {}
    }
    if (notif.data?.live_game_id) {
      navigate(`/game/${notif.data.live_game_id}`)
      setNotifOpen(false)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.post('/favorites/notifications/read-all')
      setNotifs(prev => prev.map(n => ({ ...n, read: true })))
      setUnreadCount(0)
    } catch {}
  }

  const isActive = (path) => location.pathname === path

  const formatNotifTime = (dateStr) => {
    const diff = Date.now() - new Date(dateStr).getTime()
    const min  = Math.floor(diff / 60_000)
    if (min < 1)  return 'à l\'instant'
    if (min < 60) return `il y a ${min}min`
    const h = Math.floor(min / 60)
    if (h < 24)   return `il y a ${h}h`
    return `il y a ${Math.floor(h / 24)}j`
  }

  /* ── Dropdown notifs (partagé desktop + mobile) ── */
  const NotifDropdown = () => (
    <div className="notif-dropdown">
      <div className="notif-header">
        <span className="notif-title">Notifications</span>
        {unreadCount > 0 && (
          <button className="notif-mark-all" onClick={handleMarkAllRead}>Tout lire</button>
        )}
      </div>
      <div className="notif-list">
        {notifs.length === 0 ? (
          <div className="notif-empty">
            <span className="notif-empty-icon"><Icon d={ICONS.bell} size={22} /></span>
            <span>Aucune notification</span>
          </div>
        ) : (
          notifs.map(notif => (
            <div
              key={notif.id}
              className={`notif-item ${!notif.read ? 'unread' : ''} ${notif.data?.live_game_id ? 'clickable' : ''}`}
              onClick={() => handleNotifClick(notif)}
            >
              <div className={`notif-item-icon ${notif.type === 'favorite_live' ? 'live' : ''}`}>
                {notif.type === 'favorite_live'
                  ? <span className="notif-live-dot" />
                  : <Icon d={ICONS.bell} size={14} />}
              </div>
              <div className="notif-item-body">
                <div className="notif-item-msg">{notif.message}</div>
                <div className="notif-item-time">{formatNotifTime(notif.created_at)}</div>
              </div>
              {!notif.read && <span className="notif-unread-dot" />}
            </div>
          ))
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* ════════ TOP BAR ════════ */}
      <nav className={`navbar ${scrolled ? 'navbar-scrolled' : ''}`}>

        <div className="navbar-top-line" />

        {/* ── LOGO ── */}
        <div className="navbar-logo" onClick={() => navigate('/')}>
          <img
            src="/logo.png"
            alt="JungleGap"
            className="navbar-logo-img"
            onError={e => { e.target.style.display = 'none' }}
          />
          <div className="navbar-logo-text">
            <span className="logo-name">JUNGLEGAP</span>
            <span className="logo-badge">BETA</span>
          </div>
        </div>

        {/* ── NAV LINKS (desktop) ── */}
        <div className="navbar-links">
          {NAV_ITEMS.map(({ path, key, label }) => (
            <button
              key={path}
              className={`nav-link ${isActive(path) ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <span className="nav-link-icon"><Icon d={ICONS[key]} size={17} /></span>
              <span className="nav-link-label">{label}</span>
              <span className="nav-link-pill" />
              {isActive(path) && <span className="nav-link-indicator" />}
            </button>
          ))}
        </div>

        {/* ── RIGHT ── */}
        <div className="navbar-right">
          {user ? (
            <>
              {/* Daily — desktop seulement */}
              <div className="daily-wrap">
                <button
                  className={`daily-btn ${dailyAvailable ? 'available' : 'claimed'} ${dailyClaiming ? 'claiming' : ''}`}
                  onClick={handleDaily}
                  disabled={!dailyAvailable || dailyClaiming}
                  title={dailyAvailable ? 'Bonus quotidien (+100 coins)' : 'Déjà réclamé'}
                >
                  <span className="daily-icon"><Icon d={ICONS.gift} size={17} /></span>
                  {dailyAvailable && <span className="daily-ping" />}
                </button>
                {dailyFlash && <span className="daily-flash">+100</span>}
              </div>

              {/* Notifs — desktop */}
              <div className="notif-wrap" ref={notifRefDesktop}>
                <button
                  className={`notif-btn ${unreadCount > 0 ? 'has-unread' : ''}`}
                  onClick={() => setNotifOpen(o => !o)}
                >
                  <Icon d={ICONS.bell} size={17} />
                  {unreadCount > 0 && (
                    <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
                  )}
                </button>
                {notifOpen && <NotifDropdown />}
              </div>

              {/* Coins */}
              <div className="navbar-coins" onClick={() => navigate('/profile')}>
                <div className="coins-icon"><span className="coins-icon-inner" /></div>
                <span className="coins-value">{user.coins?.toLocaleString() ?? '—'}</span>
                <span className="coins-label">coins</span>
              </div>

              {/* Avatar desktop */}
              <div className="navbar-avatar-wrap" ref={menuRefDesktop}>
                <div className="navbar-avatar-trigger" onClick={() => setMenuOpen(o => !o)}>
                  <div className="navbar-avatar">
                    {user.avatar_url
                      ? <img src={user.avatar_url} alt="avatar" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                      : <span>{user.username?.slice(0, 2).toUpperCase()}</span>
                    }
                  </div>
                  <div className="avatar-status" />
                  <span className="navbar-username">{user.username}</span>
                  <svg className={`avatar-chevron ${menuOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </div>

                {menuOpen && (
                  <div className="avatar-dropdown">
                    <div className="dropdown-header">
                      <div className="dropdown-username">{user.username}</div>
                      <div className="dropdown-coins">
                        <span className="coins-icon-inner" style={{ width: 6, height: 6 }} />
                        {user.coins?.toLocaleString()} coins
                      </div>
                    </div>
                    <div className="dropdown-divider" />
                    <button className="dropdown-item" onClick={() => { navigate('/profile'); setMenuOpen(false) }}><Icon d={ICONS.user} size={15} /> Mon profil</button>
                    <button className="dropdown-item" onClick={() => { navigate('/settings'); setMenuOpen(false) }}><Icon d={ICONS.settings} size={15} /> Paramètres</button>
                    <div className="dropdown-divider" />
                    <button className="dropdown-item danger" onClick={() => { logout(); navigate('/'); setMenuOpen(false) }}><Icon d={ICONS.logout} size={15} /> Déconnexion</button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <button className="btn-nav-ghost" onClick={() => navigate('/login')}>Connexion</button>
              <button className="btn-nav-primary" onClick={() => navigate('/register')}>S'inscrire</button>
            </>
          )}
        </div>
      </nav>

      {/* ════════ BOTTOM NAV (mobile uniquement) ════════ */}
      {user && (
        <nav className="bottom-nav">

          {MOBILE_ITEMS.map(({ path, key, label }) => (
            <button
              key={path}
              className={`bottom-nav-item ${isActive(path) ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <div className="bnav-icon-wrap">
                <Icon d={ICONS[key]} size={20} />
                {isActive(path) && <span className="bnav-active-dot" />}
              </div>
              <span className="bnav-label">{label}</span>
            </button>
          ))}

          {/* Notifs mobile */}
          <div className="bottom-nav-item" ref={notifRefMobile} style={{ position: 'relative' }}>
            <div className="bnav-icon-wrap" onClick={() => setNotifOpen(o => !o)} style={{ cursor: 'pointer' }}>
              <Icon d={ICONS.bell} size={20} />
              {unreadCount > 0 && <span className="bnav-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
            </div>
            <span className="bnav-label" style={{ pointerEvents: 'none' }}>Alertes</span>
            {notifOpen && <NotifDropdown />}
          </div>

          {/* Daily + Profil mobile */}
          <div className="bottom-nav-item" ref={menuRefMobile} style={{ position: 'relative' }}>
            <div className="bnav-icon-wrap" onClick={() => setMenuOpen(o => !o)} style={{ cursor: 'pointer' }}>
              {user.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: 28, height: 28, borderRadius: 8, objectFit: 'cover' }} onError={e => { e.target.style.display = 'none' }} />
                : <Icon d={ICONS.user} size={20} />
              }
              {dailyAvailable && <span className="bnav-ping" />}
            </div>
            <span className="bnav-label" style={{ pointerEvents: 'none' }}>Profil</span>

            {menuOpen && (
              <div className="avatar-dropdown">
                <div className="dropdown-header">
                  <div className="dropdown-username">{user.username}</div>
                  <div className="dropdown-coins">
                    <span className="coins-icon-inner" style={{ width: 6, height: 6 }} />
                    {user.coins?.toLocaleString()} coins
                  </div>
                </div>
                <div className="dropdown-divider" />
                {dailyAvailable && (
                  <button className="dropdown-item" onClick={() => { handleDaily(); setMenuOpen(false) }}>
                    <Icon d={ICONS.gift} size={15} /> Bonus quotidien
                  </button>
                )}
                <button className="dropdown-item" onClick={() => { navigate('/profile'); setMenuOpen(false) }}><Icon d={ICONS.user} size={15} /> Mon profil</button>
                <button className="dropdown-item" onClick={() => { navigate('/leaderboard'); setMenuOpen(false) }}><Icon d={ICONS.ranking} size={15} /> Classement</button>
                <button className="dropdown-item" onClick={() => { navigate('/settings'); setMenuOpen(false) }}><Icon d={ICONS.settings} size={15} /> Paramètres</button>
                <div className="dropdown-divider" />
                <button className="dropdown-item danger" onClick={() => { logout(); navigate('/'); setMenuOpen(false) }}><Icon d={ICONS.logout} size={15} /> Déconnexion</button>
              </div>
            )}
          </div>

        </nav>
      )}
    </>
  )
}