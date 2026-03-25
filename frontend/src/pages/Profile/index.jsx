import './Profile.css'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

// ─── Helpers ────────────────────────────────────────────────

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3600000)
  const d = Math.floor(h / 24)
  const m = Math.floor(diff / 60000)
  if (d > 0) return `il y a ${d}j`
  if (h > 0) return `il y a ${h}h`
  if (m > 0) return `il y a ${m}m`
  return 'à l\'instant'
}

function timeUntil(dateStr) {
  if (!dateStr) return ''
  const diff = new Date(dateStr).getTime() + 86400000 - Date.now()
  if (diff <= 0) return null
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  return `${h}h ${m}m`
}

const TX_CONFIG = {
  signup_bonus:   { icon: '🎁', bg: '#c89b3c12', label: 'Bonus inscription' },
  daily_reward:   { icon: '📅', bg: '#00e5ff10', label: 'Récompense quotidienne' },
  bet_placed:     { icon: '🎯', bg: '#d946a810', label: 'Pari placé' },
  bet_won:        { icon: '✅', bg: '#22c55e10', label: 'Pari gagné' },
  bet_lost:       { icon: '❌', bg: '#ef444410', label: 'Pari perdu' },
  crate_purchase: { icon: '📦', bg: '#a78bfa10', label: 'Caisse achetée' },
}

const TIER_COLORS = {
  CHALLENGER: '#f4c430', GRANDMASTER: '#ef4444', MASTER: '#a78bfa',
  DIAMOND: '#378add', EMERALD: '#22c55e', PLATINUM: '#00e5ff',
  GOLD: '#c89b3c', SILVER: '#9ca3af', BRONZE: '#cd7f32', IRON: '#6b7280',
}

// ─── Composant compte Riot lié ──────────────────────────────

function RiotCard({ riotPlayer }) {
  const navigate = useNavigate()

  if (!riotPlayer) return null

  const { summoner_name, tag_line, region, tier, rank, lp, profile_icon_url } = riotPlayer
  const tierColor = TIER_COLORS[tier] || '#9ca3af'

  const goToPlayer = () =>
    navigate(`/player/${region}/${encodeURIComponent(summoner_name)}/${tag_line}`)

  return (
    <div className="pcard" style={{ animation: 'fade-up 0.5s 0.2s ease both' }}>
      <div className="pcard-label">Compte Riot</div>

      {/* Ligne principale : avatar + infos */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        {/* Avatar icône LoL */}
        <div style={{
          width: 52, height: 52, borderRadius: 10,
          background: '#1e1e1e', border: '1px solid #ffffff10',
          overflow: 'hidden', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {profile_icon_url
            ? <img src={profile_icon_url} alt="icon" style={{ width: '100%', height: '100%', objectFit: 'cover' }} referrerPolicy="no-referrer" />
            : <span style={{ fontSize: 22 }}>🎮</span>
          }
        </div>

        {/* Nom + tag + rang */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'Outfit', fontSize: 16, fontWeight: 700, color: '#e8eaf0' }}>
              {summoner_name}
            </span>
            <span style={{ fontFamily: 'Inter', fontSize: 12, color: '#4b5563', fontWeight: 400 }}>
              #{tag_line}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
            {tier && (
              <span style={{
                fontFamily: 'Inter', fontSize: 11, fontWeight: 600,
                color: tierColor,
                background: `${tierColor}15`,
                border: `1px solid ${tierColor}30`,
                borderRadius: 5, padding: '2px 7px',
              }}>
                {tier} {rank} · {lp} LP
              </span>
            )}
            <span style={{
              fontFamily: 'Inter', fontSize: 11, fontWeight: 500,
              color: '#6b7280', background: '#ffffff06',
              border: '1px solid #ffffff0d', borderRadius: 5, padding: '2px 7px',
            }}>
              {region}
            </span>
          </div>
        </div>
      </div>

      {/* Bouton vers la page joueur */}
      <button
        className="riot-view-btn"
        style={{ width: '100%', padding: '9px 0', textAlign: 'center' }}
        onClick={goToPlayer}
      >
        Voir ma page joueur →
      </button>
    </div>
  )
}

// ─── Page principale ─────────────────────────────────────────

export default function Profile() {
  const navigate  = useNavigate()
  const { user, updateCoins } = useAuthStore()

  const [profile, setProfile]         = useState(null)
  const [balance, setBalance]         = useState(null)
  const [transactions, setTransactions] = useState([])
  const [bets, setBets]               = useState([])
  const [loading, setLoading]         = useState(true)
  const [dailyLoading, setDailyLoading] = useState(false)
  const [coinPop, setCoinPop]         = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [profRes, balRes, txRes, betsRes] = await Promise.all([
        api.get('/profile/me'),
        api.get('/coins/balance'),
        api.get('/coins/history'),
        api.get('/bets/my-bets'),
      ])
      setProfile(profRes.data)
      setBalance(balRes.data)
      setTransactions(txRes.data)
      setBets(betsRes.data)
    } catch (e) {
      if (e.response?.status === 401) navigate('/login')
    } finally { setLoading(false) }
  }, [navigate])

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    fetchAll()
  }, [user, fetchAll])

  const claimDaily = async () => {
    setDailyLoading(true)
    try {
      const { data } = await api.post('/coins/daily')
      setCoinPop(true)
      setTimeout(() => setCoinPop(false), 700)
      updateCoins(data.coins_total)
      await fetchAll()
    } catch (err) {
      // déjà réclamé — on refresh juste le balance
      await fetchAll()
    } finally { setDailyLoading(false) }
  }

  // Stats paris
  const wonBets  = bets.filter(b => b.status === 'won').length
  const lostBets = bets.filter(b => b.status === 'lost').length
  const totalBets = bets.filter(b => b.status !== 'pending').length
  const winRate = totalBets > 0 ? Math.round((wonBets / totalBets) * 100) : 0
  const totalGains = bets.filter(b => b.status === 'won').reduce((acc, b) => acc + (b.payout || 0), 0)

  const remaining = balance?.last_daily ? timeUntil(balance.last_daily) : null
  const dailyAvailable = balance?.daily_disponible ?? true

  if (loading) return (
    <div className="profile-page">
      <div className="profile-spinner-wrap">
        <div className="profile-spinner" />
      </div>
    </div>
  )

  return (
    <div className="profile-page">

      {/* ── BANNER ── */}
      <div className="profile-banner">
        <div className="profile-banner-overlay" />
      </div>

      {/* ── HERO ── */}
      <div className="profile-hero">
        <div className="profile-avatar">
          {profile?.avatar_url
            ? <img src={profile.avatar_url} alt="avatar" />
            : user?.username?.slice(0, 2).toUpperCase()
          }
        </div>
        <div className="profile-hero-info">
          <div className="profile-username">
            {user?.username}
            {profile?.equipped_title && (
              <span className="profile-title-badge">✦ {profile.equipped_title}</span>
            )}
          </div>
          <div className="profile-meta">
            <span>Membre Jinxit</span>
            {profile?.riot_linked && (
              <span className="profile-riot-badge">
                <span className="profile-riot-dot" />
                Riot lié
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── LAYOUT 2 colonnes ── */}
      <div className="profile-layout">

        {/* ── COLONNE GAUCHE ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Coins + Daily */}
          <div className="pcard" style={{ animation: 'fade-up 0.5s 0.05s ease both' }}>
            <div className="pcard-label">Coins</div>
            <div className="coins-display">
              <div className="coins-icon">🪙</div>
              <div>
                <div className="coins-amount">{(balance?.coins ?? user?.coins ?? 0).toLocaleString()}</div>
                <div className="coins-label">coins disponibles</div>
              </div>
            </div>

            <div className="daily-btn-wrap">
              {coinPop && <span className="coin-pop">+100 🪙</span>}
              <button
                className={`daily-btn ${dailyAvailable ? 'available' : 'claimed'}`}
                onClick={dailyAvailable ? claimDaily : undefined}
                disabled={dailyLoading}
              >
                {dailyLoading
                  ? <><span style={{ width: 14, height: 14, border: '2px solid #1a191930', borderTopColor: '#1a1919', borderRadius: '50%', animation: 'spin 0.65s linear infinite', display: 'inline-block' }} /><span>Réclamation…</span></>
                  : dailyAvailable
                    ? <><span>🎁</span><span>Récupérer +100 coins</span></>
                    : <><span>✓</span><span>Daily réclamé</span></>
                }
              </button>
              {!dailyAvailable && remaining && (
                <div className="daily-countdown">Prochain daily dans {remaining}</div>
              )}
            </div>
          </div>

          {/* Stats paris */}
          <div className="pcard" style={{ animation: 'fade-up 0.5s 0.1s ease both' }}>
            <div className="pcard-label">Statistiques</div>
            <div className="profile-stats-grid">
              <div className="pstat">
                <div className="pstat-val" style={{ color: '#22c55e' }}>{winRate}%</div>
                <div className="pstat-lbl">Win rate</div>
              </div>
              <div className="pstat">
                <div className="pstat-val" style={{ color: '#00e5ff' }}>{wonBets}</div>
                <div className="pstat-lbl">Paris gagnés</div>
              </div>
              <div className="pstat">
                <div className="pstat-val" style={{ color: '#d946a8' }}>{bets.filter(b=>b.status==='pending').length}</div>
                <div className="pstat-lbl">En cours</div>
              </div>
              <div className="pstat">
                <div className="pstat-val" style={{ color: '#c89b3c' }}>{totalGains.toLocaleString()}</div>
                <div className="pstat-lbl">Coins gagnés</div>
              </div>
            </div>
          </div>

          {/* Riot link */}
          {profile?.riot_player && <RiotCard riotPlayer={profile.riot_player} />}

        </div>

        {/* ── COLONNE DROITE ── */}
        <div className="profile-right">

          {/* Historique transactions */}
          <div className="pcard">
            <div className="section-label-sm">Historique des coins</div>
            {transactions.length === 0 ? (
              <div className="empty-state">Aucune transaction pour l'instant.</div>
            ) : (
              <div className="tx-list">
                {transactions.slice(0, 20).map((tx, i) => {
                  const cfg = TX_CONFIG[tx.type] || { icon: '💰', bg: '#ffffff08', label: tx.type }
                  const isPos = tx.amount > 0
                  return (
                    <div className="tx-row" key={i}>
                      <div className="tx-icon" style={{ background: cfg.bg }}>{cfg.icon}</div>
                      <div className="tx-body">
                        <div className="tx-desc">{tx.description || cfg.label}</div>
                        <div className="tx-date">{timeAgo(tx.created_at)}</div>
                      </div>
                      <div className={`tx-amount ${isPos ? 'tx-pos' : 'tx-neg'}`}>
                        {isPos ? '+' : ''}{tx.amount.toLocaleString()}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Derniers paris */}
          {bets.length > 0 && (
            <div className="pcard">
              <div className="section-label-sm" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Derniers paris</span>
                <button
                  onClick={() => navigate('/bets')}
                  style={{ background: 'transparent', border: 'none', fontFamily: 'Inter', fontSize: 12, color: '#6b7280', cursor: 'pointer', transition: 'color 0.2s' }}
                  onMouseEnter={e => e.target.style.color = '#9ca3af'}
                  onMouseLeave={e => e.target.style.color = '#6b7280'}
                >
                  Voir tout →
                </button>
              </div>
              <div className="tx-list">
                {bets.slice(0, 5).map((bet, i) => {
                  const statusColor = { won: '#22c55e', lost: '#ef4444', pending: '#f59e0b', cancelled: '#6b7280' }
                  const statusIcon  = { won: '✅', lost: '❌', pending: '⏳', cancelled: '↩' }
                  const statusLabel = { won: 'Gagné', lost: 'Perdu', pending: 'En cours', cancelled: 'Annulé' }
                  return (
                    <div className="tx-row" key={i}>
                      <div className="tx-icon" style={{ background: `${statusColor[bet.status]}12`, fontSize: 16 }}>
                        {statusIcon[bet.status]}
                      </div>
                      <div className="tx-body">
                        <div className="tx-desc" style={{ textTransform: 'capitalize' }}>
                          {bet.bet_type?.replace(/_/g, ' ')} — {bet.bet_value}
                        </div>
                        <div className="tx-date">
                          <span style={{ color: statusColor[bet.status], fontWeight: 500 }}>
                            {statusLabel[bet.status]}
                          </span>
                          {' · '}{bet.amount.toLocaleString()} coins misés
                          {bet.status === 'won' && bet.payout ? ` · +${bet.payout.toLocaleString()} récupérés` : ''}
                        </div>
                      </div>
                      <div className={`tx-amount ${bet.status === 'won' ? 'tx-pos' : bet.status === 'lost' ? 'tx-neg' : ''}`}
                        style={{ color: statusColor[bet.status] }}>
                        {bet.status === 'won' ? `+${bet.payout?.toLocaleString()}` :
                         bet.status === 'lost' ? `-${bet.amount?.toLocaleString()}` :
                         `${bet.amount?.toLocaleString()}`}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}