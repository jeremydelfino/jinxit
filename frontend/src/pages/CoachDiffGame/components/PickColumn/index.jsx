import './PickColumn.css'
import { getChampSplash } from '../../utils'
import { SIDE_LABELS, LANES, LANE_LABELS, LANE_ICONS } from '../../constants'

export default function PickColumn({
  side, picks, isCurrentSlot,
  assignMode = false, assignment = null, swapFrom = null, onSlotClick = null,
  players = null,
}) {
  const sideLower = side.toLowerCase()
  const list  = assignMode ? (assignment || []) : (picks || [])
  const slots = Array.from({ length: 5 }, (_, i) => list[i] || null)

  return (
    <div className={`cd-picks cd-picks-${sideLower} ${assignMode ? 'assign' : ''}`}>
      <div className={`cd-picks-header ${sideLower}`}>
        {side === 'BLUE' && <span className="cd-picks-bar blue-bar" />}
        <span className="cd-picks-label">{SIDE_LABELS[side]}</span>
        {side === 'RED' && <span className="cd-picks-bar red-bar" />}
      </div>

      <div className="cd-picks-list">
        {slots.map((champ, i) => {
          const role         = LANES[i]
          const splash       = champ ? getChampSplash(champ) : null
          const player       = players?.[i] || null
          const isActive     = !assignMode && isCurrentSlot && i === (picks?.length || 0)
          const isSwapFrom   = assignMode && swapFrom === i
          const isSwapTarget = assignMode && swapFrom !== null && swapFrom !== i && !!champ
          const clickable    = assignMode && !!champ

          return (
            <div
              key={i}
              className={[
                'cd-pick-slot', sideLower,
                champ ? 'filled' : 'empty',
                isActive ? 'active' : '',
                isSwapFrom ? 'swap-from' : '',
                isSwapTarget ? 'swap-target' : '',
                clickable ? 'clickable' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => clickable && onSlotClick?.(i)}
            >
              {champ ? (
                <>
                  {splash && (
                    <img src={splash} alt={champ} className="cd-pick-splash"
                         referrerPolicy="no-referrer" onError={e => { e.target.style.display = 'none' }} />
                  )}
                  <div className={`cd-pick-fade ${sideLower === 'blue' ? 'fade-right' : 'fade-left'}`} />
                  {assignMode && (
                    <div className="cd-pick-role">
                      <span className="cd-pick-role-ico">{LANE_ICONS[role]}</span>
                      <span className="cd-pick-role-lbl">{LANE_LABELS[role]}</span>
                    </div>
                  )}
                  {player && (
                    <div className="cd-pick-player">
                      <span className="cd-pick-player-photo">
                        <span className="cd-pick-player-ini">{(player.name || '?').slice(0, 2).toUpperCase()}</span>
                        {player.photo_url && (
                          <img src={player.photo_url} alt={player.name} referrerPolicy="no-referrer"
                               onError={e => { e.currentTarget.style.display = 'none' }} />
                        )}
                      </span>
                      <span className="cd-pick-player-name">{player.name}</span>
                    </div>
                  )}
                  <div className={`cd-pick-name ${sideLower}`}>{champ}</div>
                  {isSwapFrom   && <div className="cd-pick-swap-badge">Échanger avec…</div>}
                  {isSwapTarget && <div className="cd-pick-swap-hint">↔ {LANE_LABELS[role]}</div>}
                </>
              ) : (
                <div className="cd-pick-empty">
                  {assignMode
                    ? <span className="cd-pick-role-ico">{LANE_ICONS[role]}</span>
                    : (i + 1)}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}