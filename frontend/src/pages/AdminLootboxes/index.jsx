import './AdminLootboxes.css'
import { useState, useEffect, useRef } from 'react'
import api from '../../api/client'

const POOL_TYPE_OPTIONS = [
  { value: 'champion',   label: 'Champion' },
  { value: 'pro_player', label: 'Joueur Pro' },
  { value: 'meme',       label: 'Mème' },
  { value: 'cosmetic',   label: 'Cosmétique' },
  { value: 'sticker',    label: 'Sticker' },
]

const EMPTY_FORM = {
  name: '', description: '',
  price_coins: '',
  pool_types: ['champion'],
  collection_filter: [],
  drop_common: 60, drop_rare: 25, drop_epic: 12, drop_legendary: 3,
}

export default function AdminLootboxes() {
  const fileRef = useRef(null)

  const [boxes,       setBoxes]       = useState([])
  const [collections, setCollections] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [form,        setForm]        = useState(EMPTY_FORM)
  const [file,        setFile]        = useState(null)
  const [preview,     setPreview]     = useState(null)
  const [editingId,   setEditingId]   = useState(null)
  const [saving,      setSaving]      = useState(false)
  const [msg,         setMsg]         = useState(null)

  useEffect(() => { fetchAll() }, [])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [b, c] = await Promise.all([
        api.get('/lootbox/admin/types'),
        api.get('/admin/collections'),
      ])
      setBoxes(b.data)
      setCollections(c.data)
    } catch { setBoxes([]); setCollections([]) }
    finally { setLoading(false) }
  }

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const togglePoolType = (val) => {
    setForm(p => ({
      ...p,
      pool_types: p.pool_types.includes(val)
        ? p.pool_types.filter(x => x !== val)
        : [...p.pool_types, val]
    }))
  }

  const toggleCollection = (val) => {
    setForm(p => ({
      ...p,
      collection_filter: p.collection_filter.includes(val)
        ? p.collection_filter.filter(x => x !== val)
        : [...p.collection_filter, val]
    }))
  }

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const dropTotal = form.drop_common + form.drop_rare + form.drop_epic + form.drop_legendary

  const startEdit = (box) => {
    setEditingId(box.id)
    setForm({
      name: box.name, description: box.description || '',
      price_coins: box.price_coins ?? '',
      pool_types: box.pool_types.split(',').map(s => s.trim()).filter(Boolean),
      collection_filter: box.collection_filter ? box.collection_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
      drop_common: box.drop_rates.common,
      drop_rare: box.drop_rates.rare,
      drop_epic: box.drop_rates.epic,
      drop_legendary: box.drop_rates.legendary,
    })
    setFile(null)
    setPreview(box.image_url || null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const cancelEdit = () => {
    setEditingId(null); setForm(EMPTY_FORM); setMsg(null)
    setFile(null); setPreview(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { setMsg({ type: 'error', text: 'Nom requis' }); return }
    if (form.pool_types.length === 0) { setMsg({ type: 'error', text: 'Au moins un type dans le pool' }); return }
    if (dropTotal !== 100) { setMsg({ type: 'error', text: `Drop rates = ${dropTotal} (doit faire 100)` }); return }

    const fd = new FormData()
    fd.append('name', form.name.trim())
    if (form.description.trim()) fd.append('description', form.description.trim())
    fd.append('pool_types', form.pool_types.join(','))
    if (form.collection_filter.length > 0) fd.append('collection_filter', form.collection_filter.join(','))
    if (form.price_coins !== '') fd.append('price_coins', parseInt(form.price_coins))
    fd.append('drop_common', form.drop_common)
    fd.append('drop_rare', form.drop_rare)
    fd.append('drop_epic', form.drop_epic)
    fd.append('drop_legendary', form.drop_legendary)
    if (file) fd.append('file', file)

    const config = { headers: { 'Content-Type': 'multipart/form-data' } }

    setSaving(true)
    try {
      if (editingId) {
        await api.patch(`/lootbox/admin/types/${editingId}`, fd, config)
        setMsg({ type: 'success', text: `Caisse "${form.name}" modifiée` })
      } else {
        await api.post('/lootbox/admin/types', fd, config)
        setMsg({ type: 'success', text: `Caisse "${form.name}" créée` })
      }
      cancelEdit()
      fetchAll()
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Erreur' })
    } finally {
      setSaving(false)
      setTimeout(() => setMsg(null), 4000)
    }
  }

  const handleDelete = async (box) => {
    if (!confirm(`Supprimer "${box.name}" ?`)) return
    try {
      const r = await api.delete(`/lootbox/admin/types/${box.id}`)
      alert(r.data.mode === 'soft' ? 'Désactivée (caisses en circulation)' : 'Supprimée')
      fetchAll()
    } catch { alert('Erreur suppression') }
  }

  const toggleActive = async (box) => {
    try {
      const fd = new FormData()
      fd.append('is_active', !box.is_active)
      await api.patch(`/lootbox/admin/types/${box.id}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      fetchAll()
    } catch { alert('Erreur') }
  }

  return (
    <div className="adm-lb-page">
      <div className="adm-lb-header">
        <div className="adm-lb-title">📦 Gestion des caisses</div>
        <div className="adm-lb-count">{boxes.length} caisses</div>
      </div>

      <div className="adm-lb-layout">
        {/* ── FORM ── */}
        <form className="adm-lb-form" onSubmit={handleSubmit}>
          <div className="adm-lb-form-title">
            {editingId ? `✏️ Édition #${editingId}` : '+ Nouvelle caisse'}
            {editingId && <button type="button" className="adm-lb-cancel" onClick={cancelEdit}>Annuler</button>}
          </div>

          {/* Upload image */}
          <div className="adm-lb-group">
            <label>Image de la caisse <span className="adm-lb-hint">(optionnel)</span></label>
            <div className="adm-lb-upload" onClick={() => fileRef.current?.click()}
              style={preview ? { borderColor: '#65BD6240', padding: 0, overflow: 'hidden' } : {}}>
              {preview
                ? <img src={preview} alt="preview" className="adm-lb-upload-preview" />
                : <>
                    <div className="adm-lb-upload-icon">📦</div>
                    <div className="adm-lb-upload-label">Clique pour uploader</div>
                    <div className="adm-lb-upload-sub">PNG, JPG, WEBP</div>
                  </>
              }
              <input type="file" ref={fileRef} accept="image/*,image/webp" style={{ display: 'none' }} onChange={handleFile} />
            </div>
            {preview && (
              <button type="button" className="adm-lb-cancel" style={{ alignSelf: 'flex-start', marginTop: 4 }}
                onClick={() => { setFile(null); setPreview(null) }}>
                ✕ Retirer l'image
              </button>
            )}
          </div>

          <div className="adm-lb-group">
            <label>Nom</label>
            <input className="adm-lb-input" value={form.name} onChange={e => f('name', e.target.value)} placeholder="ex: Caisse LEC 2026" />
          </div>

          <div className="adm-lb-group">
            <label>Description</label>
            <input className="adm-lb-input" value={form.description} onChange={e => f('description', e.target.value)} placeholder="optionnel" />
          </div>

          <div className="adm-lb-group">
            <label>Prix (coins) <span className="adm-lb-hint">(vide = non achetable)</span></label>
            <input className="adm-lb-input" type="number" min="0" value={form.price_coins} onChange={e => f('price_coins', e.target.value)} placeholder="ex: 500" />
          </div>

          <div className="adm-lb-group">
            <label>Types de cartes dans le pool</label>
            <div className="adm-lb-chips">
              {POOL_TYPE_OPTIONS.map(opt => (
                <button key={opt.value} type="button"
                  className={`adm-lb-chip ${form.pool_types.includes(opt.value) ? 'active' : ''}`}
                  onClick={() => togglePoolType(opt.value)}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="adm-lb-group">
            <label>Collections autorisées <span className="adm-lb-hint">(vide = toutes)</span></label>
            {collections.length === 0 ? (
              <div className="adm-lb-empty-coll">Aucune collection définie. Crée des cartes avec un champ "collection" rempli.</div>
            ) : (
              <div className="adm-lb-chips">
                {collections.map(c => (
                  <button key={c} type="button"
                    className={`adm-lb-chip ${form.collection_filter.includes(c) ? 'active gold' : ''}`}
                    onClick={() => toggleCollection(c)}>
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="adm-lb-group">
            <label>Drop rates (%) <span className={`adm-lb-total ${dropTotal === 100 ? 'ok' : 'err'}`}>Total: {dropTotal}/100</span></label>
            <div className="adm-lb-drops">
              <DropInput label="Commune"     color="#9ca3af" value={form.drop_common}    onChange={v => f('drop_common', v)} />
              <DropInput label="Rare"        color="#3b82f6" value={form.drop_rare}      onChange={v => f('drop_rare', v)} />
              <DropInput label="Épique"      color="#a855f7" value={form.drop_epic}      onChange={v => f('drop_epic', v)} />
              <DropInput label="Légendaire"  color="#c89b3c" value={form.drop_legendary} onChange={v => f('drop_legendary', v)} />
            </div>
          </div>

          {msg && <div className={`adm-lb-msg ${msg.type}`}>{msg.text}</div>}

          <button type="submit" className="adm-lb-btn" disabled={saving}>
            {saving ? '...' : editingId ? 'Enregistrer' : '+ Créer la caisse'}
          </button>
        </form>

        {/* ── LISTE ── */}
        <div className="adm-lb-list">
          {loading ? (
            <div className="adm-lb-loading">Chargement...</div>
          ) : boxes.length === 0 ? (
            <div className="adm-lb-empty">Aucune caisse créée.</div>
          ) : (
            <div className="adm-lb-grid">
              {boxes.map(box => (
                <div key={box.id} className={`adm-lb-card ${box.is_active ? '' : 'inactive'}`}>
                  {box.image_url && (
                    <div className="adm-lb-card-img">
                      <img src={box.image_url} alt={box.name} referrerPolicy="no-referrer" />
                    </div>
                  )}
                  <div className="adm-lb-card-head">
                    <div className="adm-lb-card-name">{box.name}</div>
                    <div className="adm-lb-card-status" data-active={box.is_active}>{box.is_active ? '● Actif' : '○ Inactif'}</div>
                  </div>
                  {box.description && <div className="adm-lb-card-desc">{box.description}</div>}
                  <div className="adm-lb-card-meta">
                    <span className="adm-lb-meta-tag">💰 {box.price_coins ?? '—'}</span>
                    <span className="adm-lb-meta-tag">🏷 {box.pool_types}</span>
                    {box.collection_filter && <span className="adm-lb-meta-tag gold">📚 {box.collection_filter}</span>}
                  </div>
                  <div className="adm-lb-card-drops">
                    <span style={{ color: '#9ca3af' }}>C {box.drop_rates.common}%</span>
                    <span style={{ color: '#3b82f6' }}>R {box.drop_rates.rare}%</span>
                    <span style={{ color: '#a855f7' }}>E {box.drop_rates.epic}%</span>
                    <span style={{ color: '#c89b3c' }}>L {box.drop_rates.legendary}%</span>
                  </div>
                  <div className="adm-lb-card-actions">
                    <button className="adm-lb-act" onClick={() => startEdit(box)}>✏️ Éditer</button>
                    <button className="adm-lb-act" onClick={() => toggleActive(box)}>{box.is_active ? '🚫 Désactiver' : '✅ Activer'}</button>
                    <button className="adm-lb-act adm-lb-del" onClick={() => handleDelete(box)}>🗑</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function DropInput({ label, color, value, onChange }) {
  return (
    <div className="adm-lb-drop">
      <div className="adm-lb-drop-label" style={{ color }}>{label}</div>
      <input type="number" min="0" max="100" className="adm-lb-input adm-lb-drop-input"
        value={value} onChange={e => onChange(parseInt(e.target.value) || 0)} />
    </div>
  )
}