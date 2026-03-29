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
  const [notifOpen,    setNotifOpen]    = useState(false)
  const [notifs,       setNotifs]       = useState([])
  const [unreadCount,  setUnreadCount]  = useState(0)
  const notifRef = useRef(null)
  const menuRef  = useRef(null)

  /* ── Scroll effect ── */
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

  /* ── Init profil + daily + notifs ── */
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

  /* ── Polling notifs toutes les 60s ── */
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
    /* Marquer comme lue */
    if (!notif.read) {
      try {
        await api.post(`/favorites/notifications/${notif.id}/read`)
        setNotifs(prev => prev.map(n => n.id === notif.id ? { ...n, read: true } : n))
        setUnreadCount(c => Math.max(0, c - 1))
      } catch {}
    }
    /* Naviguer vers la game si dispo */
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

  return (
    <nav className={`navbar ${scrolled ? 'navbar-scrolled' : ''}`}>

      <div className="navbar-top-line" />

      {/* ── LOGO ── */}
      <div className="navbar-logo" onClick={() => navigate('/')}>
        <span className="logo-j">J</span>UNGLEGAP
        <span className="logo-dot" />
      </div>

      {/* ── NAV LINKS ── */}
      <div className="navbar-links">
        <button className={`nav-link ${isActive('/') ? 'active' : ''}`} onClick={() => navigate('/')}>
          <span className="nav-link-icon">⚡</span>
          Live
          {isActive('/') && <span className="nav-link-indicator" />}
        </button>
        <button className={`nav-link ${isActive('/betonpros') ? 'active' : ''}`} onClick={() => navigate('/betonpros')}>
          <span className="nav-link-icon">🎖️</span>
          Ligues Pros
          {isActive('/betonpros') && <span className="nav-link-indicator" />}
        </button>
        <button className={`nav-link ${isActive('/bets') ? 'active' : ''}`} onClick={() => navigate('/bets')}>
          <span className="nav-link-icon">🎯</span>
          Mes Paris
          {isActive('/bets') && <span className="nav-link-indicator" />}
        </button>
        <button className={`nav-link ${isActive('/leaderboard') ? 'active' : ''}`} onClick={() => navigate('/leaderboard')}>
          <span className="nav-link-icon">🏆</span>
          Classement
          {isActive('/leaderboard') && <span className="nav-link-indicator" />}
        </button>
      </div>

      {/* ── RIGHT ── */}
      <div className="navbar-right">
        {user ? (
          <>
            {/* ── DAILY BONUS ── */}
            <div className="daily-wrap">
              <button
                className={`daily-btn ${dailyAvailable ? 'available' : 'claimed'} ${dailyClaiming ? 'claiming' : ''}`}
                onClick={handleDaily}
                disabled={!dailyAvailable || dailyClaiming}
                title={dailyAvailable ? 'Récupérer ton bonus quotidien (+100 coins)' : 'Bonus déjà réclamé aujourd\'hui'}
              >
                <span className="daily-icon">{dailyClaiming ? '⏳' : '🎁'}</span>
                {dailyAvailable && <span className="daily-ping" />}
              </button>
              {dailyFlash && <span className="daily-flash">+100 🪙</span>}
            </div>

            {/* ── CLOCHE NOTIFS ── */}
            <div className="notif-wrap" ref={notifRef}>
              <button
                className={`notif-btn ${unreadCount > 0 ? 'has-unread' : ''}`}
                onClick={() => setNotifOpen(o => !o)}
                title="Notifications"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {unreadCount > 0 && (
                  <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
                )}
              </button>

              {notifOpen && (
                <div className="notif-dropdown">
                  <div className="notif-header">
                    <span className="notif-title">Notifications</span>
                    {unreadCount > 0 && (
                      <button className="notif-mark-all" onClick={handleMarkAllRead}>
                        Tout lire
                      </button>
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
                          <div className="notif-item-icon">
                            {notif.type === 'favorite_live' ? '🟢' : '🔔'}
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
              )}
            </div>

            {/* ── COINS ── */}
            <div className="navbar-coins" onClick={() => navigate('/profile')}>
              <div className="coins-icon">
                <span className="coins-icon-inner" />
              </div>
              <span className="coins-value">{user.coins?.toLocaleString() ?? '—'}</span>
              <span className="coins-label">coins</span>
            </div>

            {/* ── AVATAR ── */}
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
                  <button className="dropdown-item" onClick={() => { navigate('/profile'); setMenuOpen(false) }}>
                    <span>👤</span> Mon profil
                  </button>
                  <button className="dropdown-item" onClick={() => { navigate('/bets'); setMenuOpen(false) }}>
                    <span>🎯</span> Mes paris
                  </button>
                  <div className="dropdown-divider" />
                  <button className="dropdown-item danger" onClick={() => { logout(); navigate('/'); setMenuOpen(false) }}>
                    <span>↩</span> Déconnexion
                  </button>
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
  )
}