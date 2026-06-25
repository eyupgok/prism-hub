import { Home, Bell, FileText, DollarSign, Settings } from 'lucide-react'

const NAV = [
  { id: 'dashboard', label: 'Ana Sayfa', icon: Home },
  { id: 'reminders', label: 'Görevler', icon: Bell },
  { id: 'notes', label: 'Notlar', icon: FileText },
  { id: 'expenses', label: 'Harcama', icon: DollarSign },
  { id: 'settings', label: 'Ayarlar', icon: Settings },
]

export default function BottomNav({ active, onNavigate }) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-20 flex border-t"
      style={{
        background: 'rgba(13,13,23,0.95)',
        backdropFilter: 'blur(16px)',
        borderColor: 'rgba(109,40,217,0.2)',
      }}>
      {NAV.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onNavigate(id)}
          className={`flex-1 flex flex-col items-center gap-1 py-3 text-xs transition-colors ${
            active === id ? 'text-purple-400' : 'text-slate-500'
          }`}
        >
          <Icon size={20} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  )
}
