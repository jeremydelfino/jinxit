import './Navbar.css'
import { useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import useAuthStore from '../../../store/auth'
import api from '../../../api/client'


export default function Navbar() {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { user, logout, updateUser } = useAuthStore()
  const [scrolled,      setScrolled]      = useState(false)
  const [menuOpen,      setMenuOpen]      = useState(false)
  const [dailyAvailable, setDailyAvailable] = useState(false)
  const [dailyClaiming,  setDailyClaiming]  = useState(false)
  const [dailyFlash,     setDailyFlash]     = useState(false) // animation +100

  // Scroll effect
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handler)
    return () => window.removeEventListener('scroll', handler)
  }, [])

  // Fetch profil + statut daily au montage
  useEffect(() => {
    if (!user) return
    Promise.all([
      api.get('/profile/me'),
      api.get('/coins/balance'),
    ]).then(([profileRes, balanceRes]) => {
      updateUser({
        coins:      profileRes.data.coins,
        avatar_url: profileRes.data.avatar_url,
      })
      setDailyAvailable(balanceRes.data.daily_disponible)
    }).catch(() => {})
  }, [])

  const handleDaily = async () => {
    if (!dailyAvailable || dailyClaiming) return
    setDailyClaiming(true)
    try {
      const res = await api.post('/coins/daily')
      updateUser({ coins: res.data.coins_total })
      setDailyAvailable(false)
      setDailyFlash(true)
      setTimeout(() => setDailyFlash(false), 2000)
    } catch {
      // déjà réclamé
    } finally {
      setDailyClaiming(false)
    }
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav className={`navbar ${scrolled ? 'navbar-scrolled' : ''}`}>

      {/* Ligne décorative top */}
      <div className="navbar-top-line" />

      {/* LOGO */}
      <div className="navbar-logo" onClick={() => navigate('/')}>
        <span className="logo-j">J</span>INXIT
        <span className="logo-dot" />
      </div>

      {/* NAV LINKS — centre */}
      <div className="navbar-links">
        <button className={`nav-link ${isActive('/') ? 'active' : ''}`} onClick={() => navigate('/')}>
          <span className="nav-link-icon">⚡</span>
          Live
          {isActive('/') && <span className="nav-link-indicator" />}
        </button>
        <button className={`nav-link ${isActive('/bets') ? 'active' : ''}`} onClick={() => navigate('/bets')}>
          <span className="nav-link-icon">🎯</span>
          Mes Paris
          {isActive('/bets') && <span className="nav-link-indicator" />}
        </button>
      </div>

      {/* RIGHT */}
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
              {dailyFlash && (
                <span className="daily-flash">+100 🪙</span>
              )}
            </div>

            {/* Coins */}
            <div className="navbar-coins" onClick={() => navigate('/profile')}>
              <div className="coins-icon">
                <span className="coins-icon-inner" />
              </div>
              <span className="coins-value">{user.coins?.toLocaleString() ?? '—'}</span>
              <span className="coins-label">coins</span>
            </div>

            {/* Avatar */}
            <div className="navbar-avatar-wrap" onClick={() => setMenuOpen(o => !o)}>
              <div className="navbar-avatar">
                {user.avatar_url
                  ? <img src={user.avatar_url} alt="avatar" referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                  : <span>{user.username?.slice(0, 2).toUpperCase()}</span>
                }
              </div>
              <div className="avatar-status" />
              <span className="navbar-username">{user.username}</span>
              <svg className={`avatar-chevron ${menuOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 12 15 18 9"/></svg>

              {/* Dropdown menu */}
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