import { useState, useEffect } from 'react'
import api from '../../../api/client'
import MatchDraft from '../MatchDraft'

function phaseLabel(p) {
  return p === 'REGULAR' ? 'Saison régulière' : p === 'PLAYOFFS' ? 'Playoffs' : 'Terminée'
}

export default function CompetitionTab() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy]       = useState(false)
  const [error, setError]     = useState(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true); setError(null)
    try { const { data } = await api.get('/gm/season'); setData(data) }
    catch (e) { setError(e.response?.data?.detail || 'Erreur de chargement') }
    finally { setLoading(false) }
  }

  async function startSeason() {
    if (busy) return
    setBusy(true); setError(null)
    try { const { data } = await api.post('/gm/season/start'); setData(data) }
    catch (e) { setError(e.response?.data?.detail || 'Erreur') }
    finally { setBusy(false) }
  }

  if (playing) return <MatchDraft onExit={() => { setPlaying(false); load() }} />
  if (loading) return <div className="gm-content"><div className="gm-empty">Chargement…</div></div>

  const season = data?.season
  if (!season) {
    return (
      <div className="gm-content">
        {error && <div className="gm-error">{error}</div>}
        <div className="gm-comp-start">
          <div className="gm-comp-start-text">Aucune saison en cours.</div>
          <button className="gm-btn-primary" disabled={busy} onClick={startSeason}>
            {busy ? 'Création…' : 'Démarrer la saison LFL'}
          </button>
        </div>
      </div>
    )
  }

  const standings = data.standings || []
  const calendar  = data.calendar || []
  const myMatches = calendar.filter(m => m.involves_user)

  const playable = season.phase === 'REGULAR' && myMatches.some(
    m => m.matchday === season.current_matchday && m.status !== 'PLAYED'
  )

  const oppOf      = m => (m.home.is_user ? m.away : m.home)
  const userIsHome = m => m.home.is_user
  const resultOf   = m => {
    if (m.status !== 'PLAYED' || !m.winner_side) return null
    return m.winner_side === (userIsHome(m) ? 'HOME' : 'AWAY') ? 'WIN' : 'LOSS'
  }

  return (
    <div className="gm-content">
      {error && <div className="gm-error">{error}</div>}

      <div className="gm-bento">
        {/* Hero */}
        <div className="gm-tile gm-tile-wide gm-tile-hero">
          <div className="gm-hero-comp">
            <div>
              <div className="gm-comp-league">{season.league}</div>
              <div className="gm-comp-sub">Année {season.year} · Split {season.split_no} · {phaseLabel(season.phase)}</div>
            </div>
            <div className="gm-comp-md">J{season.current_matchday}<span> / {season.total_matchdays}</span></div>
            <div className="gm-hero-cta">
              {playable
                ? <button className="gm-btn-primary" onClick={() => setPlaying(true)}>Jouer ma journée</button>
                : season.phase === 'PLAYOFFS'
                  ? <span className="gm-hero-cta-sub">Playoffs — bientôt jouables</span>
                  : <span className="gm-hero-cta-sub">Journée jouée</span>}
            </div>
          </div>
        </div>

        {/* Classement */}
        <div className="gm-tile">
          <div className="gm-tile-head">Classement</div>
          <div className="gm-standings">
            <div className="gm-st-row gm-st-head">
              <span className="gm-st-rank">#</span>
              <span className="gm-st-team">Équipe</span>
              <span className="gm-st-rec">V-D</span>
              <span className="gm-st-pts">Pts</span>
            </div>
            {standings.map((s, i) => (
              <div key={i} className={`gm-st-row ${s.is_user ? 'me' : ''} ${i < 4 ? 'qualif' : ''}`}>
                <span className="gm-st-rank">{i + 1}</span>
                <span className="gm-st-team">
                  {s.logo_url && <img src={s.logo_url} alt="" referrerPolicy="no-referrer"
                                      onError={e => { e.target.style.display = 'none' }} />}
                  <b>{s.name}</b>
                </span>
                <span className="gm-st-rec">{s.wins}-{s.losses}</span>
                <span className="gm-st-pts">{s.points}</span>
              </div>
            ))}
          </div>
          <div className="gm-st-legend">Top 4 → playoffs</div>
        </div>

        {/* Calendrier */}
        <div className="gm-tile">
          <div className="gm-tile-head">Mon calendrier</div>
          <div className="gm-fixtures">
            {myMatches.map(m => {
              const opp     = oppOf(m)
              const res     = resultOf(m)
              const current = m.matchday === season.current_matchday && m.status !== 'PLAYED'
              const myScore  = userIsHome(m) ? m.score_home : m.score_away
              const oppScore = userIsHome(m) ? m.score_away : m.score_home
              return (
                <div key={m.id} className={`gm-fix ${current ? 'current' : ''} ${res ? res.toLowerCase() : ''}`}>
                  <span className="gm-fix-md">J{m.matchday}</span>
                  <span className="gm-fix-opp">
                    {opp.logo_url && <img src={opp.logo_url} alt="" referrerPolicy="no-referrer"
                                          onError={e => { e.target.style.display = 'none' }} />}
                    <b>{opp.name}</b>
                  </span>
                  <span className="gm-fix-fmt">{m.format}</span>
                  <span className="gm-fix-status">
                    {m.status === 'PLAYED'
                      ? <span className={`gm-fix-res ${res?.toLowerCase()}`}>{res === 'WIN' ? 'V' : 'D'} {myScore}-{oppScore}</span>
                      : current ? <span className="gm-fix-next">À jouer</span>
                                : <span className="gm-fix-soon">À venir</span>}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}