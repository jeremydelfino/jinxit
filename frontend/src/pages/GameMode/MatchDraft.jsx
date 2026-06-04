import { useEffect, useState, useRef, useCallback } from 'react'
import api from '../../api/client'
import { matchStart, matchAction, matchBotTurn, matchFinish } from '../../api/gmMatch'
import { fetchDDragonData, getAllPicked } from '../CoachDiffGame/utils'
import { BOT_DELAY_MIN_MS, BOT_DELAY_MAX_MS, LANES } from '../CoachDiffGame/constants'
import DraftHeader  from '../CoachDiffGame/components/DraftHeader'
import BanRow       from '../CoachDiffGame/components/BanRow'
import PickColumn   from '../CoachDiffGame/components/PickColumn'
import MatchSim from './MatchSim'
import ChampionGrid from '../CoachDiffGame/components/ChampionGrid'
import '../CoachDiffGame/CoachDiffGame.css'
import './MatchDraft.css'

const fmt = v => (v >= 0 ? '+' : '') + v

function MatchResult({ r, opp, onExit }) {
  const win = r.result === 'WIN'
  return (
    <div className={`gm-mres ${win ? 'win' : 'loss'}`}>
      <div className="gm-mres-badge">{win ? 'VICTOIRE' : 'DÉFAITE'}</div>
      <div className="gm-mres-opp">vs {opp?.name}</div>
      <div className="gm-mres-pwin">Probabilité estimée : {Math.round(r.p_win * 100)}%</div>
      <div className="gm-mres-draft">Draft {r.draft.user} — {r.draft.opp}</div>
      <div className="gm-mres-comp">
        <span>Draft {fmt(r.components.draft)}</span>
        <span>Force {fmt(r.components.strength)}</span>
        <span>Mental {fmt(r.components.mental)}</span>
      </div>
      {win && <div className="gm-mres-reward">+🪙 {r.reward_budget.toLocaleString()}</div>}
      <button className="gm-btn-primary" onClick={onExit}>Continuer</button>
    </div>
  )
}

export default function MatchDraft({ onExit }) {
  const [g, setG]               = useState(null)
  const [ddragon, setDd]        = useState(null)
  const [loading, setLoading]   = useState(true)
  const [busy, setBusy]         = useState(false)
  const [error, setError]       = useState(null)
  const [selected, setSelected] = useState(null)
  const [assignment, setAssign] = useState(null)
  const [swapFrom, setSwapFrom] = useState(null)
  const [result, setResult]     = useState(null)
  const [players, setPlayers]   = useState(null)   // titulaires indexés par lane [TOP..SUP]
  const botRef     = useRef(null)
  const startedRef = useRef(false)
  const [simDone, setSimDone] = useState(false)

  useEffect(() => { fetchDDragonData().then(setDd).catch(() => {}) }, [])

// Roster : titulaire (nom + photo) par lane, pour l'écran d'assignation
  useEffect(() => {
    const httpsify = u => (u || '').replace(/^http:\/\//, 'https://') || null
    ;(async () => {
      try {
        const { data } = await api.get('/gm/team')
        const starters = (data.roster || []).filter(r => r.is_starter)
        setPlayers(LANES.map(lane => {
          const r = starters.find(s => (s.role_slot || s.role) === lane)
          return r ? { name: r.player?.name || '—', photo_url: httpsify(r.player?.photo_url) } : null
        }))
      } catch { setPlayers(null) }
    })()
  }, [])

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    ;(async () => {
      try { setG(await matchStart()) }
      catch (e) { setError(e?.response?.data?.detail || 'Impossible de lancer le match') }
      finally { setLoading(false) }
    })()
  }, [])

  const state      = g?.draft_state
  const turn       = g?.current_turn
  const phase      = state?.phase
  const isAssign   = phase === 'ROLE_ASSIGN'
  const isUserTurn = turn?.actor === 'USER'

  useEffect(() => { setSelected(null) }, [state?.step])

  useEffect(() => {
    if (!g || result) return
    if (!turn || turn.actor !== 'BOT') return
    const d = BOT_DELAY_MIN_MS + Math.random() * (BOT_DELAY_MAX_MS - BOT_DELAY_MIN_MS)
    botRef.current = setTimeout(async () => {
      try { setBusy(true); setG(await matchBotTurn()) }
      catch (e) { setError(e?.response?.data?.detail || 'Erreur bot') }
      finally { setBusy(false) }
    }, d)
    return () => clearTimeout(botRef.current)
  }, [g, result])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isAssign && state && !assignment) {
      const key = state.user_side.toLowerCase()
      setAssign((state[key]?.picks || []).slice(0, 5))
    }
  }, [isAssign, state, assignment])

  const doAction = useCallback(async (champ) => {
    if (busy || !champ) return
    try { setBusy(true); setG(await matchAction(champ)); setSelected(null) }
    catch (e) { setError(e?.response?.data?.detail || 'Action impossible') }
    finally { setBusy(false) }
  }, [busy])

  function clickSlot(i) {
    if (swapFrom === null) { setSwapFrom(i); return }
    setAssign(prev => {
      const next = [...prev]
      const tmp = next[swapFrom]; next[swapFrom] = next[i]; next[i] = tmp
      return next
    })
    setSwapFrom(null)
  }

  async function validate() {
    if (busy || !assignment) return
    const role_map = Object.fromEntries(LANES.map((l, i) => [l, assignment[i]]))
    try { setBusy(true); setResult(await matchFinish(role_map)) }
    catch (e) { setError(e?.response?.data?.detail || 'Validation impossible') }
    finally { setBusy(false) }
  }

  let content
  if (loading || !ddragon) {
    content = <div className="gm-draft-loading">Chargement de la draft…</div>
  } else if (error) {
    content = (
      <div className="gm-draft-loading" style={{ gap: 16 }}>
        <div className="gm-error">{error}</div>
        <button className="gm-btn-ghost" onClick={onExit}>Retour</button>
      </div>
    )
  } else if (result && result.timeline && !simDone) {
    content = <MatchSim timeline={result.timeline} userSide={result.user_side} version={ddragon.version} onDone={() => setSimDone(true)} />
  } else if (result) {
    content = <MatchResult r={result} opp={g?.opponent} onExit={onExit} />
  } else if (g && state) {
    const pickedSet = getAllPicked(state)
    const userSide  = state.user_side
    const colProps  = side => {
      const assignActive = isAssign && side === userSide
      return {
        side, picks: state[side.toLowerCase()].picks, version: ddragon.version,
        isCurrentSlot: !isAssign && turn?.action === 'pick' && turn?.side === side,
        assignMode:  assignActive,
        assignment:  assignActive ? assignment : null,
        swapFrom:    assignActive ? swapFrom : null,
        onSlotClick: assignActive ? clickSlot : null,
        players:     assignActive ? players : null,
      }
    }

    content = (
      <div className="cdg-page">
        <div className="gm-draft-top">
          <button className="gm-btn-ghost gm-tiny" onClick={onExit}>← Quitter</button>
          <div className="gm-draft-opp">
            {g.opponent?.logo_url && <img src={g.opponent.logo_url} alt="" referrerPolicy="no-referrer"
                                          onError={e => { e.target.style.display = 'none' }} />}
            <span>vs <b>{g.opponent?.name}</b> · {g.format}</span>
          </div>
        </div>

        <DraftHeader phase={phase} step={state.step} currentTurn={turn} userSide={userSide}
                     timer={null} isUserTurn={isUserTurn} assignMode={isAssign} />

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
              <p className="cdg-ac-hint">Dans ta colonne, clique un champion puis la lane où l'envoyer. Chaque slot affiche le titulaire qui jouera ce rôle.</p>
              <button className="cdg-ac-validate" disabled={busy} onClick={validate}>
                {busy ? 'Résolution…' : 'Valider la draft'}
              </button>
            </div>
          ) : (
            <ChampionGrid champions={ddragon.champions} version={ddragon.version} pickedSet={pickedSet}
                          selected={selected} onSelect={setSelected}
                          onLockIn={() => selected && doAction(selected)}
                          disabled={!isUserTurn || busy}
                          actionLabel={turn?.action === 'ban' ? 'Ban' : 'Pick'} />
          )}

          <PickColumn {...colProps('RED')} />
        </div>
      </div>
    )
  }

  return <div className="gm-draft-overlay">{content}</div>
}