import './Game.css'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'

function formatDuration(s) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function Game() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, updateCoins } = useAuthStore()

  const [game,       setGame]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [champMap,   setChampMap]   = useState({})
  const [selections, setSelections] = useState({})
  const [amount,     setAmount]     = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [betDone,    setBetDone]    = useState(null)
  const [betError,   setBetError]   = useState(null)

  // Charger la map championId → championName
  useEffect(() => {
    fetch('https://ddragon.leagueoflegends.com/cdn/14.24.1/data/en_US/champion.json')
      .then(r => r.json())
      .then(data => {
        const map = {}
        Object.values(data.data).forEach(c => {
          map[parseInt(c.key)] = c.id
        })
        setChampMap(map)
      })
      .catch(() => {})
  }, [])

  // Charger la game
  useEffect(() => {
    api.get(`/games/${id}`)
      .then(r => setGame(r.data))
      .catch(() => setError('Partie introuvable ou terminée'))
      .finally(() => setLoading(false))
  }, [id])

  // Refresh durée toutes les 30s
  useEffect(() => {
    if (!game) return
    const iv = setInterval(() => {
      api.get(`/games/${id}`)
        .then(r => setGame(r.data))
        .catch(() => {})
    }, 30000)
    return () => clearInterval(iv)
  }, [game])

  const getChampName = (p) => p.championName || champMap[p.championId] || '???'
  const getChampIcon = (p) => {
    const name = getChampName(p)
    if (!name || name === '???') return null
    return `https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/${name}.png`
  }
  const getPlayerName = (p) => p.summonerName || p.riotIdGameName || '—'

  const toggleSelection = (type, value) => {
    if (!game?.bets_open) return
    setSelections(prev => {
      if (prev[type] === value) {
        const next = { ...prev }
        delete next[type]
        return next
      }
      return { ...prev, [type]: value }
    })
  }

  const selectionList = Object.entries(selections).map(([type, value]) => ({ type, value }))
  const odds = Math.pow(2, selectionList.length)
  const potentialGain = amount ? Math.floor(parseInt(amount) * odds) : 0

  const handleBet = async () => {
    if (!selectionList.length) { setBetError('Choisis au moins une sélection'); return }
    if (!amount || parseInt(amount) <= 0) { setBetError('Montant invalide'); return }
    if (!user) { navigate('/login'); return }
    setSubmitting(true)
    setBetError(null)
    try {
      const res = await api.post('/bets/place', {
        live_game_id: game.id,
        selections: selectionList,
        amount: parseInt(amount),
      })
      setBetDone(res.data)
      updateCoins(res.data.new_balance)
      setSelections({})
      setAmount('')
    } catch (err) {
      setBetError(err.response?.data?.detail || 'Erreur lors du pari')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return (
    <div className="game-page">
      <div className="game-loading">
        <div className="game-spinner" />
        <span>Chargement de la partie...</span>
      </div>
    </div>
  )

  if (error) return (
    <div className="game-page">
      <div className="game-error">
        <div className="game-error-title">Partie introuvable</div>
        <div className="game-error-sub">{error}</div>
        <button className="game-back-btn" onClick={() => navigate('/')}>← Retour à l'accueil</button>
      </div>
    </div>
  )

  const { blue_team, red_team, bets_open, duration_seconds, queue, pro } = game
  const allChampions = [...blue_team, ...red_team].map(p => getChampName(p)).filter(n => n !== '???')

  return (
    <div className="game-page">

      {/* ── BANNER ── */}
      <div className="game-banner" style={{
        background: pro
          ? `linear-gradient(135deg, ${pro.accent_color}20, #1a1919 60%)`
          : 'linear-gradient(135deg, #00e5ff08, #1a1919 60%)'
      }}>
        {pro?.team_logo_url && (
          <img className="game-banner-logo" src={pro.team_logo_url} alt="" referrerPolicy="no-referrer" />
        )}
        <div className="game-banner-overlay" />
      </div>

      {/* ── HEADER ── */}
      <div className="game-header">
        <button className="game-back-btn" onClick={() => navigate('/')}>← Retour</button>
        <div className="game-header-center">
          <div className="game-live-badge">
            <span className="live-dot" />
            LIVE
          </div>
          <div className="game-queue">{queue}</div>
          <div className="game-timer">{formatDuration(duration_seconds)}</div>
        </div>
        {!bets_open
          ? <div className="bets-closed-badge">🔒 Paris fermés</div>
          : <div className="bets-open-badge">✓ Paris ouverts</div>
        }
      </div>

      {/* ── MAIN LAYOUT ── */}
      <div className="game-layout">

        {/* ══ DRAFT ══ */}
        <div className="draft-wrapper">

          {/* BLUE SIDE */}
          <div className="draft-side">
            <div className="side-header blue">
              <span className="side-bar blue-bar" />
              BLUE SIDE
            </div>
            <div className="draft-champs">
              {blue_team.map((p, i) => (
                <div key={i} className="draft-champ blue-champ">
                  <div className="champ-portrait-wrap blue-accent">
                    {getChampIcon(p)
                      ? <img src={getChampIcon(p)} alt={getChampName(p)} className="champ-portrait-img" onError={e => { e.target.style.display = 'none' }} />
                      : <div className="champ-portrait-fallback">{getChampName(p).slice(0, 2)}</div>
                    }
                    <div className="champ-portrait-shine" />
                  </div>
                  <div className="champ-info">
                    <div className="champ-info-name">{getChampName(p)}</div>
                    <div className="champ-info-player">{getPlayerName(p)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CENTER */}
          <div className="draft-center">
            <div className="draft-vs">VS</div>
          </div>

          {/* RED SIDE */}
          <div className="draft-side red-side">
            <div className="side-header red">
              <span className="side-bar red-bar" />
              RED SIDE
            </div>
            <div className="draft-champs">
              {red_team.map((p, i) => (
                <div key={i} className="draft-champ red-champ">
                  <div className="champ-info red-info">
                    <div className="champ-info-name">{getChampName(p)}</div>
                    <div className="champ-info-player">{getPlayerName(p)}</div>
                  </div>
                  <div className="champ-portrait-wrap red-accent">
                    {getChampIcon(p)
                      ? <img src={getChampIcon(p)} alt={getChampName(p)} className="champ-portrait-img" onError={e => { e.target.style.display = 'none' }} />
                      : <div className="champ-portrait-fallback">{getChampName(p).slice(0, 2)}</div>
                    }
                    <div className="champ-portrait-shine" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ══ BET SLIP ══ */}
        <div className="bet-panel">

          {/* Victoire */}
          <div className="bet-block">
            <div className="bet-block-title">
              🏆 Victoire
              <span className="bet-cote">x2</span>
            </div>
            <div className="bet-options-row">
              <button
                className={`bet-opt blue-opt ${selections.who_wins === 'blue' ? 'selected' : ''}`}
                onClick={() => toggleSelection('who_wins', 'blue')}
                disabled={!bets_open}
              >
                <span className="opt-dot blue-dot" />
                Blue side
              </button>
              <button
                className={`bet-opt red-opt ${selections.who_wins === 'red' ? 'selected' : ''}`}
                onClick={() => toggleSelection('who_wins', 'red')}
                disabled={!bets_open}
              >
                <span className="opt-dot red-dot" />
                Red side
              </button>
            </div>
          </div>

          {/* First Blood */}
          <div className="bet-block">
            <div className="bet-block-title">
              🩸 First Blood
              <span className="bet-cote">x2</span>
            </div>
            <select
              className="bet-select"
              value={selections.first_blood || ''}
              onChange={e => {
                if (!bets_open) return
                const val = e.target.value
                if (!val) {
                  setSelections(prev => { const n = { ...prev }; delete n.first_blood; return n })
                } else {
                  setSelections(prev => ({ ...prev, first_blood: val }))
                }
              }}
              disabled={!bets_open}
            >
              <option value="">— Choisir un champion —</option>
              <optgroup label="Blue side">
                {blue_team.map((p, i) => (
                  <option key={i} value={getChampName(p)}>{getChampName(p)} ({getPlayerName(p)})</option>
                ))}
              </optgroup>
              <optgroup label="Red side">
                {red_team.map((p, i) => (
                  <option key={i} value={getChampName(p)}>{getChampName(p)} ({getPlayerName(p)})</option>
                ))}
              </optgroup>
            </select>
          </div>

          {/* Récap combiné */}
          <div className="bet-slip">
            <div className="slip-header">
              <span className="slip-title">Mon pari</span>
              {selectionList.length > 0 && (
                <span className="slip-count">{selectionList.length} sélection{selectionList.length > 1 ? 's' : ''}</span>
              )}
            </div>

            {selectionList.length === 0 ? (
              <div className="slip-empty">Aucune sélection</div>
            ) : (
              <div className="slip-rows">
                {selectionList.map((s, i) => (
                  <div key={i} className="slip-row">
                    <span className="slip-label">
                      {s.type === 'who_wins' ? '🏆 Victoire' : '🩸 First Blood'}
                    </span>
                    <span className="slip-val" style={{
                      color: s.value === 'blue' ? '#378add' : s.value === 'red' ? '#ef4444' : '#00e5ff'
                    }}>
                      {s.value}
                    </span>
                    <span className="slip-odd">x2</span>
                  </div>
                ))}
                <div className="slip-total-row">
                  <span>Cote totale</span>
                  <span className="slip-total-odds">x{odds.toFixed(1)}</span>
                </div>
              </div>
            )}

            {/* Montant */}
            <div className="slip-amount-wrap">
              <input
                className="slip-amount-input"
                type="number"
                min="1"
                placeholder="Mise en coins..."
                value={amount}
                onChange={e => setAmount(e.target.value)}
                disabled={!bets_open}
              />
              <div className="slip-presets">
                {[100, 500, 1000].map(v => (
                  <button key={v} className="preset-btn" onClick={() => setAmount(String(v))} disabled={!bets_open}>{v}</button>
                ))}
                <button className="preset-btn" onClick={() => setAmount(String(user?.coins || 0))} disabled={!bets_open}>MAX</button>
              </div>
            </div>

            {potentialGain > 0 && (
              <div className="slip-gain">
                Gain potentiel : <strong>{potentialGain.toLocaleString()} coins</strong>
              </div>
            )}

            {/* Carte bonus — placeholder */}
            <div className="slip-card-slot">
              <span>🃏</span>
              <span className="card-slot-txt">Carte bonus</span>
              <span className="card-slot-soon">Bientôt</span>
            </div>

            {betError && <div className="slip-error">{betError}</div>}
            {betDone && <div className="slip-success">✓ Pari placé ! Gain potentiel : {betDone.potential_gain?.toLocaleString()} coins</div>}

            <button
              className="btn-place-bet"
              onClick={handleBet}
              disabled={!bets_open || submitting || !selectionList.length || !amount}
            >
              {!bets_open
                ? '🔒 Paris fermés'
                : submitting
                  ? 'Placement...'
                  : `Parier ${amount ? parseInt(amount).toLocaleString() : '—'} coins`
              }
            </button>

            {user && <div className="slip-balance">Solde : {user.coins?.toLocaleString()} coins</div>}
          </div>
        </div>
      </div>
    </div>
  )
}