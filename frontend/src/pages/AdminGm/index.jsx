import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import GmCard from '../../components/ui/GmCard'
import './AdminGm.css'

const ROLES = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']
const LEAGUES = ['LFL', 'LEC', 'LCK', 'LCS', 'LPL']

// Miroir exact de backend/services/gm_ovr.py — preview live
const ROLE_WEIGHTS = {
  TOP:     { laning: 25, teamfight: 25, mechanics: 20, vision: 12, stress: 8, clutch: 10 },
  JUNGLE:  { laning: 18, teamfight: 21, mechanics: 21, vision: 22, stress: 8, clutch: 10 },
  MID:     { laning: 20, teamfight: 20, mechanics: 25, vision: 17, stress: 8, clutch: 10 },
  ADC:     { laning: 20, teamfight: 25, mechanics: 29, vision:  8, stress: 8, clutch: 10 },
  SUPPORT: { laning: 15, teamfight: 25, mechanics: 12, vision: 30, stress: 8, clutch: 10 },
}

function computeOvr(role, s) {
  const w = ROLE_WEIGHTS[(role || '').toUpperCase()] || ROLE_WEIGHTS.MID
  const total = s.laning * w.laning + s.teamfight * w.teamfight + s.vision * w.vision
    + s.mechanics * w.mechanics + s.stress * w.stress + s.clutch * w.clutch
  return Math.round(total / 100)
}

function salaryFromOvr(ovr) {
  return Math.round(20 * Math.pow(1.10, Math.max(0, ovr - 60)))
}

const STAT_DEFS = [
  ['laning', 'Laning'],
  ['teamfight', 'Teamfight'],
  ['mechanics', 'Mécaniques'],
  ['vision', 'Vision'],
  ['stress', 'Sang-froid'],
  ['clutch', 'Clutch'],
]

function statColor(v) {
  if (v >= 90) return '#c89b3c'
  if (v >= 80) return '#65BD62'
  if (v >= 70) return '#d1d5db'
  return '#9b6b6b'
}

const EMPTY_STATS = { laning: 70, teamfight: 70, vision: 70, mechanics: 70, stress: 70, clutch: 70 }

export default function AdminGm() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const [cards, setCards]     = useState([])
  const [loading, setLoading] = useState(true)
  const [league, setLeague]   = useState('LFL')
  const [search, setSearch]   = useState('')
  const [selId, setSelId]     = useState(null)
  const [draft, setDraft]     = useState(null)
  const [saving, setSaving]   = useState(false)
  const [msg, setMsg]         = useState(null)

  useEffect(() => {
    if (!user?.is_admin) { navigate('/'); return }
    load(league)
    // eslint-disable-next-line
  }, [])

  async function load(lg) {
    setLoading(true)
    try {
      const { data } = await api.get('/gm/admin/cards', { params: lg ? { league: lg } : {} })
      setCards(Array.isArray(data) ? data : [])
    } catch (e) {
      setMsg({ type: 'error', text: 'Erreur de chargement' })
      setCards([])
    } finally {
      setLoading(false)
    }
  }

  function pickLeague(lg) {
    setLeague(lg); setSelId(null); setDraft(null); setMsg(null)
    load(lg)
  }

  function selectCard(c) {
    setSelId(c.card_id)
    setDraft({
      role:        c.role,
      nationality: c.nationality || '',
      ego:         c.ego,
      traits:      c.traits || [],
      photo_url:   c.player?.photo_url || '',
      stats:       { ...EMPTY_STATS, ...c.stats },
    })
    setMsg(null)
  }

  const selected = useMemo(() => cards.find(c => c.card_id === selId) || null, [cards, selId])

  const liveOvr = draft ? computeOvr(draft.role, draft.stats) : 0
  const liveSalary = salaryFromOvr(liveOvr)

  const dirty = useMemo(() => {
    if (!selected || !draft) return false
    if (draft.role !== selected.role) return true
    if ((draft.nationality || '') !== (selected.nationality || '')) return true
    if (draft.ego !== selected.ego) return true
    if (JSON.stringify(draft.traits) !== JSON.stringify(selected.traits || [])) return true
    return STAT_DEFS.some(([k]) => draft.stats[k] !== selected.stats[k])
  }, [selected, draft])

  function setStat(k, v) {
    const n = Math.max(0, Math.min(100, parseInt(v, 10) || 0))
    setDraft(d => ({ ...d, stats: { ...d.stats, [k]: n } }))
  }

  function addTrait(t) {
    const v = t.trim().toUpperCase()
    if (!v || draft.traits.includes(v)) return
    setDraft(d => ({ ...d, traits: [...d.traits, v] }))
  }
  function removeTrait(t) {
    setDraft(d => ({ ...d, traits: d.traits.filter(x => x !== t) }))
  }

  async function save() {
    if (!selected || !dirty || saving) return
    setSaving(true); setMsg(null)
    try {
      const body = {
        role: draft.role,
        nationality: draft.nationality ? draft.nationality.toUpperCase().slice(0, 2) : null,
        ego: draft.ego,
        traits: draft.traits,
        ...draft.stats,
      }
      const { data } = await api.put(`/gm/admin/cards/${selected.card_id}`, body)
      setCards(cs => cs.map(c => c.card_id === data.card_id ? data : c))
      setMsg({ type: 'success', text: `✓ ${data.player?.name || 'Carte'} — OVR ${data.ovr}` })
    } catch (e) {
      setMsg({ type: 'error', text: e.response?.data?.detail || "Erreur à l'enregistrement" })
    } finally {
      setSaving(false)
    }
  }

  async function savePhoto() {
    if (!selected) return
    const next = (draft.photo_url || '').trim()
    if (next === (selected.player?.photo_url || '')) return
    try {
      const { data } = await api.put(`/gm/admin/cards/${selected.card_id}`, { photo_url: next || null })
      setCards(cs => cs.map(c => c.card_id === data.card_id ? data : c))
      setMsg({ type: 'success', text: '✓ Image mise à jour' })
    } catch (e) {
      setMsg({ type: 'error', text: e.response?.data?.detail || 'Erreur image' })
    }
  }

  async function deactivate() {
    if (!selected) return
    if (!confirm(`Dégager ${selected.player?.name || 'ce joueur'} ? La carte sera désactivée.`)) return
    try {
      await api.delete(`/gm/admin/cards/${selected.card_id}`)
      setCards(cs => cs.filter(c => c.card_id !== selected.card_id))
      setSelId(null); setDraft(null); setMsg(null)
    } catch (e) {
      setMsg({ type: 'error', text: e.response?.data?.detail || 'Erreur' })
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cards.filter(c => !q
      || (c.player?.name || '').toLowerCase().includes(q)
      || (c.player?.team_code || '').toLowerCase().includes(q))
  }, [cards, search])

  const previewEntry = draft && selected ? {
    ovr: liveOvr,
    role: draft.role,
    ego: draft.ego,
    nationality: draft.nationality,
    stats: draft.stats,
    player: { ...selected.player, photo_url: draft.photo_url || selected.player?.photo_url },
  } : null

  const weights = draft ? (ROLE_WEIGHTS[draft.role] || ROLE_WEIGHTS.MID) : ROLE_WEIGHTS.MID
  const maxW = Math.max(...Object.values(weights))

  return (
    <div className="agm-page">
      {/* ─── Header ─── */}
      <header className="agm-header">
        <div className="agm-head-left">
          <h1 className="agm-title">Notation des joueurs</h1>
          <span className="agm-sub">MYCEO · saisie des stats & OVR</span>
        </div>
        <div className="agm-count">{filtered.length} carte{filtered.length > 1 ? 's' : ''}</div>
      </header>

      {/* ─── Filtres ─── */}
      <div className="agm-filters">
        <div className="agm-leagues">
          {LEAGUES.map(lg => (
            <button key={lg} className={`agm-lg ${league === lg ? 'active' : ''}`} onClick={() => pickLeague(lg)}>{lg}</button>
          ))}
        </div>
        <input className="agm-search" placeholder="Rechercher un joueur ou une équipe…" value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      <div className="agm-layout">
        {/* ─── Colonne 1 : liste ─── */}
        <aside className="agm-list">
          {loading ? (
            <div className="agm-empty">Chargement…</div>
          ) : filtered.length === 0 ? (
            <div className="agm-empty">Aucune carte.</div>
          ) : filtered.map(c => (
            <button key={c.card_id} className={`agm-row ${selId === c.card_id ? 'active' : ''}`} onClick={() => selectCard(c)}>
              <span className="agm-row-ovr" style={{ color: statColor(c.ovr) }}>{c.ovr}</span>
              {c.player?.photo_url
                ? <img className="agm-row-photo" src={c.player.photo_url} alt="" referrerPolicy="no-referrer" onError={e => { e.target.style.visibility = 'hidden' }} />
                : <span className="agm-row-photo agm-row-photo-ph">{(c.player?.name || '?').slice(0, 2).toUpperCase()}</span>}
              <span className="agm-row-id">
                <b>{c.player?.name || '—'}</b>
                <small>{c.player?.team_code || '—'} · {c.role}</small>
              </span>
            </button>
          ))}
        </aside>

        {/* ─── Colonne 2 : éditeur ─── */}
        <section className="agm-editor">
          {!draft ? (
            <div className="agm-editor-empty">
              <div className="agm-editor-empty-ic">←</div>
              <div>Sélectionne un joueur pour éditer ses stats.</div>
            </div>
          ) : (
            <>
              <div className="agm-ed-head">
                <div className="agm-ed-name">{selected.player?.name}</div>
                {dirty && <span className="agm-dirty">non enregistré</span>}
              </div>

              {/* Rôle */}
              <div className="agm-field">
                <label className="agm-label">Rôle</label>
                <div className="agm-roles">
                  {ROLES.map(r => (
                    <button key={r} className={`agm-role ${draft.role === r ? 'active' : ''}`} onClick={() => setDraft(d => ({ ...d, role: r }))}>{r}</button>
                  ))}
                </div>
              </div>

              {/* Image */}
              <div className="agm-field">
                <label className="agm-label">Image <span className="agm-label-hint">— collez un lien, sauvegarde auto</span></label>
                <div className="agm-photo-edit">
                  <input className="agm-photo-input" placeholder="https://…" value={draft.photo_url}
                    onChange={e => setDraft(d => ({ ...d, photo_url: e.target.value }))}
                    onBlur={savePhoto}
                    onKeyDown={e => { if (e.key === 'Enter') e.target.blur() }} />
                  {draft.photo_url
                    ? <img className="agm-photo-thumb" src={draft.photo_url} alt="" referrerPolicy="no-referrer"
                           onError={e => { e.target.style.opacity = .25 }} onLoad={e => { e.target.style.opacity = 1 }} />
                    : <span className="agm-photo-thumb agm-photo-thumb-ph">—</span>}
                </div>
              </div>

              {/* Stats */}
              <div className="agm-field">
                <label className="agm-label">Stats <span className="agm-label-hint">— les libellés dorés pèsent le plus pour ce rôle</span></label>
                <div className="agm-stats">
                  {STAT_DEFS.map(([k, lbl]) => {
                    const v = draft.stats[k]
                    const heavy = weights[k] === maxW
                    return (
                      <div key={k} className={`agm-stat ${heavy ? 'heavy' : ''}`}>
                        <div className="agm-stat-top">
                          <span className="agm-stat-lbl">{lbl}<span className="agm-stat-w">{weights[k]}</span></span>
                          <input className="agm-stat-num" type="number" min="0" max="100" value={v} onChange={e => setStat(k, e.target.value)} />
                        </div>
                        <input className="agm-stat-range" type="range" min="0" max="100" value={v}
                          style={{ '--fill': `${v}%`, '--c': statColor(v) }}
                          onChange={e => setStat(k, e.target.value)} />
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Ego + Nationalité */}
              <div className="agm-grid2">
                <div className="agm-field">
                  <label className="agm-label">Ego</label>
                  <div className="agm-ego">
                    {[1, 2, 3, 4, 5].map(i => (
                      <button key={i} className={`agm-star ${i <= draft.ego ? 'on' : ''}`} onClick={() => setDraft(d => ({ ...d, ego: i }))}>★</button>
                    ))}
                  </div>
                </div>
                <div className="agm-field">
                  <label className="agm-label">Nationalité (ISO-2)</label>
                  <div className="agm-nat">
                    <input className="agm-nat-input" maxLength={2} placeholder="KR" value={draft.nationality}
                      onChange={e => setDraft(d => ({ ...d, nationality: e.target.value.toUpperCase().replace(/[^A-Z]/g, '') }))} />
                    {draft.nationality?.length === 2 &&
                      <img className="agm-nat-flag" src={`https://flagcdn.com/w40/${draft.nationality.toLowerCase()}.png`} alt="" onError={e => { e.target.style.display = 'none' }} />}
                  </div>
                </div>
              </div>

              {/* Traits */}
              <div className="agm-field">
                <label className="agm-label">Traits</label>
                <div className="agm-traits">
                  {draft.traits.map(t => (
                    <span key={t} className="agm-trait" onClick={() => removeTrait(t)}>{t}<i>✕</i></span>
                  ))}
                  <input className="agm-trait-input" placeholder="+ trait (Entrée)"
                    onKeyDown={e => { if (e.key === 'Enter') { addTrait(e.target.value); e.target.value = '' } }} />
                </div>
              </div>
            </>
          )}
        </section>

        {/* ─── Colonne 3 : preview ─── */}
        <aside className="agm-preview">
          {previewEntry ? (
            <>
              <div className="agm-preview-card">
                <GmCard entry={previewEntry} />
              </div>
              <div className="agm-readout">
                <div className="agm-readout-row"><span>OVR</span><b style={{ color: statColor(liveOvr) }}>{liveOvr}</b></div>
                <div className="agm-readout-row"><span>Salaire /j</span><b className="agm-gold">🪙 {liveSalary.toLocaleString()}</b></div>
              </div>
              {msg && <div className={`agm-msg ${msg.type}`}>{msg.text}</div>}
              <button className="agm-save" disabled={!dirty || saving} onClick={save}>
                {saving ? 'Enregistrement…' : dirty ? 'Enregistrer' : 'À jour'}
              </button>
            </>
          ) : (
            <div className="agm-preview-ph">
              <div className="agm-preview-ph-card" />
              <span>Aperçu de la carte</span>
            </div>
          )}
        </aside>
      </div>
         <div className="agm-danger">
                <button className="agm-deactivate" onClick={deactivate}>Dégager le joueur</button>
        </div>
    </div>
  )
}