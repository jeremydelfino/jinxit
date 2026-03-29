import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Register.css'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

const REGIONS = [
  { id: 'EUW',  flag: '🇪🇺' },
  { id: 'EUNE', flag: '🌍'  },
  { id: 'NA',   flag: '🇺🇸' },
  { id: 'KR',   flag: '🇰🇷' },
  { id: 'BR',   flag: '🇧🇷' },
  { id: 'JP',   flag: '🇯🇵' },
  { id: 'TR',   flag: '🇹🇷' },
  { id: 'OCE',  flag: '🇦🇺' },
]

const STEPS = ['Compte', 'Riot ID', 'Vérifier']

function Stepper({ current }) {
  return (
    <div className="reg-stepper">
      {STEPS.map((label, i) => (
        <div className="reg-si" key={i}>
          <div className={`reg-dot ${i < current ? 'done' : ''} ${i === current ? 'active' : ''}`}>
            {i < current ? '✓' : i + 1}
          </div>
          <span className={`reg-label ${i === current ? 'active' : ''}`}>{label}</span>
          {i < STEPS.length - 1 && <div className={`reg-line ${i < current ? 'done' : ''}`} />}
        </div>
      ))}
    </div>
  )
}

function getStrength(p) {
  if (!p) return null
  if (p.length < 6) return { label: 'Faible', c: 'w', pct: 30 }
  if (p.length < 10 || !/[A-Z]/.test(p) || !/[0-9]/.test(p)) return { label: 'Moyen', c: 'm', pct: 62 }
  return { label: 'Fort', c: 's', pct: 100 }
}

export default function Register() {
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const [step, setStep]       = useState(0)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const [acc, setAcc] = useState({ username: '', email: '', password: '', confirm: '' })
  const setA = k => e => { setAcc(a => ({ ...a, [k]: e.target.value })); setError('') }
  const str = getStrength(acc.password)

  const [region, setRegion] = useState('')
  const [riotId, setRiotId] = useState('')

  const [riotData, setRiotData]   = useState(null)
  const [verifying, setVerifying] = useState(false)

  const go0 = e => {
    e.preventDefault(); setError('')
    if (acc.password !== acc.confirm) return setError('Les mots de passe ne correspondent pas')
    if (acc.password.length < 8) return setError('Minimum 8 caractères')
    setStep(1)
  }

  const go1 = async e => {
    e.preventDefault(); setError('')
    if (!region) return setError('Sélectionne ta région')
    const parts = riotId.trim().split('#')
    if (parts.length !== 2 || !parts[0] || !parts[1]) return setError('Format : GameName#TAG')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/register/init-riot', {
        email: acc.email, game_name: parts[0].trim(),
        tag_line: parts[1].trim(), region,
      })
      setRiotData(data); setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Riot ID introuvable')
    } finally { setLoading(false) }
  }

  const verify = async () => {
    setError(''); setVerifying(true)
    try {
      const { data } = await api.post('/auth/register/complete', {
        username: acc.username, email: acc.email, password: acc.password,
        game_name: riotData.game_name, tag_line: riotData.tag_line,
        region, expected_icon_id: riotData.icon_id,
      })
      login({ username: data.username, coins: data.coins }, data.token)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Mauvaise icône, réessaie')
    } finally { setVerifying(false) }
  }

  return (
    <div className="auth-page">
      <div className="auth-glow auth-glow-1" />
      <div className="auth-glow auth-glow-2" />

      <div className="auth-card" style={{ maxWidth: step === 2 ? 420 : 400 }}>
        <div className="auth-logo" onClick={() => navigate('/')}>junglegap</div>
        <Stepper current={step} />

        {/* ── STEP 0 ── */}
        {step === 0 && <>
          <h1 className="auth-title">Créer un compte</h1>
          <p className="auth-sub">3 étapes, c'est rapide.</p>

          <div className="auth-bonus">
            <div className="bonus-dot" />
            <span>500 coins offerts à l'inscription</span>
          </div>

          <form onSubmit={go0}>
            <div className="auth-fields">
              <div className="auth-field">
                <label className="auth-label">Pseudo</label>
                <input className="auth-input" type="text" placeholder="TonPseudo"
                  value={acc.username} onChange={setA('username')}
                  required minLength={3} maxLength={20} autoComplete="username" />
              </div>
              <div className="auth-field">
                <label className="auth-label">Email</label>
                <input className="auth-input" type="email" placeholder="you@example.com"
                  value={acc.email} onChange={setA('email')} required autoComplete="email" />
              </div>
              <div className="auth-field">
                <label className="auth-label">Mot de passe</label>
                <input className="auth-input" type="password" placeholder="••••••••"
                  value={acc.password} onChange={setA('password')} required autoComplete="new-password" />
                {str && (
                  <div className="strength-row">
                    <div className="strength-track">
                      <div className={`strength-fill sf-${str.c}`} style={{ width: `${str.pct}%` }} />
                    </div>
                    <span className={`strength-label sl-${str.c}`}>{str.label}</span>
                  </div>
                )}
              </div>
              <div className="auth-field">
                <label className="auth-label">Confirmation</label>
                <input
                  className={`auth-input ${acc.confirm && acc.confirm !== acc.password ? 'err' : ''}`}
                  type="password" placeholder="••••••••"
                  value={acc.confirm} onChange={setA('confirm')} required autoComplete="new-password" />
              </div>
            </div>

            {error && <p className="auth-error" style={{ marginTop: 12 }}>{error}</p>}

            <button className="auth-btn btn-cyan" type="submit" style={{ marginTop: 20 }}>
              Continuer <span className="btn-shimmer" />
            </button>
          </form>

          <p className="auth-footer">
            Déjà un compte ? <Link to="/login" className="auth-link">Se connecter</Link>
          </p>
        </>}

        {/* ── STEP 1 ── */}
        {step === 1 && <>
          <h1 className="auth-title">Riot ID</h1>
          <p className="auth-sub">Liaison obligatoire pour parier sur les parties live.</p>

          <form onSubmit={go1}>
            <div className="auth-fields">
              <div className="auth-field">
                <label className="auth-label">Région</label>
                <div className="reg-regions">
                  {REGIONS.map(r => (
                    <button key={r.id} type="button"
                      className={`reg-region ${region === r.id ? 'r-on' : ''}`}
                      onClick={() => { setRegion(r.id); setError('') }}>
                      <span className="reg-flag">{r.flag}</span>
                      <span className="reg-id">{r.id}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="auth-field">
                <label className="auth-label">Riot ID</label>
                <input className="auth-input" type="text" placeholder="GameName#TAG"
                  value={riotId} onChange={e => { setRiotId(e.target.value); setError('') }} required />
              </div>
            </div>

            {error && <p className="auth-error" style={{ marginTop: 12 }}>{error}</p>}

            <div className="reg-nav" style={{ marginTop: 20 }}>
              <button type="button" className="btn-ghost" onClick={() => { setStep(0); setError('') }}>
                Retour
              </button>
              <button className="auth-btn btn-cyan" type="submit" disabled={loading}>
                {loading
                  ? <><span className="auth-spinner" /><span>Vérification…</span></>
                  : <><span>Continuer</span><span className="btn-shimmer" /></>
                }
              </button>
            </div>
          </form>
        </>}

        {/* ── STEP 2 ── */}
        {step === 2 && riotData && <>
          <h1 className="auth-title">Vérification</h1>
          <p className="auth-sub">Équipe cette icône dans LoL puis reviens ici.</p>

          <div className="verify-wrap">
            <div className="verify-steps">
              {[
                { n:1, t:'Ouvre League of Legends', s:'Lance le client' },
                { n:2, t:'Profil → Icône',          s:'Paramètres invocateur' },
                { n:3, t:`Équipe l'icône #${riotData.icon_id}`, s:'Puis sauvegarde', cur:true },
                { n:4, t:'Clique sur Vérifier',     s:'Check en temps réel' },
              ].map(row => (
                <div key={row.n} className={`v-row ${row.cur ? 'cur' : ''}`}>
                  <div className="v-num">{row.n}</div>
                  <div className="v-txt">
                    <strong>{row.t}</strong>
                    <span>{row.s}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="verify-icon-col">
              <img className="v-img" src={riotData.icon_url} alt={`icône ${riotData.icon_id}`} />
              <span className="v-badge">#{riotData.icon_id}</span>
              <p className="v-name">
                {riotData.game_name}<span className="v-tag">#{riotData.tag_line}</span>
              </p>
            </div>
          </div>

          {error && <p className="auth-error">{error}</p>}

          <div className="reg-nav" style={{ marginTop: 16 }}>
            <button type="button" className="btn-ghost" onClick={() => { setStep(1); setError('') }}>
              Retour
            </button>
            <button className="auth-btn btn-green" onClick={verify} disabled={verifying} style={{ flex: 2 }}>
              {verifying
                ? <><span className="auth-spinner" /><span>Vérification…</span></>
                : <><span>Vérifier et créer mon compte</span><span className="btn-shimmer" /></>
              }
            </button>
          </div>

          <p className="verify-tip">Sauvegarde l'icône dans LoL avant de cliquer</p>
        </>}
      </div>
    </div>
  )
}