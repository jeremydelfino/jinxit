import './TcgCardModal.css'
import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import api from '../../../api/client'

const RARITY_META = {
  common:    { color: '#9ca3af', label: 'Commune' },
  rare:      { color: '#3b82f6', label: 'Rare' },
  epic:      { color: '#a855f7', label: 'Épique' },
  legendary: { color: '#c89b3c', label: 'Légendaire' },
}

const TYPE_LABELS = {
  champion:   'Champion',
  pro_player: 'Joueur Pro',
  meme:       'Meme',
  cosmetic:   'Cosmétique',
  sticker:    'Sticker',
}

const CONFETTI_COLORS = ['#e2b147', '#c89b3c', '#f5d77a', '#ffffff', '#fff4d6']
const CONFETTI_COUNT  = 28

/**
 * Props :
 * - card             : objet carte
 * - quantity         : nb d'exemplaires possédés (0 = pas possédée)
 * - userCardId       : id du UserCard (si possédée) — requis pour équiper le titre
 * - equippedTitleId  : id de la carte titre actuellement équipée par l'user (optionnel)
 * - onTitleChange    : callback (newEquippedTitleId) appelé quand on équipe/déséquipe
 * - onClose
 */
export default function TcgCardModal({ card, quantity, userCardId, equippedTitleId, onTitleChange, onClose }) {
  const wrapRef = useRef(null)
  const [rotX, setRotX] = useState(0)
  const [rotY, setRotY] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [hasDragged, setHasDragged] = useState(false)
  const [equipBusy, setEquipBusy] = useState(false)
  const [localEquippedId, setLocalEquippedId] = useState(equippedTitleId)
  const dragStart = useRef({ x: 0, y: 0, rotX: 0, rotY: 0 })

  const rarity = RARITY_META[card.rarity] || RARITY_META.common
  const isLegendary = card.rarity === 'legendary'
  const isEquipped = card.is_title && localEquippedId === card.id
  const canEquip   = card.is_title && quantity > 0 && userCardId

  // Pré-calcul confettis (legendary only)
  const confettis = useMemo(() => {
    if (!isLegendary) return []
    return Array.from({ length: CONFETTI_COUNT }, () => {
      const x0 = Math.random() * 380 - 20
      const drift = (Math.random() - 0.5) * 120
      return {
        x0:    `${x0}px`,
        x1:    `${x0 + drift}px`,
        rot:   `${(Math.random() - 0.5) * 720}deg`,
        dur:   `${3 + Math.random() * 3}s`,
        delay: `${Math.random() * 5}s`,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
      }
    })
  }, [card.id, isLegendary])

  // ── Close on Escape ──
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // ── Hover tilt + tracking du glint ──
  function onMouseMove(e) {
    const r = wrapRef.current.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    wrapRef.current.style.setProperty('--mx', `${px * 100}%`)
    wrapRef.current.style.setProperty('--my', `${py * 100}%`)

    if (dragging || hasDragged) return
    setRotY((px - 0.5) * 30)
    setRotX(-(py - 0.5) * 30)
  }
  function onMouseLeave() {
    if (dragging || hasDragged) return
    setRotX(0); setRotY(0)
  }

  // ── Drag global ──
  const onDragMove = useCallback(e => {
    const dx = e.clientX - dragStart.current.x
    const dy = e.clientY - dragStart.current.y
    setRotY(dragStart.current.rotY + dx * 0.5)
    setRotX(dragStart.current.rotX - dy * 0.5)
  }, [])
  const onDragEnd = useCallback(() => {
    setDragging(false)
    window.removeEventListener('mousemove', onDragMove)
    window.removeEventListener('mouseup', onDragEnd)
  }, [onDragMove])
  function onMouseDown(e) {
    e.preventDefault()
    setDragging(true)
    setHasDragged(true)
    dragStart.current = { x: e.clientX, y: e.clientY, rotX, rotY }
    window.addEventListener('mousemove', onDragMove)
    window.addEventListener('mouseup', onDragEnd)
  }

  function reset() {
    setRotX(0); setRotY(0); setHasDragged(false)
  }

  // ── Equiper / déséquiper le titre ──
  async function handleEquipTitle() {
    if (equipBusy || !canEquip) return
    setEquipBusy(true)
    try {
      if (isEquipped) {
        await api.delete('/cards/equip-title')
        setLocalEquippedId(null)
        onTitleChange?.(null)
      } else {
        await api.post('/cards/equip-title', { user_card_id: userCardId })
        setLocalEquippedId(card.id)
        onTitleChange?.(card.id)
      }
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur")
    } finally {
      setEquipBusy(false)
    }
  }

  const effect = card.trigger_type ? buildEffect(card) : null

  return (
    <div className="tcm-overlay" onClick={onClose}>
      <button className="tcm-close" onClick={onClose}>✕</button>

      <div className="tcm-content" onClick={e => e.stopPropagation()} style={{ '--rc': rarity.color }}>

        {/* ─── COLONNE GAUCHE : CARTE 3D ─── */}
        <div className="tcm-card-col">
          <div
            ref={wrapRef}
            className={`tcm-card-wrap is-${card.rarity} ${dragging ? 'dragging' : ''}`}
            onMouseMove={onMouseMove}
            onMouseLeave={onMouseLeave}
            onMouseDown={onMouseDown}
            style={{ '--rc': rarity.color }}
          >
            {isLegendary && (
              <div className="tcm-confetti-layer">
                {confettis.map((c, i) => (
                  <span key={i} className="tcm-confetti" style={{
                    '--x0': c.x0, '--x1': c.x1, '--rot': c.rot,
                    '--dur': c.dur, '--delay': c.delay,
                    background: c.color, boxShadow: `0 0 6px ${c.color}80`,
                  }} />
                ))}
              </div>
            )}

            <div className="tcm-card-3d" style={{ transform: `rotateX(${rotX}deg) rotateY(${rotY}deg)` }}>
              <div className="tcm-face tcm-front">
                <img src={card.image_url} alt={card.name} referrerPolicy="no-referrer" />
                <div className="tcm-glint" />
              </div>
              <div className="tcm-face tcm-back">
                <img src="/card_back.png" alt="Dos de carte" />
              </div>
            </div>
          </div>

          <div className="tcm-hint">
            <span>🖱 Survole pour incliner · Clique-glisse pour tourner</span>
            {hasDragged && <button className="tcm-reset" onClick={reset}>↻ Reset</button>}
          </div>
        </div>

        {/* ─── COLONNE DROITE ─── */}
        <div className="tcm-info-col">
          <div className="tcm-rarity-badge" style={{ '--rc': rarity.color }}>
            {rarity.label.toUpperCase()}
          </div>

          <h2 className="tcm-name">{card.name}</h2>

          <div className="tcm-meta">
            <span className="tcm-meta-item">{TYPE_LABELS[card.type] || card.type}</span>
            {card.collection && <>
              <span className="tcm-meta-sep">·</span>
              <span className="tcm-meta-item tcm-meta-coll">{card.collection}</span>
            </>}
          </div>

          {effect && (
            <div className="tcm-section">
              <div className="tcm-section-title">⚡ Effet</div>
              <div className="tcm-effect-box">
                <div className="tcm-effect-boost">{effect.boost}</div>
                <div className="tcm-effect-cond">{effect.condition}</div>
              </div>
            </div>
          )}

          {(card.is_title || card.is_banner) && (
            <div className="tcm-section">
              <div className="tcm-section-title">🎨 Cosmétique</div>
              <div className="tcm-cosm-tags">
                {card.is_title && <span className="tcm-cosm">🏷 Titre</span>}
                {card.is_banner && <span className="tcm-cosm">🖼 Bannière</span>}
              </div>
              {card.is_title && card.title_text && (
                <div className="tcm-title-preview">✦ {card.title_text}</div>
              )}

              {/* ── Bouton equip titre ── */}
              {canEquip && (
                <button
                  className={`tcm-equip-btn ${isEquipped ? 'is-equipped' : ''}`}
                  onClick={handleEquipTitle}
                  disabled={equipBusy}
                >
                  {equipBusy
                    ? '…'
                    : isEquipped
                      ? '✓ Titre équipé · Retirer'
                      : '✦ Équiper ce titre'}
                </button>
              )}
            </div>
          )}

          {card.lore && (
            <div className="tcm-section">
              <div className="tcm-section-title">📜 Lore</div>
              <div className="tcm-lore">{card.lore}</div>
            </div>
          )}

          {card.artist && (
            <div className="tcm-artist">
              <span className="tcm-artist-label">Artiste</span>
              <span className="tcm-artist-name">{card.artist}</span>
            </div>
          )}

          {quantity > 0 && (
            <div className="tcm-quantity">
              <span className="tcm-qty-label">Possédée</span>
              <span className="tcm-qty-val">×{quantity}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function buildEffect(card) {
  const val = card.boost_type === 'percent_gain'
    ? `+${Math.round((card.boost_value || 0) * 100)}%`
    : `+${card.boost_value || 0}`
  let cond = ''
  if (card.trigger_type === 'champion')      cond = `Quand tu paris sur ${card.trigger_value}`
  else if (card.trigger_type === 'player')   cond = `Quand tu paris sur ${card.trigger_value}`
  else if (card.trigger_type === 'mechanic') cond = `Trigger : ${card.trigger_value}`
  else if (card.trigger_type === 'any')      cond = 'Sur tous les paris'
  else cond = card.trigger_value || ''
  return { boost: val, condition: cond }
}