import './GameMode.css'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import api from '../../api/client'
import GmCard from '../../components/ui/GmCard'
import { TABS } from './constants'
import GeneralTab from './tabs/GeneralTab'
import SquadTab from './tabs/SquadTab'
import ShopTab from './tabs/ShopTab'
import CompetitionTab from './tabs/CompetitionTab'

export default function GameMode() {
  const navigate = useNavigate()
  const token = useAuthStore(s => s.token)

  const [loading, setLoading] = useState(true)
  const [data, setData]       = useState(null)
  const [needCreate, setNeed] = useState(false)
  const [name, setName]       = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError]     = useState(null)

  const [tab, setTab]         = useState('general')
  const [packs, setPacks]     = useState([])
  const [opening, setOpening] = useState(null)
  const [revealed, setRevealed] = useState(null)
  const [busyId, setBusyId]   = useState(null)

  useEffect(() => { if (!token) { navigate('/login'); return } load() }, [token])

  async function load() {
    setLoading(true); setError(null)
    try {
      const { data } = await api.get('/gm/team')
      setData(data); setNeed(false); loadPacks()
    } catch (e) {
      if (e.response?.status === 404) setNeed(true)
      else setError(e.response?.data?.detail || 'Erreur de chargement')
    } finally { setLoading(false) }
  }

  async function loadPacks() {
    try { const { data } = await api.get('/gm/packs'); setPacks(data) } catch {}
  }

  async function createTeam() {
    if (creating) return
    if (name.trim().length < 2) { setError('Nom trop court'); return }
    setCreating(true); setError(null)
    try {
      const { data } = await api.post('/gm/team', { name: name.trim() })
      setData(data); setNeed(false); loadPacks()
    } catch (e) { setError(e.response?.data?.detail || 'Erreur à la création') }
    finally { setCreating(false) }
  }

  async function patchContract(id, body) {
    if (busyId) return
    setBusyId(id); setError(null)
    try { const { data: res } = await api.patch(`/gm/contracts/${id}`, body); setData(res) }
    catch (e) { setError(e.response?.data?.detail || 'Erreur') }
    finally { setBusyId(null) }
  }

  async function sell(id) {
    if (busyId) return
    if (!window.confirm('Revendre ce joueur ?')) return
    setBusyId(id); setError(null)
    try { await api.post(`/gm/contracts/${id}/sell`); await load() }
    catch (e) { setError(e.response?.data?.detail || 'Erreur à la vente') }
    finally { setBusyId(null) }
  }

  async function openPack(pack) {
    if (opening) return
    if (data.team.budget < pack.price_budget) { setError('Budget insuffisant'); return }
    setOpening(pack.id); setError(null); setRevealed(null)
    try {
      const { data: res } = await api.post(`/gm/packs/${pack.id}/open`)
      setData(d => ({ ...d, team: { ...d.team, budget: res.budget } }))
      setRevealed(res.card); load()
    } catch (e) { setError(e.response?.data?.detail || "Erreur à l'ouverture"); setOpening(null) }
  }

  function closeReveal() { setRevealed(null); setOpening(null) }

  if (loading) return <div className="gm-loading">Chargement…</div>

  if (needCreate) return (
    <div className="gm-create">
      <div className="gm-create-box">
        <div className="gm-create-eyebrow">MYCEO</div>
        <h1 className="gm-create-title">Crée ta franchise</h1>
        <p className="gm-create-sub">Tu démarres en LFL avec 5 joueurs et 5&nbsp;000 de budget.</p>
        <input className="gm-create-input" placeholder="Nom de ton équipe" value={name} maxLength={60}
          onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && createTeam()} />
        {error && <div className="gm-error">{error}</div>}
        <button className="gm-btn-primary gm-block" disabled={creating} onClick={createTeam}>
          {creating ? 'Création…' : 'Fonder la franchise'}
        </button>
      </div>
    </div>
  )

  const { team, roster } = data
  const starters = roster.filter(r => r.is_starter)
  const bench = roster.filter(r => !r.is_starter)
  const wage = roster.reduce((s, r) => s + (r.salary || 0), 0)
  
  return (
    <div className="gm-page">
      <header className="gm-header">
        <div className="gm-header-id">
          <div className="gm-logo">{team.name.slice(0, 1).toUpperCase()}</div>
          <div>
            <h1 className="gm-team-name">{team.name}</h1>
            <span className="gm-league-badge">{team.league}</span>
          </div>
        </div>
        <div className="gm-header-stats">
          <div className="gm-hstat"><span className="gm-hstat-val gold">{team.ovr}</span><span className="gm-hstat-lbl">OVR</span></div>
          <div className="gm-hstat"><span className="gm-hstat-val">🪙 {team.budget.toLocaleString()}</span><span className="gm-hstat-lbl">Budget</span></div>
          <div className="gm-hstat"><span className="gm-hstat-val">{team.fans.toLocaleString()}</span><span className="gm-hstat-lbl">Fans</span></div>
          <div className="gm-hstat"><span className="gm-hstat-val">{team.reputation}</span><span className="gm-hstat-lbl">Réput.</span></div>
        </div>
      </header>

      <nav className="gm-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`gm-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </nav>

      {error && <div className="gm-error">{error}</div>}

      {tab === 'general' && <GeneralTab team={team} starters={starters} bench={bench} wage={wage} onGoComp={() => setTab('comp')} />}
      {tab === 'squad'   && <SquadTab starters={starters} bench={bench} busyId={busyId} onPatch={patchContract} onSell={sell} />}
      {tab === 'shop'    && <ShopTab packs={packs} budget={team.budget} opening={opening} onOpen={openPack} />}
      {tab === 'comp'    && <CompetitionTab />}

      {revealed && (
        <div className="gm-overlay" onClick={closeReveal}>
          <div className="gm-reveal" onClick={e => e.stopPropagation()}>
            <div className="gm-reveal-label">Tu as obtenu</div>
            <GmCard entry={revealed} size="lg" />
            <div className="gm-reveal-sub">Ajouté à ta réserve.</div>
            <button className="gm-btn-primary" onClick={closeReveal}>Continuer</button>
          </div>
        </div>
      )}
    </div>
  )
}