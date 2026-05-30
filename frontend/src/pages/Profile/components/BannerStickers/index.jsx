import './BannerStickers.css'
import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import api from '../../../../api/client'

// Tailles disponibles (clé stockée en DB → px de rendu)
const SIZES = { small: 70, medium: 100, large: 140 }
const SIZE_ORDER = ['small', 'medium', 'large']
const SIZE_LABELS = { small: 'S', medium: 'M', large: 'L' }

export default function BannerStickers({ userId, isOwnProfile, bannerRef }) {
  const [stickers, setStickers]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [showPicker, setShowPicker] = useState(false)
  const [inventory, setInventory]   = useState([])
  const [draggingId, setDraggingId] = useState(null)

  // état vif du drag (jamais dans le state React pour éviter les valeurs périmées)
  const drag = useRef(null)
  const moved = useRef(false)

  useEffect(() => { load() }, [userId])

  async function load() {
    setLoading(true)
    try {
      const path = isOwnProfile
        ? '/cards/equipped-stickers'
        : `/cards/equipped-stickers/public/${userId}`
      const { data } = await api.get(path)
      setStickers(Array.isArray(data) ? data : [])
    } catch {
      setStickers([])
    } finally {
      setLoading(false)
    }
  }

  async function openPicker() {
    if (!isOwnProfile) return
    setShowPicker(true)
    try {
      const { data } = await api.get('/cards/my-cards')
      const equippedIds = new Set(stickers.map(s => s.user_card_id))
      const available = data
        .filter(uc => uc.card.type === 'sticker')
        .filter(uc => !equippedIds.has(uc.id))
      setInventory(available)
    } catch {
      setInventory([])
    }
  }

  async function pickSticker(userCardId) {
    try {
      await api.post('/cards/equip-sticker', {
        user_card_id: userCardId,
        position_x:   50,
        position_y:   50,
      })
      setShowPicker(false)
      await load()
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur à l'équipement")
    }
  }

  async function unequip(userCardId) {
    if (!window.confirm("Retirer ce sticker de la bannière ?")) return
    try {
      await api.delete(`/cards/equip-sticker/${userCardId}`)
      await load()
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur")
    }
  }

  /* ── RESIZE : cycle S → M → L → S ── */
  async function cycleSize(e, sticker) {
    e.stopPropagation()
    const cur  = sticker.size || 'medium'
    const next = SIZE_ORDER[(SIZE_ORDER.indexOf(cur) + 1) % SIZE_ORDER.length]
    setStickers(prev => prev.map(s =>
      s.user_card_id === sticker.user_card_id ? { ...s, size: next } : s
    ))
    try {
      await api.post('/cards/move-sticker', {
        user_card_id: sticker.user_card_id,
        position_x:   sticker.position_x,
        position_y:   sticker.position_y,
        size:         next,
      })
    } catch {
      load()
    }
  }

  /* ── DRAG : listeners sur document le temps du drag.
     Le sticker re-render à chaque move, donc capturer SUR lui est fragile.
     document reste stable → pointerup garanti, pas de "collage". ── */
  function onPointerDown(e, sticker) {
    if (!isOwnProfile) return
    if (e.button !== undefined && e.button !== 0) return  // clic gauche seulement
    e.preventDefault()

    const banner = bannerRef?.current
    if (!banner) return
    const bRect = banner.getBoundingClientRect()

    const centerX  = (sticker.position_x / 100) * bRect.width
    const centerY  = (sticker.position_y / 100) * bRect.height
    const pointerX = e.clientX - bRect.left
    const pointerY = e.clientY - bRect.top

    drag.current = {
      id:      sticker.user_card_id,
      offsetX: pointerX - centerX,
      offsetY: pointerY - centerY,
      lastX:   sticker.position_x,
      lastY:   sticker.position_y,
    }
    moved.current = false
    setDraggingId(sticker.user_card_id)

    document.addEventListener('pointermove', onDocMove)
    document.addEventListener('pointerup', onDocUp)
  }

  function onDocMove(e) {
    const d = drag.current
    if (!d) return
    const banner = bannerRef?.current
    if (!banner) return
    const bRect = banner.getBoundingClientRect()

    const pointerX = e.clientX - bRect.left
    const pointerY = e.clientY - bRect.top
    const x = ((pointerX - d.offsetX) / bRect.width)  * 100
    const y = ((pointerY - d.offsetY) / bRect.height) * 100
    const cx = Math.max(0, Math.min(100, x))
    const cy = Math.max(0, Math.min(100, y))

    moved.current = true
    d.lastX = cx
    d.lastY = cy
    const id = d.id
    setStickers(prev => prev.map(s =>
      s.user_card_id === id
        ? { ...s, position_x: cx, position_y: cy }
        : s
    ))
  }

  async function onDocUp() {
    document.removeEventListener('pointermove', onDocMove)
    document.removeEventListener('pointerup', onDocUp)
    const d = drag.current
    if (!d) return

    const { id, lastX, lastY } = d
    const wasMoved = moved.current
    drag.current = null
    setDraggingId(null)

    if (!wasMoved) return  // simple clic, pas de drag → rien à sauvegarder

    const st = stickers.find(s => s.user_card_id === id)
    try {
      await api.post('/cards/move-sticker', {
        user_card_id: id,
        position_x:   lastX,
        position_y:   lastY,
        size:         st?.size || 'medium',
      })
    } catch {
      load()
    }
  }

  // sécurité : nettoyage si le composant démonte en plein drag
  useEffect(() => () => {
    document.removeEventListener('pointermove', onDocMove)
    document.removeEventListener('pointerup', onDocUp)
  }, [])

  if (loading) return null
  if (!isOwnProfile && stickers.length === 0) return null

  const canAddMore = isOwnProfile && stickers.length < 3

  return (
    <>
      {stickers.map(s => {
        const px = SIZES[s.size || 'medium']
        return (
          <div
            key={s.user_card_id}
            className={`bs-sticker r-${s.card.rarity} ${draggingId === s.user_card_id ? 'dragging' : ''}`}
            style={{
              left:   `${s.position_x}%`,
              top:    `${s.position_y}%`,
              width:  `${px}px`,
              height: `${px}px`,
            }}
            onPointerDown={(e) => onPointerDown(e, s)}
            title={s.card.name}
          >
            <img src={s.card.image_url} alt={s.card.name} referrerPolicy="no-referrer" draggable={false} />
            {isOwnProfile && (
              <>
                <button
                  className="bs-sticker-size"
                  onClick={(e) => cycleSize(e, s)}
                  onPointerDown={(e) => e.stopPropagation()}
                  title="Changer la taille"
                >{SIZE_LABELS[s.size || 'medium']}</button>
                <button
                  className="bs-sticker-remove"
                  onClick={(e) => { e.stopPropagation(); unequip(s.user_card_id) }}
                  onPointerDown={(e) => e.stopPropagation()}
                  title="Retirer"
                >×</button>
              </>
            )}
          </div>
        )
      })}

      {canAddMore && (
        <button className="bs-add-btn" onClick={openPicker}>
          <span>+</span> Sticker
        </button>
      )}

      {showPicker && createPortal(
        <div className="bs-picker-overlay" onClick={() => setShowPicker(false)}>
          <div className="bs-picker" onClick={e => e.stopPropagation()}>
            <div className="bs-picker-head">
              <div className="bs-picker-eyebrow">PERSONNALISATION</div>
              <h3 className="bs-picker-title">Choisir un sticker</h3>
              <button className="bs-picker-close" onClick={() => setShowPicker(false)}>×</button>
            </div>
            {inventory.length === 0 ? (
              <div className="bs-picker-empty">
                <div className="bs-picker-empty-icon">✨</div>
                <div className="bs-picker-empty-title">Aucun sticker disponible</div>
                <div className="bs-picker-empty-sub">Ouvre des caisses pour en obtenir.</div>
              </div>
            ) : (
              <div className="bs-picker-grid">
                {inventory.map(uc => (
                  <button
                    key={uc.id}
                    className={`bs-picker-card r-${uc.card.rarity}`}
                    onClick={() => pickSticker(uc.id)}
                  >
                    <img src={uc.card.image_url} alt={uc.card.name} referrerPolicy="no-referrer" />
                    <div className="bs-picker-card-name">{uc.card.name}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  )
}