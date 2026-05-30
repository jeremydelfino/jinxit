import './DraftHeader.css'
import { PHASE_LABELS, SIDE_LABELS } from '../../constants'

export default function DraftHeader({ phase, step, currentTurn, userSide, timer, isUserTurn, assignMode = false }) {
  const phaseLabel = PHASE_LABELS[phase] || phase
  const turnSide   = currentTurn?.side
  const turnAction = currentTurn?.action === 'ban' ? 'BAN' : 'PICK'

  return (
    <div className="cdh">

      <div className="cdh-left">
        <div className="cdh-phase">{phaseLabel}</div>
        <div className="cdh-step">{assignMode ? 'Phase finale' : `Étape ${Math.min(step + 1, 20)} / 20`}</div>
      </div>

      <div className={`cdh-center ${assignMode || isUserTurn ? 'user' : 'bot'}`}>
        <div className="cdh-actor">
          {assignMode ? '✦ ASSIGNE TES RÔLES' : (isUserTurn ? '✦ TON TOUR' : '⏳ Le bot réfléchit…')}
        </div>
        {!assignMode && (
          <div className="cdh-action">
            <span className={`cdh-side-badge cdh-side-${(turnSide || '').toLowerCase()}`}>
              {SIDE_LABELS[turnSide] || '—'}
            </span>
            <span className={`cdh-action-badge cdh-action-${(currentTurn?.action || 'ban').toLowerCase()}`}>
              {turnAction}
            </span>
          </div>
        )}
      </div>

      <div className="cdh-right">
        {timer !== null && (
          <div className={`cdh-timer ${timer <= 5 ? 'urgent' : ''}`}>
            <div className="cdh-timer-num">{timer}</div>
            <div className="cdh-timer-label">sec</div>
          </div>
        )}
        <div className="cdh-userside">
          <div className="cdh-userside-label">Tu joues</div>
          <div className={`cdh-userside-val cdh-side-${userSide.toLowerCase()}`}>
            {SIDE_LABELS[userSide]}
          </div>
        </div>
      </div>

    </div>
  )
}