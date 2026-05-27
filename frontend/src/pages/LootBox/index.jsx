import './LootBox.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import TcgCard from '../../components/ui/TcgCard'
import TcgCardModal from '../../components/ui/TcgCardModal'

const RARITY_META = {
  common:    { color: '#9ca3af', label: 'Commune',     resale: 50 },
  rare:      { color: '#3b82f6', label: 'Rare',        resale: 200 },
  epic:      { color: '#a855f7', label: 'Épique',      resale: 800 },
  legendary: { color: '#c89b3c', label: 'Légendaire',  resale: 3000 },
}

const RARITY_RANK = { legendary: 0, epic: 1, rare: 2, common: 3 }

const TABS = [
  { id: 'collection', label: 'Collection', icon: '🃏' },
  { id: 'stickers',   label: 'Stickers',   icon: '✨' },
  { id: 'boxes',      label: 'Mes caisses', icon: '📦' },
  { id: 'shop',       label: 'Boutique',   icon: '🛒' },
]

export default function LootBox() {
  const navigate = useNavigate()
  const token = useAuthStore(s => s.token)
  const user = useAuthStore(s => s.user)
  const refreshUser = useAuthStore(s => s.refreshUser)
  const updateUser  = useAuthStore(s => s.updateUser)

  const [tab, setTab] = useState('collection')

  // Data
  const [boxes, setBoxes]       = useState([])
  const [types, setTypes]       = useState([])
  const [progress, setProgress] = useState({})
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  // Actions in flight
  const [opening, setOpening]     = useState(null)
  const [buyingId, setBuyingId]   = useState(null)
  const [sellingId, setSellingId] = useState(null)
  const [revealed, setRevealed]   = useState(null)
  const [phase, setPhase]         = useState('idle')

  // ── Zoom modal + active collection filters ──
  const [zoomedCard, setZoomedCard]                 = useState(null) // { card, quantity, userCardId }
  const [activeCardsColl, setActiveCardsColl]       = useState(null) // null = "Toutes"
  const [activeStickersColl, setActiveStickersColl] = useState(null)

  useEffect(() => {
    if (!token) { navigate('/login'); return }
    loadAll()
  }, [token])

  async function loadAll() {
    setLoading(true)
    const [b, t, p] = await Promise.allSettled([
      api.get('/lootbox/my-boxes'),
      api.get('/lootbox/types'),
      api.get('/cards/collection-progress'),
    ])
    if (b.status === 'fulfilled') setBoxes(b.value.data)
    if (t.status === 'fulfilled') setTypes(t.value.data)
    if (p.status === 'fulfilled') setProgress(p.value.data)
    const firstError = [b, t, p].find(r => r.status === 'rejected')
    if (firstError) setError(firstError.reason?.response?.data?.detail || "Certaines données n'ont pas pu être chargées")
    setLoading(false)
  }

  async function openBox(box) {
    if (opening) return
    setOpening(box.id)
    setPhase('shaking')
    setError(null)
    try {
      const [{ data }] = await Promise.all([
        api.post(`/lootbox/${box.id}/open`),
        new Promise(r => setTimeout(r, 1200)),
      ])
      setPhase('revealing')
      setTimeout(() => setRevealed(data.card), 300)
      loadAll()
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur à l'ouverture")
      setOpening(null)
      setPhase('idle')
    }
  }

  async function buyBox(boxType) {
    if (buyingId) return
    setBuyingId(boxType.id)
    setError(null)
    try {
      await api.post(`/lootbox/buy/${boxType.id}`)
      await refreshUser?.()
      await loadAll()
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur à l'achat")
    } finally {
      setBuyingId(null)
    }
  }

  async function sellCard(userCardId, cardName, rarity) {
    if (sellingId) return
    const price = RARITY_META[rarity]?.resale ?? '?'
    if (!window.confirm(`Revendre "${cardName}" pour ${price} coins ?`)) return
    setSellingId(userCardId)
    setError(null)
    try {
      await api.post(`/cards/${userCardId}/sell`)
      await refreshUser?.()
      await loadAll()
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur à la revente")
    } finally {
      setSellingId(null)
    }
  }

  function closeReveal() {
    setRevealed(null)
    setOpening(null)
    setPhase('idle')
  }

  function handleTitleChange(newId) {
    updateUser?.({ equipped_title_id: newId })
  }

  // ─── Computed ─────────────────────────────────────────────
  const totalBoxes = boxes.length
  const grouped = boxes.reduce((acc, b) => {
    const id = b.box_type.id
    if (!acc[id]) acc[id] = { ...b.box_type, count: 0, boxes: [] }
    acc[id].count++
    acc[id].boxes.push(b)
    return acc
  }, {})
  const groupedList = Object.values(grouped)

  // Progress separé : cartes hors stickers vs stickers
  const collectionsAll = Object.entries(progress).flatMap(([type, colls]) =>
    colls.map(c => ({ ...c, _type: type }))
  )
  const cardsCollections    = collectionsAll.filter(c => c._type !== 'sticker')
  const stickersCollections = collectionsAll.filter(c => c._type === 'sticker')

  // Stats globales hero
  const totalOwnedCards = cardsCollections.reduce((s, c) => s + c.owned, 0)
  const totalCards      = cardsCollections.reduce((s, c) => s + c.total, 0)
  const totalOwnedStick = stickersCollections.reduce((s, c) => s + c.owned, 0)
  const totalStickers   = stickersCollections.reduce((s, c) => s + c.total, 0)

  // Regrouper par nom de collection + tri rareté décroissante au sein de chaque collection
  function mergeByCollectionName(list) {
    const map = {}
    for (const c of list) {
      const key = c.name || '__none__'
      if (!map[key]) map[key] = { name: c.name, total: 0, owned: 0, cards: [] }
      map[key].total += c.total
      map[key].owned += c.owned
      map[key].cards = map[key].cards.concat(c.cards)
    }
    // Tri : rareté décroissante, puis owned avant locked, puis nom
    for (const k in map) {
      map[k].cards.sort((a, b) => {
        const rA = RARITY_RANK[a.card.rarity] ?? 99
        const rB = RARITY_RANK[b.card.rarity] ?? 99
        if (rA !== rB) return rA - rB
        if (a.owned !== b.owned) return a.owned ? -1 : 1
        return a.card.name.localeCompare(b.card.name)
      })
    }
    return Object.values(map).sort((a, b) =>
      (a.name === null) - (b.name === null) || (a.name || '').localeCompare(b.name || '')
    )
  }
  const collectionsCards    = mergeByCollectionName(cardsCollections)
  const collectionsStickers = mergeByCollectionName(stickersCollections)

  return (
    <div className="lb-page">
      <div className="lb-glow lb-glow-1" />
      <div className="lb-glow lb-glow-2" />
      <div className="lb-glow lb-glow-3" />

      {/* ─── HERO ─── */}
      <header className="lb-hero">
        <div className="lb-hero-eyebrow">CAISSES & COLLECTION</div>
        <h1 className="lb-hero-title">Ta collection</h1>
        <p className="lb-hero-sub">Ouvre des caisses, complète tes collections, équipe tes stickers.</p>

        <div className="lb-hero-stats">
          <div className="lb-hero-stat">
            <div className="lb-hero-stat-val lb-hero-stat-gold">{user?.coins?.toLocaleString() ?? '—'}</div>
            <div className="lb-hero-stat-lbl">Coins</div>
          </div>
          <div className="lb-hero-stat-divider" />
          <div className="lb-hero-stat">
            <div className="lb-hero-stat-val">{totalBoxes}</div>
            <div className="lb-hero-stat-lbl">Caisses en attente</div>
          </div>
          <div className="lb-hero-stat-divider" />
          <div className="lb-hero-stat">
            <div className="lb-hero-stat-val lb-hero-stat-green">{totalOwnedCards}<span className="lb-hero-stat-tot">/{totalCards}</span></div>
            <div className="lb-hero-stat-lbl">Cartes</div>
          </div>
          <div className="lb-hero-stat-divider" />
          <div className="lb-hero-stat">
            <div className="lb-hero-stat-val lb-hero-stat-purple">{totalOwnedStick}<span className="lb-hero-stat-tot">/{totalStickers}</span></div>
            <div className="lb-hero-stat-lbl">Stickers</div>
          </div>
        </div>
      </header>

      {error && <div className="lb-error">⚠ {error}</div>}

      {/* ─── TABS ─── */}
      <div className="lb-tabs-wrap">
        <div className="lb-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`lb-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <span className="lb-tab-icon">{t.icon}</span>
              <span className="lb-tab-label">{t.label}</span>
              {t.id === 'boxes' && totalBoxes > 0 && <span className="lb-tab-badge">{totalBoxes}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* ─── CONTENT ─── */}
      <div className="lb-content">
        {loading ? (
          <div className="lb-skeleton-grid">
            {[...Array(6)].map((_, i) => <div key={i} className="lb-skeleton" />)}
          </div>
        ) : (
          <>
            {tab === 'collection' && (
              <CollectionView
                collections={collectionsCards}
                onSell={sellCard}
                sellingId={sellingId}
                onCardClick={(card, quantity, userCardId) => setZoomedCard({ card, quantity, userCardId })}
                activeCollection={activeCardsColl}
                setActiveCollection={setActiveCardsColl}
              />
            )}
            {tab === 'stickers' && (
              <CollectionView
                collections={collectionsStickers}
                onSell={sellCard}
                sellingId={sellingId}
                onCardClick={(card, quantity, userCardId) => setZoomedCard({ card, quantity, userCardId })}
                activeCollection={activeStickersColl}
                setActiveCollection={setActiveStickersColl}
                emptyLabel="sticker"
              />
            )}
            {tab === 'boxes' && (
              <BoxesView groupedList={groupedList} opening={opening} onOpen={openBox} onSwitchToShop={() => setTab('shop')} />
            )}
            {tab === 'shop' && (
              <ShopView types={types} user={user} buyingId={buyingId} onBuy={buyBox} />
            )}
          </>
        )}
      </div>

      {/* ─── REVEAL OVERLAY ─── */}
      {opening !== null && (
        <div className="lb-overlay" onClick={revealed ? closeReveal : undefined}>
          <div className="lb-overlay-bg" />
          {phase === 'shaking' && (
            <div className="lb-stage lb-stage-shaking">
              <div className="lb-stage-rays" />
              <div className="lb-stage-box">📦</div>
              <div className="lb-stage-text">Ouverture en cours…</div>
            </div>
          )}
          {revealed && (
            <div
              className={`lb-stage lb-stage-revealed lb-r-${revealed.rarity}`}
              onClick={e => e.stopPropagation()}
              style={{ '--rc': RARITY_META[revealed.rarity].color }}
            >
              <div className="lb-burst" />
              <div className="lb-reveal-rarity">{RARITY_META[revealed.rarity].label.toUpperCase()}</div>
              <div className="lb-reveal-card-wrap">
                <TcgCard card={revealed} size="lg" />
              </div>
              <div className="lb-reveal-name">{revealed.name}</div>
              <button className="lb-btn-primary lb-btn-continue" onClick={closeReveal}>
                Continuer <span className="lb-btn-shimmer" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* ─── ZOOM MODAL ─── */}
      {zoomedCard && (
        <TcgCardModal
          card={zoomedCard.card}
          quantity={zoomedCard.quantity}
          userCardId={zoomedCard.userCardId}
          equippedTitleId={user?.equipped_title_id}
          onTitleChange={handleTitleChange}
          onClose={() => setZoomedCard(null)}
        />
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════════════════ */
/* SUB-VIEWS                                                   */
/* ════════════════════════════════════════════════════════════ */

function CollectionView({ collections, onSell, sellingId, onCardClick, activeCollection, setActiveCollection, emptyLabel = 'carte' }) {
  if (!collections || collections.length === 0 || collections.every(c => c.total === 0)) {
    return (
      <div className="lb-empty">
        <div className="lb-empty-icon">🎴</div>
        <div className="lb-empty-title">Aucune {emptyLabel} disponible</div>
        <div className="lb-empty-sub">Le catalogue se remplira au fil des collections sorties.</div>
      </div>
    )
  }

  const totalAll = collections.reduce((s, c) => s + c.total, 0)
  const ownedAll = collections.reduce((s, c) => s + c.owned, 0)

  const current = activeCollection === null
    ? null
    : collections.find(c => (c.name || '__none__') === activeCollection)

  return (
    <div className="lb-collections">
      <div className="lb-coll-tabs">
        <button
          className={`lb-coll-tab ${activeCollection === null ? 'active' : ''}`}
          onClick={() => setActiveCollection(null)}
        >
          Toutes <span className="lb-coll-tab-count">{ownedAll}/{totalAll}</span>
        </button>
        {collections.map(c => {
          const key = c.name || '__none__'
          return (
            <button
              key={key}
              className={`lb-coll-tab ${activeCollection === key ? 'active' : ''}`}
              onClick={() => setActiveCollection(key)}
            >
              {c.name || 'Sans collection'} <span className="lb-coll-tab-count">{c.owned}/{c.total}</span>
            </button>
          )
        })}
      </div>

      {current ? (
        <CollectionBlock collection={current} onSell={onSell} sellingId={sellingId} onCardClick={onCardClick} />
      ) : (
        collections.map((c, i) => (
          <CollectionBlock key={(c.name || 'sans') + i} collection={c} onSell={onSell} sellingId={sellingId} onCardClick={onCardClick} />
        ))
      )}
    </div>
  )
}

function CollectionBlock({ collection, onSell, sellingId, onCardClick }) {
  const pct = collection.total === 0 ? 0 : Math.round((collection.owned / collection.total) * 100)
  return (
    <section className="lb-coll">
      <header className="lb-coll-head">
        <div>
          <div className="lb-coll-eyebrow">COLLECTION</div>
          <h3 className="lb-coll-name">{collection.name || 'Sans collection'}</h3>
        </div>
        <div className="lb-coll-progress">
          <div className="lb-coll-count">{collection.owned}<span className="lb-coll-total">/{collection.total}</span></div>
          <div className="lb-coll-bar">
            <div className="lb-coll-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="lb-coll-pct">{pct}%</div>
        </div>
      </header>

      <div className="lb-coll-grid">
        {collection.cards.map(entry => (
          <CardSlot key={entry.card.id} entry={entry} onSell={onSell} sellingId={sellingId} onCardClick={onCardClick} />
        ))}
      </div>
    </section>
  )
}

function CardSlot({ entry, onSell, sellingId, onCardClick }) {
  const { card, owned, quantity, user_card_id, equipped, equipped_slot } = entry
  const isSelling = sellingId === user_card_id
  const isEquipped = equipped || equipped_slot
  const isLast = owned && quantity <= 1
  const resale = RARITY_META[card.rarity]?.resale ?? 0

  return (
    <div className={`lb-slot lb-slot-${card.rarity} ${owned ? 'owned' : 'locked'}`}>
      <div
        className="lb-slot-card"
        onClick={owned ? () => onCardClick(card, quantity, user_card_id) : undefined}
      >
        <TcgCard card={card} size="sm" minimal />
        {!owned && <div className="lb-slot-lock-overlay">🔒</div>}
      </div>

      {owned ? (
        <div className="lb-slot-footer">
          <div className="lb-slot-qty-wrap">
            <span className="lb-slot-qty-val">×{quantity}</span>
            {isEquipped && <span className="lb-slot-eq-dot" title="Équipée" />}
          </div>
          <button
            className="lb-slot-sell"
            disabled={isSelling || (isLast && isEquipped)}
            onClick={() => onSell(user_card_id, card.name, card.rarity)}
            title={isLast && isEquipped ? "Déséquipe avant de vendre" : `Revendre +${resale}`}
          >
            {isSelling ? '…' : <><span className="lb-slot-sell-icon">⛁</span>{resale}</>}
          </button>
        </div>
      ) : (
        <div className="lb-slot-locked">Non obtenue</div>
      )}
    </div>
  )
}

function BoxesView({ groupedList, opening, onOpen, onSwitchToShop }) {
  if (groupedList.length === 0) {
    return (
      <div className="lb-empty">
        <div className="lb-empty-icon">📦</div>
        <div className="lb-empty-title">Aucune caisse pour le moment</div>
        <div className="lb-empty-sub">File à la boutique pour en récupérer une.</div>
        <button className="lb-btn-primary lb-empty-cta" onClick={onSwitchToShop}>
          Aller à la boutique <span className="lb-btn-shimmer" />
        </button>
      </div>
    )
  }
  return (
    <div className="lb-boxes-grid">
      {groupedList.map(g => (
        <div key={g.id} className="lb-box-card">
          <div className="lb-box-img-wrap">
            {g.image_url
              ? <img src={g.image_url} alt={g.name} referrerPolicy="no-referrer" />
              : <div className="lb-box-placeholder">📦</div>}
            <div className="lb-box-count-badge">×{g.count}</div>
          </div>
          <div className="lb-box-body">
            <div className="lb-box-name">{g.name}</div>
            {g.description && <div className="lb-box-desc">{g.description}</div>}
            <div className="lb-box-rates">
              {['common','rare','epic','legendary'].map(r => (
                <div key={r} className="lb-rate" style={{ '--rc': RARITY_META[r].color }}>
                  <span className="lb-rate-dot" />
                  <span className="lb-rate-val">{g.drop_rates[r]}%</span>
                </div>
              ))}
            </div>
            <button
              className="lb-btn-primary"
              disabled={opening === g.boxes[0].id}
              onClick={() => onOpen(g.boxes[0])}
            >
              {opening === g.boxes[0].id ? "Ouverture…" : "Ouvrir une caisse"}
              <span className="lb-btn-shimmer" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function ShopView({ types, user, buyingId, onBuy }) {
  if (types.length === 0) {
    return (
      <div className="lb-empty">
        <div className="lb-empty-icon">🏷</div>
        <div className="lb-empty-title">Boutique vide</div>
        <div className="lb-empty-sub">Aucune caisse en vente pour le moment.</div>
      </div>
    )
  }
  return (
    <>
      <div className="lb-shop-section-title">📦 Caisses</div>
      <div className="lb-shop-grid">
        {types.map(t => {
          const cantAfford = user?.coins != null && t.price_coins != null && user.coins < t.price_coins
          return (
            <div key={t.id} className="lb-shop-card">
              <div className="lb-shop-glow" />
              <div className="lb-shop-img-wrap">
                {t.image_url
                  ? <img src={t.image_url} alt={t.name} referrerPolicy="no-referrer" />
                  : <div className="lb-shop-placeholder">📦</div>}
              </div>
              <div className="lb-shop-body">
                <div className="lb-shop-name">{t.name}</div>
                {t.description && <div className="lb-shop-desc">{t.description}</div>}
                <div className="lb-shop-rates">
                  {['common','rare','epic','legendary'].map(r => (
                    <div key={r} className="lb-rate-bar" style={{ '--rc': RARITY_META[r].color }}>
                      <div className="lb-rate-bar-label">
                        <span className="lb-rate-dot" />
                        <span>{RARITY_META[r].label}</span>
                      </div>
                      <div className="lb-rate-bar-track">
                        <div className="lb-rate-bar-fill" style={{ width: `${t.drop_rates[r]}%` }} />
                      </div>
                      <div className="lb-rate-bar-val">{t.drop_rates[r]}%</div>
                    </div>
                  ))}
                </div>
                <button
                  className="lb-btn-buy"
                  disabled={!t.price_coins || cantAfford || buyingId === t.id}
                  onClick={() => onBuy(t)}
                >
                  {!t.price_coins
                    ? "Non achetable"
                    : buyingId === t.id
                      ? "Achat…"
                      : cantAfford
                        ? "Coins insuffisants"
                        : <><span className="lb-coin">⛁</span> {t.price_coins.toLocaleString()}</>
                  }
                  <span className="lb-btn-shimmer" />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="lb-shop-section-title">🛒 Achat à l'unité</div>
      <div className="lb-empty lb-empty-soft">
        <div className="lb-empty-icon">🚧</div>
        <div className="lb-empty-title">Bientôt disponible</div>
        <div className="lb-empty-sub">Tu pourras acheter des cartes individuellement ici.</div>
      </div>
    </>
  )
}