import { useState } from 'react'
import { Settings as SettingsIcon, Server, Shield, Zap, Info, LogOut } from 'lucide-react'
import { api } from '../api/client'
import SesAyari from '../components/SesAyari'

const STACK = [
  { label: 'Frontend', value: 'React 18 + Vite + Tailwind CSS' },
  { label: 'Grafikler', value: 'Recharts' },
  { label: 'İkonlar', value: 'Lucide React' },
  { label: 'Backend', value: 'Python 3.11 + FastAPI' },
  { label: 'Veritabanı', value: 'SQLite (WAL mode)' },
  { label: 'AI / NLP', value: 'Groq — llama-3.3-70b-versatile' },
  { label: 'Ses', value: 'Groq Whisper — whisper-large-v3' },
  { label: 'Görsel', value: 'Groq — qwen/qwen3.6-27b' },
  { label: 'Seslendirme', value: 'ElevenLabs — eleven_multilingual_v2' },
  { label: 'Deploy', value: 'Oracle Cloud VM (systemd + Caddy)' },
]

export default function Settings() {
  const apiUrl = import.meta.env.VITE_API_URL || '(aynı adres — istekler panelin sunucusuna gidiyor)'
  const [loggingOut, setLoggingOut] = useState(false)

  async function logout() {
    setLoggingOut(true)
    try {
      await api.logout()
    } finally {
      // Çerez silindi; sayfayı yenilemek en temiz sıfırlama
      window.location.reload()
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <SettingsIcon className="text-slate-400" size={22} />
          Ayarlar
        </h1>
        <p className="text-slate-500 text-sm mt-1">PRISM Hub yapılandırması</p>
      </div>

      {/* API Config */}
      <div className="glass-card p-5 space-y-4">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          <Server size={15} className="text-purple-400" />
          API Bağlantısı
        </h2>
        <div>
          <label className="block text-xs text-slate-600 mb-1.5">VITE_API_URL</label>
          <div className="rounded-xl px-4 py-3 font-mono text-sm text-slate-300 break-all"
            style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)' }}>
            {apiUrl}
          </div>
          <p className="text-xs text-slate-700 mt-1.5">
            Değiştirmek için frontend/.env dosyasındaki VITE_API_URL güncellenir ve panel yeniden derlenir.
          </p>
        </div>
      </div>

      <SesAyari />

      {/* Tech Stack */}
      <div className="glass-card p-5">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2 mb-4">
          <Zap size={15} className="text-amber-400" />
          Teknoloji Stack
        </h2>
        <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          {STACK.map(({ label, value }) => (
            <div key={label} className="flex justify-between items-center py-2.5">
              <span className="text-slate-500 text-sm">{label}</span>
              <span className="text-slate-300 text-sm text-right">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Security */}
      <div className="glass-card p-5 space-y-3">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          <Shield size={15} className="text-green-400" />
          Güvenlik
        </h2>
        <p className="text-slate-400 text-sm leading-relaxed">
          Telegram bot sadece yetkili{' '}
          <code className="text-purple-400 text-xs px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(167,139,250,0.1)' }}>
            TELEGRAM_CHAT_ID
          </code>{' '}
          sahibine yanıt verir.
        </p>
        <p className="text-slate-400 text-sm leading-relaxed">
          Panele parolayla giriş yapılır. Oturum bileti <strong className="text-slate-200">HttpOnly</strong>{' '}
          çerezde tutulur — JavaScript okuyamaz ve JS paketinde gizli anahtar bulunmaz.
        </p>
        <button onClick={logout} disabled={loggingOut} className="btn-secondary w-full mt-1">
          <LogOut size={15} />
          {loggingOut ? 'Çıkılıyor...' : 'Oturumu kapat'}
        </button>
      </div>

      {/* About */}
      <div className="glass-card p-5">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2 mb-3">
          <Info size={15} className="text-blue-400" />
          Hakkında
        </h2>
        <p className="text-slate-400 text-sm leading-relaxed">
          <strong className="text-slate-200">PRISM Hub</strong> — Eyüp Gök'ün kişisel AI asistan projesi.
          Telegram üzerinden doğal Türkçe dille hatırlatıcı, not, harcama ve hava durumu yönetimi.
        </p>
        <p className="text-slate-700 text-xs mt-3">v1.0.0</p>
      </div>
    </div>
  )
}
