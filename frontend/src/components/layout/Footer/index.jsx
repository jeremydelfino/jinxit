import { useNavigate } from 'react-router-dom'
import './Footer.css'

/* ══════════════════════════════════════
   ICÔNES — SVG line (stroke = currentColor)
══════════════════════════════════════ */
const Icon = ({ d, size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
)

const ICONS = {
  live:     <><circle cx="12" cy="12" r="3"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14M19.07 4.93a10 10 0 0 1 0 14.14M7.76 7.76a6 6 0 0 0 0 8.48M16.24 7.76a6 6 0 0 1 0 8.48"/></>,
  leagues:  <><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22M18 2H6v7a6 6 0 0 0 12 0V2Z"/></>,
  games:    <><line x1="6" y1="11" x2="10" y2="11"/><line x1="8" y1="9" x2="8" y2="13"/><line x1="15" y1="12" x2="15.01" y2="12"/><line x1="18" y1="10" x2="18.01" y2="10"/><rect x="2" y="6" width="20" height="12" rx="2"/></>,
  bets:     <><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></>,
  ranking:  <><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></>,
  user:     <><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
  login:    <><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></>,
  register: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></>,
}

const LINKS = {
  platform: [
    { label: 'Live',        path: '/',            key: 'live' },
    { label: 'Ligues Pros', path: '/betonpros',   key: 'leagues' },
    { label: 'Jeux',        path: '/games',       key: 'games' },
    { label: 'Mes Prédictions',   path: '/bets',        key: 'bets' },
    { label: 'Classement',  path: '/leaderboard', key: 'ranking' },
  ],
  account: [
    { label: 'Mon Profil',  path: '/profile',  key: 'user' },
    { label: 'Connexion',   path: '/login',    key: 'login' },
    { label: 'S\'inscrire', path: '/register', key: 'register' },
  ],
}

const SOCIALS = [
  { label: 'Twitter / X', href: 'https://x.com/JungleGap_FR', icon: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.259 5.63L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  )},
  { label: 'Discord',    href: '#', icon: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
    </svg>
  )},
]

export default function Footer() {
  const navigate = useNavigate()

  return (
    <footer className="footer">

      {/* ─── AMBIENT GLOW ─── */}
      <div className="footer-glow footer-glow-green" />
      <div className="footer-glow footer-glow-gold" />

      {/* ─── SEPARATOR ─── */}
      <div className="footer-sep">
        <div className="footer-sep-line" />
        <span className="footer-sep-dot" />
        <div className="footer-sep-line" />
      </div>

      {/* ─── MAIN GRID ─── */}
      <div className="footer-inner">

        {/* ── BRAND COL ── */}
        <div className="footer-brand">
          <div className="footer-logo" onClick={() => navigate('/')}>
            <span className="footer-logo-j">J</span>UNGLEGAP
            <span className="footer-logo-beta">BETA</span>
            <span className="footer-logo-dot" />
          </div>
          <p className="footer-tagline">
            Le seul endroit où la <span className="footer-tagline-accent">Jungle Gap</span><br/>
            se transforme en réussite.
          </p>

          <div className="footer-coverage">
            <span className="footer-coverage-label">Couverture</span>
            <span className="footer-coverage-leagues">LCK · LEC · LFL</span>
          </div>

          <div className="footer-socials">
            {SOCIALS.map(s => (
              <a key={s.label} href={s.href} className="footer-social-btn" title={s.label} target="_blank" rel="noopener noreferrer">
                {s.icon}
              </a>
            ))}
          </div>
        </div>

        {/* ── PLATFORM LINKS ── */}
        <div className="footer-col">
          <div className="footer-col-title">
            <span className="footer-col-title-line" />
            Plateforme
          </div>
          <div className="footer-links">
            {LINKS.platform.map(l => (
              <button key={l.path} className="footer-link" onClick={() => navigate(l.path)}>
                <span className="footer-link-icon"><Icon d={ICONS[l.key]} /></span>
                {l.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── ACCOUNT LINKS ── */}
        <div className="footer-col">
          <div className="footer-col-title">
            <span className="footer-col-title-line" />
            Compte
          </div>
          <div className="footer-links">
            {LINKS.account.map(l => (
              <button key={l.path} className="footer-link" onClick={() => navigate(l.path)}>
                <span className="footer-link-icon"><Icon d={ICONS[l.key]} /></span>
                {l.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── DISCLAIMER ── */}
        <div className="footer-col footer-col-disclaimer">
          <div className="footer-col-title">
            <span className="footer-col-title-line" />
            À propos
          </div>
          <p className="footer-disclaimer">
            Jungle Gap est une plateforme d'amusement, de fun — Conçu pour les fans de LoL et d'Esports. Aucun argent réel n'est impliqué.
          </p>
          <div className="footer-riot-badge">
            <span className="footer-riot-dot" />
            <span>Propulsé par Riot Games API</span>
          </div>
          <div className="footer-riot-badge" style={{ marginTop: 6 }}>
            <span className="footer-riot-dot footer-riot-dot-gold" />
            <span>Données live · Côtes dynamiques</span>
          </div>
        </div>

      </div>

      {/* ─── BOTTOM BAR ─── */}
      <div className="footer-bottom">
        <div className="footer-bottom-inner">
          <div className="footer-bottom-logo">
            <span className="footer-bottom-j">J</span>G
          </div>
          <span className="footer-copyright">
            © 2026 Jungle Gap · Plateforme pour la communauté League of Legends France. Tous droits réservés.
          </span>
          <div className="footer-bottom-links">
            <button className="footer-bottom-link">Mentions légales</button>
            <span className="footer-bottom-sep">·</span>
            <button className="footer-bottom-link">Confidentialité</button>
          </div>
        </div>
      </div>

    </footer>
  )
}