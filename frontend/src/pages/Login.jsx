import { useState } from 'react'
import { Lock, Eye, EyeOff } from 'lucide-react'
import { api } from '../api/client'

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    if (!password || busy) return
    setBusy(true)
    setError('')
    try {
      await api.login(password)
      onSuccess()
    } catch (err) {
      setError(err.message || 'Giriş yapılamadı')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
            style={{
              background: 'linear-gradient(135deg, rgba(139,92,246,0.25), rgba(109,40,217,0.15))',
              border: '1px solid rgba(139,92,246,0.35)',
            }}>
            <Lock size={22} className="text-purple-300" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">PRISM</h1>
          <p className="text-slate-500 text-sm mt-1.5">Kişisel AI Asistan Hub</p>
        </div>

        <form onSubmit={submit} className="glass-card p-6 space-y-4">
          <div>
            <label htmlFor="panel-password" className="block text-xs text-slate-500 mb-2">
              Panel parolası
            </label>
            <div className="relative">
              <input
                id="panel-password"
                type={show ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field pr-11"
                placeholder="••••••••"
                autoFocus
                autoComplete="current-password"
                disabled={busy}
              />
              <button
                type="button"
                onClick={() => setShow(!show)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                aria-label={show ? 'Parolayı gizle' : 'Parolayı göster'}
              >
                {show ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-400 rounded-xl px-3 py-2.5"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary w-full" disabled={busy || !password}>
            {busy ? (
              <>
                <span className="w-4 h-4 rounded-full border-2 border-white/40 border-t-transparent animate-spin" />
                Giriş yapılıyor...
              </>
            ) : (
              'Giriş yap'
            )}
          </button>
        </form>

        <p className="text-center text-slate-700 text-xs mt-6">
          Oturum bu tarayıcıda 30 gün açık kalır.
        </p>
      </div>
    </div>
  )
}
