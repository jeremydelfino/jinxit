import './TcgCard.css'

const RARITY_CONFIG = {
  common:    { color: '#9ca3af', label: 'Commune',     glow: '#9ca3af30' },
  rare:      { color: '#3b82f6', label: 'Rare',        glow: '#3b82f640' },
  epic:      { color: '#a855f7', label: 'Épique',      glow: '#a855f740' },
  legendary: { color: '#c89b3c', label: 'Légendaire',  glow: '#c89b3c50' },
}

const TYPE_ICON = {
  champion:   '⚔️',
  pro_player: '👑',
  meme:       '😂',
  cosmetic:   '✨',
}

function formatBoost(card) {
  if (!card.trigger_type) return null
  const pct = card.boost_type === 'percent_gain'
    ? `+${Math.round(card.boost_value * 100)}%`
    : `+${card.boost_value} coins`

  if (card.trigger_type === 'any')
    return { boost: pct, condition: 'sur tous les paris' }
  if (card.trigger_type === 'champion')
    return { boost: pct, condition: `si ${card.trigger_value} joué` }
  if (card.trigger_type === 'player')
    return { boost: pct, condition: `si ${card.trigger_value} en game` }
  if (card.trigger_type === 'mechanic')
    return { boost: pct, condition: `sur pari ${card.trigger_value}` }
  return null
}

export default function TcgCard({ card, size = 'md' }) {
  const r = RARITY_CONFIG[card.rarity] || RARITY_CONFIG.common
  const effect = formatBoost(card)

  return (
    <div className={`tcg-card tcg-${size}`} style={{ '--rc': r.color, '--rg': r.glow }}>
      <div className="tcg-inner">

        {/* ── RECTO : art de la carte ── */}
        <div className="tcg-front">
          {/* Cadre rareté en haut */}
          <div className="tcg-top-bar" />

          {/* Image */}
          <div className="tcg-art">
            {card.image_url
              ? <img src={card.image_url} alt={card.name} referrerPolicy="no-referrer" />
              : <div className="tcg-art-placeholder">{TYPE_ICON[card.type] || '🃏'}</div>
            }
            {/* Shimmer legendary */}
            {card.rarity === 'legendary' && <div className="tcg-shimmer" />}
          </div>

          {/* Footer recto */}
          <div className="tcg-front-footer">
            <div className="tcg-card-name">{card.name}</div>
            <div className="tcg-rarity-badge" style={{ color: r.color }}>{r.label}</div>
          </div>
        </div>

        {/* ── VERSO : stats & effet ── */}
        <div className="tcg-back">
          <div className="tcg-back-header">
            <div className="tcg-back-icon">{TYPE_ICON[card.type] || '🃏'}</div>
            <div className="tcg-back-name">{card.name}</div>
          </div>

          <div className="tcg-back-rarity" style={{ color: r.color, borderColor: r.color + '40', background: r.color + '12' }}>
            {r.label}
          </div>

          {effect ? (
            <div className="tcg-effect">
              <div className="tcg-effect-boost">{effect.boost}</div>
              <div className="tcg-effect-condition">{effect.condition}</div>
            </div>
          ) : (
            <div className="tcg-no-effect">Carte cosmétique</div>
          )}

          {(card.is_title || card.is_banner) && (
            <div className="tcg-cosmetic-tags">
              {card.is_title && <span className="tcg-cosm-tag">🏷 Titre</span>}
              {card.is_banner && <span className="tcg-cosm-tag">🖼 Bannière</span>}
            </div>
          )}

          {card.is_title && card.title_text && (
            <div className="tcg-title-preview">✦ {card.title_text}</div>
          )}
        </div>
      </div>
    </div>
  )
}