import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Login.css'
import api from '../../api/client'
import useAuthStore from '../../store/auth'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = k => e => { setForm(f => ({ ...f, [k]: e.target.value })); setError('') }

  const submit = async e => {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const { data } = await api.post('/auth/login', form)
      login({ username: data.username, coins: data.coins, is_admin: data.is_admin }, data.token)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Identifiants incorrects')
    } finally { setLoading(false) }
  }

  return (
    <div className="auth-page">
      {/* ─── GLOWS ─── */}
      <div className="auth-glow auth-glow-1" />
      <div className="auth-glow auth-glow-2" />
      <div className="auth-glow auth-glow-3" />

      {/* ─── IMAGES FLOTTANTES ─── */}
      <img src="/logo.png"        className="auth-float auth-float-1" alt="" />
      <img src="/teemo1_png.png"  className="auth-float auth-float-2" alt="" />
      <img src="/teemo2.png"      className="auth-float auth-float-3" alt="" />
      <img src="/jungle1.webp"    className="auth-float auth-float-4" alt="" />

      {/* ─── CARD ─── */}
      <div className="auth-card">
        <div className="auth-logo" onClick={() => navigate('/')}>junglegap</div>

        <h1 className="auth-title">Connexion</h1>
        <p className="auth-sub">Content de te revoir.</p>

        <form onSubmit={submit}>
          <div className="auth-fields">
            <div className="auth-field">
              <label className="auth-label">Email</label>
              <input
                className="auth-input"
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={set('email')}
                required
                autoComplete="email"
              />
            </div>
            <div className="auth-field">
              <label className="auth-label">Mot de passe</label>
              <input
                className="auth-input"
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={set('password')}
                required
                autoComplete="current-password"
              />
            </div>
          </div>

          {error && <p className="auth-error" style={{ marginTop: 14 }}>{error}</p>}

          <button className="auth-btn btn-green" type="submit" disabled={loading} style={{ marginTop: 20 }}>
            {loading
              ? <><span className="auth-spinner" /><span>Connexion…</span></>
              : <><span>Se connecter</span><span className="btn-shimmer" /></>
            }
          </button>
        </form>

        <p className="auth-footer">
          Pas encore de compte ?{' '}
          <Link to="/register" className="auth-link">S'inscrire</Link>
        </p>
      </div>
    </div>
  )
}