import { Home, Bell, FileText, MessageSquare, Settings } from 'lucide-react'
import LiraSign from './LiraSign'

const NAV = [
  { id: 'dashboard', label: 'Panel', icon: Home },
  { id: 'reminders', label: 'Görev', icon: Bell },
  { id: 'notes', label: 'Not', icon: FileText },
  { id: 'expenses', label: 'Harcama', icon: LiraSign },
  { id: 'sohbet', label: 'Sohbet', icon: MessageSquare },
  { id: 'settings', label: 'Ayarlar', icon: Settings },
]

export default function BottomNav({ active, onNavigate }) {
  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 z-20 flex border-t"
      style={{
        background: 'rgba(10, 10, 15, 0.92)',
        backdropFilter: 'blur(20px) saturate(140%)',
        WebkitBackdropFilter: 'blur(20px) saturate(140%)',
        borderColor: 'var(--border)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {NAV.map(({ id, label, icon: Icon }) => {
        const isActive = active === id
        return (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className="relative flex-1 flex flex-col items-center gap-1 py-3 text-[11px]"
            style={{
              color: isActive ? 'var(--accent-bright)' : 'var(--text-faint)',
              transition: 'color 0.25s var(--ease)',
            }}
          >
            {/* Aktif sekmenin üstündeki ışıklı çizgi */}
            {isActive && (
              <span
                className="absolute top-0 h-[2px] w-8 rounded-full animate-scale-in"
                style={{ background: 'linear-gradient(90deg, transparent, var(--accent-bright), transparent)' }}
              />
            )}
            <Icon
              size={20}
              style={{
                transform: isActive ? 'translateY(-1px) scale(1.08)' : 'none',
                transition: 'transform 0.25s var(--ease)',
              }}
            />
            <span>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
