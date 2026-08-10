import { useCallback, useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import BottomNav from './components/BottomNav'
import Dashboard from './pages/Dashboard'
import Reminders from './pages/Reminders'
import Notes from './pages/Notes'
import Expenses from './pages/Expenses'
import Budget from './pages/Budget'
import Settings from './pages/Settings'
import Login from './pages/Login'
import { api, UNAUTHORIZED_EVENT } from './api/client'

const PAGES = {
  dashboard: Dashboard,
  reminders: Reminders,
  notes: Notes,
  expenses: Expenses,
  budget: Budget,
  settings: Settings,
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  // null = oturum durumu henüz bilinmiyor (ilk kontrol sürüyor)
  const [auth, setAuth] = useState(null)

  const checkAuth = useCallback(async () => {
    try {
      setAuth(await api.me())
    } catch {
      // Sunucuya ulaşılamıyorsa giriş ekranını göster — orada anlaşılır bir hata verilir
      setAuth({ authenticated: false, login_required: true, login_enabled: true })
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // Oturum ortada düşerse (çerez süresi dolduysa) giriş ekranına dön
  useEffect(() => {
    const onUnauthorized = () => setAuth((a) => ({ ...a, authenticated: false }))
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  if (auth === null) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-purple-600 border-t-transparent animate-spin" />
      </div>
    )
  }

  if (auth.login_required && !auth.authenticated) {
    return <Login onSuccess={checkAuth} />
  }

  const Page = PAGES[page] || Dashboard

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Sidebar active={page} onNavigate={setPage} />
      <main className="md:pl-64 pb-20 md:pb-0 min-h-screen">
        <div className="max-w-5xl mx-auto p-4 md:p-6 lg:p-8">
          <Page onNavigate={setPage} />
        </div>
      </main>
      <BottomNav active={page} onNavigate={setPage} />
    </div>
  )
}
