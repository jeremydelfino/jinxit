import './Navbar.css'
import { useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import useAuthStore from '../../../store/auth'
import api from '../../../api/client'

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
  const notifRef = useRef(null)
  const menuRef  = useRef(null)

  /* ── Scroll ── */
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handler)
    return () => window.removeEventListener('scroll', handler)
  }, [])

  /* ── Fermer dropdowns au clic extérieur ── */
  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false)
      if (menuRef.current  && !menuRef.current.contains(e.target))  setMenuOpen(false)
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
            <span className="notif-empty-icon">🔔</span>
            <span>Aucune notification</span>
          </div>
        ) : (
          notifs.map(notif => (
            <div
              key={notif.id}
              className={`notif-item ${!notif.read ? 'unread' : ''} ${notif.data?.live_game_id ? 'clickable' : ''}`}
              onClick={() => handleNotifClick(notif)}
            >
              <div className="notif-item-icon">{notif.type === 'favorite_live' ? '🟢' : '🔔'}</div>
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
          {[
            { path: '/',           icon: '⚡', label: 'Live' },
            { path: '/betonpros', icon: '🎖️', label: 'Ligues Pros' },
            { path: '/bets',      icon: '🎯', label: 'Mes Paris' },
            { path: '/leaderboard', icon: '🏆', label: 'Classement' },
          ].map(({ path, icon, label }) => (
            <button
              key={path}
              className={`nav-link ${isActive(path) ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <span className="nav-link-icon">{icon}</span>
              {label}
              {isActive(path) && <span className="nav-link-indicator" />}
            </button>
          ))}
        </div>

        {/* ── RIGHT ── */}
        <div className="navbar-right">
          {user ? (
            <>
              {/* Daily — desktop seulement (géré dans bottom nav sur mobile) */}
              <div className="daily-wrap">
                <button
                  className={`daily-btn ${dailyAvailable ? 'available' : 'claimed'} ${dailyClaiming ? 'claiming' : ''}`}
                  onClick={handleDaily}
                  disabled={!dailyAvailable || dailyClaiming}
                  title={dailyAvailable ? 'Bonus quotidien (+100 coins)' : 'Déjà réclamé'}
                >
                  <span className="daily-icon">{dailyClaiming ? '⏳' : '🎁'}</span>
                  {dailyAvailable && <span className="daily-ping" />}
                </button>
                {dailyFlash && <span className="daily-flash">+100 🪙</span>}
              </div>

              {/* Notifs — desktop */}
              <div className="notif-wrap" ref={notifRef}>
                <button
                  className={`notif-btn ${unreadCount > 0 ? 'has-unread' : ''}`}
                  onClick={() => setNotifOpen(o => !o)}
                >
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                  </svg>
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

              {/* Avatar */}
              <div className="navbar-avatar-wrap" ref={menuRef} onClick={() => setMenuOpen(o => !o)}>
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

                {menuOpen && (
                  <div className="avatar-dropdown" onClick={e => e.stopPropagation()}>
                    <div className="dropdown-header">
                      <div className="dropdown-username">{user.username}</div>
                      <div className="dropdown-coins">
                        <span className="coins-icon-inner" style={{ width: 6, height: 6 }} />
                        {user.coins?.toLocaleString()} coins
                      </div>
                    </div>
                    <div className="dropdown-divider" />
                    <button className="dropdown-item" onClick={() => { navigate('/profile'); setMenuOpen(false) }}><span>👤</span> Mon profil</button>
                    <button className="dropdown-item" onClick={() => { navigate('/settings'); setMenuOpen(false) }}><span>⚙️</span> Paramètres</button>
                    <div className="dropdown-divider" />
                    <button className="dropdown-item danger" onClick={() => { logout(); navigate('/'); setMenuOpen(false) }}><span>↩</span> Déconnexion</button>
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

          {/* Live */}
          <button className={`bottom-nav-item ${isActive('/') ? 'active' : ''}`} onClick={() => navigate('/')}>
            <div className="bnav-icon-wrap">⚡{isActive('/') && <span className="bnav-active-dot" />}</div>
            <span className="bnav-label">Live</span>
          </button>

          {/* Ligues */}
          <button className={`bottom-nav-item ${isActive('/betonpros') ? 'active' : ''}`} onClick={() => navigate('/betonpros')}>
            <div className="bnav-icon-wrap">🎖️{isActive('/betonpros') && <span className="bnav-active-dot" />}</div>
            <span className="bnav-label">Ligues</span>
          </button>

          {/* Paris */}
          <button className={`bottom-nav-item ${isActive('/bets') ? 'active' : ''}`} onClick={() => navigate('/bets')}>
            <div className="bnav-icon-wrap">🎯{isActive('/bets') && <span className="bnav-active-dot" />}</div>
            <span className="bnav-label">Paris</span>
          </button>

          {/* Notifs */}
          <div className="bottom-nav-item" ref={notifRef} style={{ position: 'relative' }}>
            <div className="bnav-icon-wrap" onClick={() => setNotifOpen(o => !o)} style={{ cursor: 'pointer' }}>
              🔔
              {unreadCount > 0 && <span className="bnav-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
            </div>
            <span className="bnav-label" style={{ pointerEvents: 'none' }}>Alertes</span>
            {notifOpen && <NotifDropdown />}
          </div>

          {/* Daily + Profil */}
          <div className="bottom-nav-item" ref={menuRef} style={{ position: 'relative' }}>
            <div className="bnav-icon-wrap" onClick={() => setMenuOpen(o => !o)} style={{ cursor: 'pointer' }}>
              {/* Avatar ou icône */}
              {user.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: 28, height: 28, borderRadius: 8, objectFit: 'cover' }} onError={e => { e.target.style.display = 'none' }} />
                : <span style={{ fontSize: 20 }}>👤</span>
              }
              {dailyAvailable && <span className="bnav-ping" />}
            </div>
            <span className="bnav-label" style={{ pointerEvents: 'none' }}>Profil</span>

            {menuOpen && (
              <div className="avatar-dropdown" onClick={e => e.stopPropagation()}>
                <div className="dropdown-header">
                  <div className="dropdown-username">{user.username}</div>
                  <div className="dropdown-coins">
                    <span className="coins-icon-inner" style={{ width: 6, height: 6 }} />
                    {user.coins?.toLocaleString()} coins
                  </div>
                </div>
                <div className="dropdown-divider" />
                {/* Daily bonus dans le menu mobile */}
                {dailyAvailable && (
                  <button className="dropdown-item" onClick={() => { handleDaily(); setMenuOpen(false) }}>
                    <span>🎁</span> Bonus quotidien
                  </button>
                )}
                <button className="dropdown-item" onClick={() => { navigate('/profile'); setMenuOpen(false) }}><span>👤</span> Mon profil</button>
                <button className="dropdown-item" onClick={() => { navigate('/leaderboard'); setMenuOpen(false) }}><span>🏆</span> Classement</button>
                <button className="dropdown-item" onClick={() => { navigate('/settings'); setMenuOpen(false) }}><span>⚙️</span> Paramètres</button>
                <div className="dropdown-divider" />
                <button className="dropdown-item danger" onClick={() => { logout(); navigate('/'); setMenuOpen(false) }}><span>↩</span> Déconnexion</button>
              </div>
            )}
          </div>

        </nav>
      )}
    </>
  )
}