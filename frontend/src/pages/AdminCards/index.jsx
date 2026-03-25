import './AdminCards.css'
import { useState, useEffect, useRef } from 'react'
import api from '../../api/client'

const RARITIES = [
  { value: 'common',    label: 'Commune',     color: '#9ca3af' },
  { value: 'rare',      label: 'Rare',        color: '#3b82f6' },
  { value: 'epic',      label: 'Épique',      color: '#a855f7' },
  { value: 'legendary', label: 'Légendaire',  color: '#c89b3c' },
]

const TYPES = [
  { value: 'champion',   label: 'Champion' },
  { value: 'pro_player', label: 'Joueur Pro' },
  { value: 'meme',       label: 'Mème' },
  { value: 'cosmetic',   label: 'Cosmétique' },
]

const TRIGGER_TYPES = [
  { value: 'champion',  label: 'Champion joué' },
  { value: 'player',    label: 'Joueur présent' },
  { value: 'mechanic',  label: 'Mécanique' },
  { value: 'any',       label: 'Tous les paris' },
]

const TRIGGER_PRESETS = {
  mechanic: ['first_blood', 'first_tower', 'over_30_kills', 'under_30_kills'],
}

const EMPTY_FORM = {
  name: '', type: 'champion', rarity: 'common',
  boost_type: 'percent_gain', boost_value: '0.15',
  trigger_type: 'champion', trigger_value: '',
  is_banner: false, is_title: false, title_text: '',
  hasEffect: true,
}

export default function AdminCards() {
  const fileRef = useRef(null)
  const [cards,     setCards]     = useState([])
  const [loading,   setLoading]   = useState(true)
  const [form,      setForm]      = useState(EMPTY_FORM)
  const [preview,   setPreview]   = useState(null)
  const [file,      setFile]      = useState(null)
  const [saving,    setSaving]    = useState(false)
  const [msg,       setMsg]       = useState(null)
  const [filter,    setFilter]    = useState('all')

  useEffect(() => {
    fetchCards()
  }, [])

  const fetchCards = () => {
    setLoading(true)
    api.get('/admin/cards')
      .then(r => setCards(r.data))
      .catch(() => setCards([]))
      .finally(() => setLoading(false))
  }

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) { setMsg({ type: 'error', text: 'Sélectionne une image' }); return }
    if (!form.name.trim()) { setMsg({ type: 'error', text: 'Nom requis' }); return }

    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', form.name)
    fd.append('type', form.type)
    fd.append('rarity', form.rarity)
    fd.append('is_banner', form.is_banner)
    fd.append('is_title', form.is_title)
    if (form.is_title) fd.append('title_text', form.title_text)

    if (form.hasEffect) {
      fd.append('boost_type', form.boost_type)
      fd.append('boost_value', parseFloat(form.boost_value) || 0)
      fd.append('trigger_type', form.trigger_type)
      fd.append('trigger_value', form.trigger_value)
    }

    setSaving(true)
    try {
      await api.post('/admin/cards', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMsg({ type: 'success', text: `Carte "${form.name}" créée !` })
      setForm(EMPTY_FORM)
      setFile(null)
      setPreview(null)
      fetchCards()
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Erreur lors de la création' })
    } finally {
      setSaving(false)
      setTimeout(() => setMsg(null), 4000)
    }
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Supprimer la carte "${name}" ?`)) return
    try {
      await api.delete(`/admin/cards/${id}`)
      setCards(c => c.filter(x => x.id !== id))
    } catch (err) {
      alert('Erreur suppression')
    }
  }

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const filtered = filter === 'all' ? cards : cards.filter(c => c.rarity === filter)

  return (
    <div className="admin-cards-page">
      <div className="admin-header">
        <div className="admin-title">🃏 Gestion des cartes</div>
        <div className="admin-count">{cards.length} cartes</div>
      </div>

      <div className="admin-layout">

        {/* ── FORMULAIRE CRÉATION ── */}
        <form className="card-form" onSubmit={handleSubmit}>
          <div className="form-section-title">Nouvelle carte</div>

          {/* Upload image */}
          <div className="upload-zone" onClick={() => fileRef.current?.click()}
            style={preview ? { borderColor: '#00e5ff40', padding: 0, overflow: 'hidden' } : {}}>
            {preview
              ? <img src={preview} alt="preview" className="upload-preview" />
              : <>
                  <div className="upload-icon">🖼</div>
                  <div className="upload-label">Clique pour uploader l'image</div>
                  <div className="upload-sub">PNG, JPG, WEBP</div>
                </>
            }
            <input type="file" ref={fileRef} accept="image/*,image/webp" style={{ display: 'none' }} onChange={handleFile} />
          </div>
          {preview && (
            <button type="button" className="btn-reset-img" onClick={() => { setFile(null); setPreview(null) }}>
              ✕ Changer l'image
            </button>
          )}

          {/* Nom */}
          <div className="form-group">
            <label>Nom de la carte</label>
            <input className="form-input" placeholder="ex: Faker — The Unkillable" value={form.name} onChange={e => f('name', e.target.value)} />
          </div>

          {/* Type + Rareté */}
          <div className="form-row">
            <div className="form-group">
              <label>Type</label>
              <select className="form-input" value={form.type} onChange={e => f('type', e.target.value)}>
                {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Rareté</label>
              <select className="form-input" value={form.rarity} onChange={e => f('rarity', e.target.value)}
                style={{ color: RARITIES.find(r => r.value === form.rarity)?.color }}>
                {RARITIES.map(r => <option key={r.value} value={r.value} style={{ color: r.color }}>{r.label}</option>)}
              </select>
            </div>
          </div>

          {/* Toggle effet */}
          <div className="form-toggle">
            <label className="toggle-label">
              <input type="checkbox" checked={form.hasEffect} onChange={e => f('hasEffect', e.target.checked)} />
              <span className="toggle-slider" />
              Cette carte a un effet sur les paris
            </label>
          </div>

          {/* Effet */}
          {form.hasEffect && (
            <div className="effect-block">
              <div className="form-row">
                <div className="form-group">
                  <label>Type de boost</label>
                  <select className="form-input" value={form.boost_type} onChange={e => f('boost_type', e.target.value)}>
                    <option value="percent_gain">% des gains</option>
                    <option value="flat_gain">Coins fixes</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Valeur {form.boost_type === 'percent_gain' ? '(0.15 = +15%)' : '(coins)'}</label>
                  <input className="form-input" type="number" step="0.01" min="0"
                    value={form.boost_value} onChange={e => f('boost_value', e.target.value)} />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Déclencheur</label>
                  <select className="form-input" value={form.trigger_type} onChange={e => f('trigger_type', e.target.value)}>
                    {TRIGGER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Valeur du déclencheur</label>
                  {form.trigger_type === 'mechanic' ? (
                    <select className="form-input" value={form.trigger_value} onChange={e => f('trigger_value', e.target.value)}>
                      <option value="">-- Choisir --</option>
                      {TRIGGER_PRESETS.mechanic.map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  ) : form.trigger_type === 'any' ? (
                    <input className="form-input" disabled value="Tous les paris" style={{ opacity: 0.5 }} />
                  ) : (
                    <input className="form-input"
                      placeholder={form.trigger_type === 'champion' ? 'ex: Yasuo, Ahri...' : 'ex: Faker, Caps...'}
                      value={form.trigger_value} onChange={e => f('trigger_value', e.target.value)} />
                  )}
                </div>
              </div>

              {/* Preview de l'effet */}
              {form.boost_value > 0 && form.trigger_type && (
                <div className="effect-preview">
                  <span className="effect-preview-icon">⚡</span>
                  {form.trigger_type === 'any'
                    ? `+${form.boost_type === 'percent_gain' ? Math.round(form.boost_value * 100) + '%' : form.boost_value + ' coins'} sur tous les paris`
                    : `+${form.boost_type === 'percent_gain' ? Math.round(form.boost_value * 100) + '%' : form.boost_value + ' coins'} si ${form.trigger_value || '...'} est dans la partie`
                  }
                </div>
              )}
            </div>
          )}

          {/* Cosmétiques */}
          <div className="form-row">
            <label className="toggle-label">
              <input type="checkbox" checked={form.is_banner} onChange={e => f('is_banner', e.target.checked)} />
              <span className="toggle-slider" />
              Bannière de profil
            </label>
            <label className="toggle-label">
              <input type="checkbox" checked={form.is_title} onChange={e => f('is_title', e.target.checked)} />
              <span className="toggle-slider" />
              Titre de profil
            </label>
          </div>
          {form.is_title && (
            <div className="form-group">
              <label>Texte du titre</label>
              <input className="form-input" placeholder='ex: "Le Parieur Légendaire"' value={form.title_text} onChange={e => f('title_text', e.target.value)} />
            </div>
          )}

          {msg && <div className={`form-msg ${msg.type}`}>{msg.text}</div>}

          <button type="submit" className="btn-create" disabled={saving}>
            {saving ? 'Upload en cours...' : '+ Créer la carte'}
          </button>
        </form>

        {/* ── LISTE DES CARTES ── */}
        <div className="cards-panel">
          <div className="cards-panel-header">
            <div className="rarity-filters">
              {[{ value: 'all', label: 'Toutes', color: '#e8eaf0' }, ...RARITIES].map(r => (
                <button key={r.value} className={`rarity-filter ${filter === r.value ? 'active' : ''}`}
                  style={filter === r.value ? { borderColor: r.color, color: r.color, background: r.color + '18' } : {}}
                  onClick={() => setFilter(r.value)}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="cards-loading">Chargement...</div>
          ) : filtered.length === 0 ? (
            <div className="cards-empty">Aucune carte pour le moment.</div>
          ) : (
            <div className="cards-admin-grid">
              {filtered.map(card => {
                const r = RARITIES.find(x => x.value === card.rarity) || RARITIES[0]
                return (
                  <div key={card.id} className="admin-card-item" style={{ '--rc': r.color }}>
                    <div className="admin-card-img">
                      {card.image_url
                        ? <img src={card.image_url} alt={card.name} referrerPolicy="no-referrer" />
                        : <div className="admin-card-placeholder">🃏</div>
                      }
                      <div className="admin-card-rarity-bar" />
                    </div>
                    <div className="admin-card-info">
                      <div className="admin-card-name">{card.name}</div>
                      <div className="admin-card-meta">
                        <span style={{ color: r.color }}>{r.label}</span>
                        <span style={{ color: '#4b5563' }}>·</span>
                        <span style={{ color: '#6b7280' }}>{TYPES.find(t => t.value === card.type)?.label}</span>
                      </div>
                      {card.trigger_type && (
                        <div className="admin-card-effect">
                          ⚡ +{card.boost_type === 'percent_gain' ? Math.round(card.boost_value * 100) + '%' : card.boost_value}
                          {card.trigger_type !== 'any' && ` · ${card.trigger_value}`}
                        </div>
                      )}
                    </div>
                    <button className="admin-card-delete" onClick={() => handleDelete(card.id, card.name)}>✕</button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}