import { Home, Bell, FileText, DollarSign, Wallet, Settings, Sparkles } from 'lucide-react'

// Tailwind sınıf adlarını kaynak dosyada birebir arar — `stagger-${i}` gibi
// birleştirilmiş adları göremez ve o kuralları çıktıdan siler. O yüzden düz liste.
const STAGGER = ['stagger-1', 'stagger-2', 'stagger-3', 'stagger-4', 'stagger-5', 'stagger-6']

const NAV = [
  { id: 'dashboard', label: 'Panel', icon: Home },
  { id: 'reminders', label: 'Hatırlatıcılar', icon: Bell },
  { id: 'notes', label: 'Notlar', icon: FileText },
  { id: 'expenses', label: 'Harcamalar', icon: DollarSign },
  { id: 'budget', label: 'Bütçe', icon: Wallet },
  { id: 'settings', label: 'Ayarlar', icon: Settings },
]

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside
      className="hidden md:flex flex-col w-64 h-screen fixed left-0 top-0 z-20 border-r"
      style={{ background: 'var(--bg)', borderColor: 'var(--border)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-6">
        <div
          className="w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 animate-pulse-glow"
          style={{ background: 'linear-gradient(135deg, var(--accent), var(--accent-deep))' }}
        >
          <Sparkles size={19} className="text-white" />
        </div>
        <div>
          <p className="font-display font-bold text-xl tracking-tight leading-none text-white">
            PRISM
          </p>
          <p className="text-[10px] mt-1 tracking-[0.18em] uppercase" style={{ color: 'var(--text-faint)' }}>
            Kişisel Asistan
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        <p className="px-4 pb-2 text-[10px] tracking-[0.18em] uppercase" style={{ color: 'var(--text-faint)' }}>
          Menü
        </p>
        {NAV.map(({ id, label, icon: Icon }, i) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`nav-item animate-fade-up ${STAGGER[i]} w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium ${
              active === id ? 'active' : ''
            }`}
            style={active === id ? undefined : { color: 'var(--text-soft)' }}
          >
            <Icon size={18} />
            {label}
            {active === id && (
              <span
                className="ml-auto h-1.5 w-1.5 rounded-full animate-pulse-glow"
                style={{ background: 'var(--accent-bright)' }}
              />
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <p className="text-xs" style={{ color: 'var(--text-soft)' }}>Eyüp Gök</p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>PRISM v1.0</p>
      </div>
    </aside>
  )
}
