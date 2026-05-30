import './CoachDiffGame.css'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import { getGame, userAction, botTurn, assignRoles } from '../../api/coachdiff'
import { fetchDDragonData, getAllPicked } from './utils'
import { BOT_DELAY_MIN_MS, BOT_DELAY_MAX_MS, TURN_DURATION_S, ROLE_ASSIGN_DURATION_S, LANES } from './constants'

import DraftHeader  from './components/DraftHeader'
import BanRow       from './components/BanRow'
import PickColumn   from './components/PickColumn'
import ChampionGrid from './components/ChampionGrid'
import ScoreReveal  from './components/ScoreReveal'

export default function CoachDiffGame() {
  const { gameId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [game,       setGame]       = useState(null)
  const [ddragon,    setDdragon]    = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [busy,       setBusy]       = useState(false)
  const [selected,   setSelected]   = useState(null)
  const [timer,      setTimer]      = useState(null)
  const [assignment, setAssignment] = useState(null)   // [champ x5] en ordre de rôle
  const [swapFrom,   setSwapFrom]   = useState(null)
  const [assignTimer, setAssignTimer] = useState(null)

  const botTimerRef   = useRef(null)
  const tickRef       = useRef(null)
  const assignTickRef = useRef(null)
  const submitRef     = useRef(null)

  /* ─── DDragon ─── */
  useEffect(() => {
    fetchDDragonData().then(setDdragon).catch(e => console.error('DDragon fetch failed', e))
  }, [])

  /* ─── Load game ─── */
  const loadGame = useCallback(async () => {
    try {
      setGame(await getGame(gameId)); setLoading(false)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Partie introuvable'); setLoading(false)
    }
  }, [gameId])
  useEffect(() => { loadGame() }, [loadGame])

  /* ─── Reset selected au changement de tour ─── */
  useEffect(() => { setSelected(null) }, [game?.draft_state?.step])

  /* ─── Tour automatique du bot ─── */
  useEffect(() => {
    if (!game || game.status !== 'in_progress') return
    const turn = game.current_turn
    if (!turn || turn.actor !== 'BOT') return
    const delay = BOT_DELAY_MIN_MS + Math.random() * (BOT_DELAY_MAX_MS - BOT_DELAY_MIN_MS)
    botTimerRef.current = setTimeout(async () => {
      try { setBusy(true); setGame(await botTurn(game.id)) }
      catch (e) { console.error('Bot turn failed', e) }
      finally { setBusy(false) }
    }, delay)
    return () => clearTimeout(botTimerRef.current)
  }, [game])

  /* ─── Action user (pick/ban) ─── */
  const handleUserAction = useCallback(async (champion) => {
    if (busy || !game) return
    try { setBusy(true); setGame(await userAction(game.id, champion)) }
    catch (e) { alert(e?.response?.data?.detail || 'Action impossible') }
    finally { setBusy(false) }
  }, [busy, game])

  /* ─── Envoi de l'assignation ─── */
  const handleAssignRoles = useCallback(async (roleMap) => {
    if (busy || !game) return
    try { setBusy(true); setGame(await assignRoles(game.id, roleMap)) }
    catch (e) { alert(e?.response?.data?.detail || 'Assignation impossible') }
    finally { setBusy(false) }
  }, [busy, game])

  const submitAssignment = useCallback(() => {
    setAssignment(curr => {
      if (curr && curr.length === 5 && !busy) {
        const roleMap = {}
        LANES.forEach((lane, i) => { roleMap[lane] = curr[i] })
        handleAssignRoles(roleMap)
      }
      return curr
    })
  }, [busy, handleAssignRoles])
  submitRef.current = submitAssignment

  const handleSlotClick = (i) => {
    if (swapFrom === null) { setSwapFrom(i); return }
    if (swapFrom === i)    { setSwapFrom(null); return }
    setAssignment(prev => {
      const next = [...prev]
      ;[next[swapFrom], next[i]] = [next[i], next[swapFrom]]
      return next
    })
    setSwapFrom(null)
  }

  /* ─── Timer du tour user + auto-pick ─── */
  const isUserTurn = game?.status === 'in_progress' && game?.current_turn?.actor === 'USER'
  useEffect(() => {
    clearInterval(tickRef.current)
    if (!isUserTurn || !ddragon) { setTimer(null); return }
    setTimer(TURN_DURATION_S)
    tickRef.current = setInterval(() => {
      setTimer(prev => {
        if (prev === null) return null
        if (prev <= 1) {
          clearInterval(tickRef.current)
          const picked = getAllPicked(game.draft_state)
          const cands = ddragon.champions.filter(c => !picked.has(c.id))
          if (cands.length) handleUserAction(cands[Math.floor(Math.random() * cands.length)].id)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(tickRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isUserTurn, game?.draft_state?.step, ddragon])

  /* ─── Phase ROLE_ASSIGN : init + timer 30s ─── */
  useEffect(() => {
    if (game?.draft_state?.phase !== 'ROLE_ASSIGN') return
    const key = game.draft_state.user_side.toLowerCase()
    const picks = game.draft_state[key]?.picks || []
    setAssignment(prev => prev ?? picks.slice(0, 5))
    setAssignTimer(ROLE_ASSIGN_DURATION_S)
    clearInterval(assignTickRef.current)
    assignTickRef.current = setInterval(() => {
      setAssignTimer(prev => {
        if (prev === null) return null
        if (prev <= 1) { clearInterval(assignTickRef.current); submitRef.current?.(); return 0 }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(assignTickRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game?.draft_state?.phase])

  /* ─── Guards ─── */
  if (!user)              return <div className="cdg-loading">Connecte-toi pour jouer</div>
  if (loading || !ddragon) return <div className="cdg-loading">Chargement…</div>
  if (error) return (
    <div className="cdg-error">
      <div>{error}</div>
      <button onClick={() => navigate('/games/coachdiff')}>Retour</button>
    </div>
  )
  if (!game) return null

  const phase = game.draft_state?.phase
  const state = game.draft_state

  if (game.status === 'finished') {
    return <ScoreReveal game={game} version={ddragon.version} />
  }

  /* ─── Draft ─── */
/* ─── Board (draft + assignation sur la même page) ─── */
  const turn = game.current_turn
  const pickedSet = getAllPicked(state)
  const actionLabel = turn?.action === 'ban' ? 'Ban' : 'Pick'

  const isAssign = phase === 'ROLE_ASSIGN'
  const userSide = state.user_side
  const userKey  = userSide.toLowerCase()
  const assignList = assignment || (state[userKey]?.picks || []).slice(0, 5)

  const colProps = (side) => ({
    side,
    picks: state[side.toLowerCase()].picks,
    version: ddragon.version,
    isCurrentSlot: !isAssign && turn?.action === 'pick' && turn?.side === side,
    assignMode: isAssign && userSide === side,
    assignment: userSide === side ? assignList : null,
    swapFrom:   userSide === side ? swapFrom : null,
    onSlotClick: userSide === side ? handleSlotClick : null,
  })

  return (
    <div className="cdg-page">
      <DraftHeader
        phase={phase} step={state.step} currentTurn={turn} userSide={userSide}
        timer={isAssign ? null : (isUserTurn ? timer : null)}
        isUserTurn={isUserTurn} assignMode={isAssign}
      />

      <div className="cdg-bans">
        <BanRow side="BLUE" bans={state.blue.bans} version={ddragon.version}
                isCurrentSlot={!isAssign && turn?.action === 'ban' && turn?.side === 'BLUE'} />
        <BanRow side="RED" bans={state.red.bans} version={ddragon.version}
                isCurrentSlot={!isAssign && turn?.action === 'ban' && turn?.side === 'RED'} />
      </div>

      <div className="cdg-board">
        <PickColumn {...colProps('BLUE')} />

        {isAssign ? (
          <div className="cdg-ac">
            <div className="cdg-ac-icon">🎯</div>
            <h3 className="cdg-ac-title">Place tes champions</h3>
            <p className="cdg-ac-hint">Clique un champion de ta colonne, puis la lane à échanger. De haut en bas : Top · Jungle · Mid · ADC · Support.</p>
            <button className="cdg-ac-validate" onClick={submitAssignment} disabled={busy}>
              {busy ? 'Validation…' : 'Valider la draft'}
            </button>
            <div className={`cdg-ac-timer ${(assignTimer ?? 30) <= 5 ? 'urgent' : ''}`}>{assignTimer ?? 30}s</div>
          </div>
        ) : (
          <ChampionGrid
            champions={ddragon.champions} version={ddragon.version} pickedSet={pickedSet}
            selected={selected} onSelect={setSelected}
            onLockIn={() => selected && handleUserAction(selected)}
            disabled={!isUserTurn || busy} actionLabel={actionLabel}
          />
        )}

        <PickColumn {...colProps('RED')} />
      </div>
    </div>
  )
}