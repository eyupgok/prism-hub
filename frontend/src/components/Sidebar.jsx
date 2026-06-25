import { Home, Bell, FileText, DollarSign, Settings, Zap } from 'lucide-react'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: Home },
  { id: 'reminders', label: 'Hatırlatıcılar', icon: Bell },
  { id: 'notes', label: 'Notlar', icon: FileText },
  { id: 'expenses', label: 'Harcamalar', icon: DollarSign },
  { id: 'settings', label: 'Ayarlar', icon: Settings },
]

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="hidden md:flex flex-col w-64 h-screen fixed left-0 top-0 z-20 border-r"
      style={{ background: '#0d0d17', borderColor: 'rgba(109,40,217,0.2)' }}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-6 border-b"
        style={{ borderColor: 'rgba(109,40,217,0.15)' }}>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #7c3aed, #4c1d95)' }}>
          <Zap size={18} className="text-white" />
        </div>
        <div>
          <p className="text-white font-bold text-lg tracking-tight leading-none">PRISM</p>
          <p className="text-purple-400 text-xs mt-0.5">Kişisel AI Hub</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-150 ${
              active === id
                ? 'text-purple-300'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
            style={active === id ? {
              background: 'rgba(124,58,237,0.15)',
              border: '1px solid rgba(124,58,237,0.3)',
            } : {}}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t" style={{ borderColor: 'rgba(109,40,217,0.15)' }}>
        <p className="text-xs text-slate-500">Eyüp Gök</p>
        <p className="text-xs text-slate-700 mt-0.5">PRISM v1.0</p>
      </div>
    </aside>
  )
}
