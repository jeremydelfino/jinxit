import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import './AdminRatings.css'

const LEAGUE_MAP = {
  T1:'LCK', GEN:'LCK', HLE:'LCK', KT:'LCK', DK:'LCK', NS:'LCK', KRX:'LCK', BFX:'LCK', DNS:'LCK', BRO:'LCK',
  G2:'LEC', FNC:'LEC', KC:'LEC', VIT:'LEC', TH:'LEC', GX:'LEC', MKOI:'LEC', SK:'LEC', NAVI:'LEC', SHFT:'LEC', LR:'LEC', KCB:'LEC',
  VITB:'LFL', SLY:'LFL', GW:'LFL', IJC:'LFL', JL:'LFL', ZPR:'LFL', TLNP:'LFL', GL:'LFL', BKR:'LFL', FK:'LFL', SC:'LFL', LIL:'LFL',
}

const LEAGUE_COLOR = { LCK: '#0bc4f5', LEC: '#9b59f5', LFL: '#65BD62' }

function boostMeta(v) {
  const n = parseFloat(v)
  if (n >= 1.5) return { label: '🔥 Hyped',   color: '#65BD62' }
  if (n >  1.0) return { label: '↑ Favori',   color: '#a3d977' }
  if (n === 1.0) return { label: '— Neutre',  color: '#6b7280' }
  if (n >= 0.7) return { label: '↓ Outsider', color: '#f59e0b' }
  return               { label: '💀 Underdog', color: '#ef4444' }
}

export default function AdminRatings() {
  const { user }    = useAuthStore()
  const navigate    = useNavigate()

  const [ratings, setRatings] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [form,    setForm]    = useState({ manual_boost: 1.0, notes: '' })
  const [saving,  setSaving]  = useState(false)
  const [msg,     setMsg]     = useState(null)
  const [league,  setLeague]  = useState('ALL')

  useEffect(() => {
    if (!user?.is_admin) { navigate('/'); return }
    load()
  }, [])

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/esports/admin/ratings')
      setRatings(Array.isArray(data) ? data : [])
    } catch (e) {
      setMsg({ type: 'error', text: 'Erreur de chargement' })
      setRatings([])
    } finally {
      setLoading(false)
    }
  }

  function startEdit(r) {
    setEditing(r.team_code)
    setForm({ manual_boost: r.manual_boost, notes: r.notes || '' })
    setMsg(null)
  }

  async function save() {
    setSaving(true)
    setMsg(null)
    try {
      await api.post(`/esports/admin/ratings/${editing}`, {
        manual_boost: parseFloat(form.manual_boost),
        notes:        form.notes || null,
      })
      setMsg({ type: 'success', text: `✓ ${editing} mis à jour` })
      setEditing(null)
      load()
    } catch (e) {
      const d = e.response?.data?.detail
      setMsg({ type: 'error', text: typeof d === 'string' ? d : 'Erreur' })
    } finally {
      setSaving(false)
    }
  }

  const LEAGUES  = ['ALL', 'LCK', 'LEC', 'LFL']
  const filtered = ratings.filter(r => league === 'ALL' || LEAGUE_MAP[r.team_code] === league)

  return (
    <div className="ar-page">

      {/* ── HEADER ── */}
      <div className="ar-header">
        <div>
          <h1 className="ar-title">⚡ Ratings & Boosts</h1>
          <p className="ar-sub">Influence les côtes en ajustant la hype de chaque équipe</p>
        </div>
        <span className="ar-count">{ratings.length} équipes</span>
      </div>

      {/* ── TOOLBAR ── */}
      <div className="ar-toolbar">
        <div className="ar-filters">
          {LEAGUES.map(l => (
            <button
              key={l}
              className={`ar-filter ${league === l ? 'active' : ''}`}
              style={league === l && l !== 'ALL'
                ? { borderColor: LEAGUE_COLOR[l], color: LEAGUE_COLOR[l], background: LEAGUE_COLOR[l] + '18' }
                : {}}
              onClick={() => setLeague(l)}
            >
              {l}
            </button>
          ))}
        </div>
        {msg && !editing && <div className={`ar-msg ${msg.type}`}>{msg.text}</div>}
      </div>

      {/* ── CONTENU ── */}
      {loading ? (
        <div className="ar-loading">Chargement...</div>
      ) : filtered.length === 0 ? (
        <div className="ar-empty">Aucune équipe trouvée.</div>
      ) : (
        <div className="ar-grid">
          {filtered.map(r => {
            const lc   = LEAGUE_COLOR[LEAGUE_MAP[r.team_code]] || '#6b7280'
            const meta = boostMeta(r.manual_boost)
            const isEd = editing === r.team_code

            return (
              <div
                key={r.team_code}
                className={`ar-card ${isEd ? 'editing' : ''}`}
                style={{ '--lc': lc, '--bc': meta.color }}
              >
                {/* Top */}
                <div className="ar-card-top">
                  <div className="ar-card-id">
                    <span className="ar-dot" />
                    <span className="ar-league">{LEAGUE_MAP[r.team_code] || '?'}</span>
                    <span className="ar-code">{r.team_code}</span>
                  </div>
                  <span className="ar-pill">{meta.label}</span>
                </div>

                {/* Vue lecture */}
                {!isEd ? (
                  <>
                    <div className="ar-boost-display">
                      <span className="ar-boost-num" style={{ color: meta.color }}>
                        ×{parseFloat(r.manual_boost).toFixed(2)}
                      </span>
                      <div className="ar-boost-bar">
                        <div
                          className="ar-boost-fill"
                          style={{
                            width:      `${Math.min(((r.manual_boost - 0.1) / 2.9) * 100, 100)}%`,
                            background: meta.color,
                          }}
                        />
                      </div>
                    </div>
                    {r.notes && <p className="ar-notes">"{r.notes}"</p>}
                    <button className="ar-btn-edit" onClick={() => startEdit(r)}>
                      Modifier
                    </button>
                  </>
                ) : (
                  /* Vue édition */
                  <div className="ar-edit-form">
                    <label className="ar-label">
                      Boost&nbsp;
                      <span style={{ color: meta.color }}>
                        ×{parseFloat(form.manual_boost).toFixed(2)}
                      </span>
                    </label>
                    <input
                      type="range" min="0.1" max="3.0" step="0.05"
                      value={form.manual_boost}
                      onChange={e => setForm(f => ({ ...f, manual_boost: e.target.value }))}
                      className="ar-range"
                      style={{ '--fill': meta.color }}
                    />
                    <div className="ar-range-labels">
                      <span>0.1 💀</span><span>1.0</span><span>3.0 🔥</span>
                    </div>
                    <input
                      className="ar-input"
                      placeholder="Note (optionnel)"
                      value={form.notes}
                      onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                    />
                    <div className="ar-edit-actions">
                      <button className="ar-btn-cancel" onClick={() => setEditing(null)}>
                        Annuler
                      </button>
                      <button className="ar-btn-save" onClick={save} disabled={saving}>
                        {saving ? '...' : 'Sauvegarder'}
                      </button>
                    </div>
                    {msg && <div className={`ar-msg ${msg.type}`}>{msg.text}</div>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}