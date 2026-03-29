import './Leaderboard.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

const MEDALS = ['🥇', '🥈', '🥉']

const RANK_COLORS = {
  1: { color: '#f4c430', glow: '#f4c43030', border: '#f4c43040' },
  2: { color: '#9ca3af', glow: '#9ca3af20', border: '#9ca3af30' },
  3: { color: '#cd7f32', glow: '#cd7f3220', border: '#cd7f3230' },
}

export default function Leaderboard() {
  const navigate        = useNavigate()
  const { user }        = useAuthStore()
  const [players, setPlayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [userRank, setUserRank] = useState(null)

  useEffect(() => {
    api.get('/leaderboard')
      .then(r => {
        setPlayers(r.data)
        if (user) {
          const found = r.data.find(p => p.id === user.id)
          if (found) setUserRank(found.rank)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="lb-page">
      <div className="lb-loading">
        <div className="lb-spinner" />
        <div className="lb-loading-text">Chargement du classement...</div>
      </div>
    </div>
  )

  const top3   = players.slice(0, 3)
  const rest   = players.slice(3)

  return (
    <div className="lb-page">

      {/* ── GLOWS ── */}
      <div className="lb-glow lb-glow-1" />
      <div className="lb-glow lb-glow-2" />
      <div className="lb-glow lb-glow-3" />

      {/* ── HERO ── */}
      <div className="lb-hero">
        <div className="lb-eyebrow">Classement global · Jinxit</div>
        <h1 className="lb-title">
          Les meilleurs<br />
          <span className="lb-accent">parieurs</span>
        </h1>
        <p className="lb-sub">Top 50 des joueurs avec le plus de coins</p>
        {user && userRank && (
          <div className="lb-my-rank">
            <span className="lb-my-rank-label">Ta position</span>
            <span className="lb-my-rank-value">#{userRank}</span>
          </div>
        )}
      </div>

      {/* ── PODIUM TOP 3 ── */}
      {top3.length > 0 && (
        <div className="lb-podium">
          {/* 2ème */}
          {top3[1] && (
            <div className="lb-podium-card lb-podium-2" style={{ animationDelay: '0.1s' }}>
              <div className="lb-podium-medal">🥈</div>
              <div className="lb-podium-avatar" style={{ borderColor: RANK_COLORS[2].border, boxShadow: `0 0 20px ${RANK_COLORS[2].glow}` }}>
                {top3[1].avatar_url
                  ? <img src={top3[1].avatar_url} alt={top3[1].username} referrerPolicy="no-referrer" />
                  : <span>{top3[1].username?.slice(0, 2).toUpperCase()}</span>
                }
              </div>
              <div className="lb-podium-name">{top3[1].username}</div>
              <div className="lb-podium-coins" style={{ color: RANK_COLORS[2].color }}>
                {top3[1].coins?.toLocaleString()}
                <span className="lb-coin-dot" style={{ background: RANK_COLORS[2].color }} />
              </div>
              <div className="lb-podium-bar lb-podium-bar-2" />
            </div>
          )}

          {/* 1er */}
          {top3[0] && (
            <div className="lb-podium-card lb-podium-1" style={{ animationDelay: '0s' }}>
              <div className="lb-podium-crown">👑</div>
              <div className="lb-podium-medal">🥇</div>
              <div className="lb-podium-avatar lb-podium-avatar-1" style={{ borderColor: RANK_COLORS[1].border, boxShadow: `0 0 32px ${RANK_COLORS[1].glow}` }}>
                {top3[0].avatar_url
                  ? <img src={top3[0].avatar_url} alt={top3[0].username} referrerPolicy="no-referrer" />
                  : <span>{top3[0].username?.slice(0, 2).toUpperCase()}</span>
                }
              </div>
              <div className="lb-podium-name lb-podium-name-1">{top3[0].username}</div>
              <div className="lb-podium-coins" style={{ color: RANK_COLORS[1].color }}>
                {top3[0].coins?.toLocaleString()}
                <span className="lb-coin-dot" style={{ background: RANK_COLORS[1].color }} />
              </div>
              <div className="lb-podium-bar lb-podium-bar-1" />
            </div>
          )}

          {/* 3ème */}
          {top3[2] && (
            <div className="lb-podium-card lb-podium-3" style={{ animationDelay: '0.2s' }}>
              <div className="lb-podium-medal">🥉</div>
              <div className="lb-podium-avatar" style={{ borderColor: RANK_COLORS[3].border, boxShadow: `0 0 20px ${RANK_COLORS[3].glow}` }}>
                {top3[2].avatar_url
                  ? <img src={top3[2].avatar_url} alt={top3[2].username} referrerPolicy="no-referrer" />
                  : <span>{top3[2].username?.slice(0, 2).toUpperCase()}</span>
                }
              </div>
              <div className="lb-podium-name">{top3[2].username}</div>
              <div className="lb-podium-coins" style={{ color: RANK_COLORS[3].color }}>
                {top3[2].coins?.toLocaleString()}
                <span className="lb-coin-dot" style={{ background: RANK_COLORS[3].color }} />
              </div>
              <div className="lb-podium-bar lb-podium-bar-3" />
            </div>
          )}
        </div>
      )}

      {/* ── LISTE 4-50 ── */}
      {rest.length > 0 && (
        <div className="lb-list-wrap">
          <div className="lb-list">
            {rest.map((p, i) => {
              const isMe = user && p.id === user.id
              return (
                <div
                  key={p.id}
                  className={`lb-row ${isMe ? 'lb-row--me' : ''}`}
                  style={{ animationDelay: `${(i * 0.03).toFixed(2)}s` }}
                >
                  <div className="lb-row-rank">#{p.rank}</div>

                  <div className="lb-row-avatar">
                    {p.avatar_url
                      ? <img src={p.avatar_url} alt={p.username} referrerPolicy="no-referrer" />
                      : <span>{p.username?.slice(0, 2).toUpperCase()}</span>
                    }
                  </div>

                  <div className="lb-row-name">
                    {p.username}
                    {isMe && <span className="lb-me-tag">Toi</span>}
                  </div>

                  <div className="lb-row-bar-wrap">
                    <div
                      className="lb-row-bar"
                      style={{ width: `${Math.round((p.coins / players[0].coins) * 100)}%` }}
                    />
                  </div>

                  <div className="lb-row-coins">
                    {p.coins?.toLocaleString()}
                    <span className="lb-coin-dot" />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

    </div>
  )
}