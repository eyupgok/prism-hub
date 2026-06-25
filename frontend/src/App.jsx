import { useState } from 'react'
import Sidebar from './components/Sidebar'
import BottomNav from './components/BottomNav'
import Dashboard from './pages/Dashboard'
import Reminders from './pages/Reminders'
import Notes from './pages/Notes'
import Expenses from './pages/Expenses'
import Settings from './pages/Settings'

const PAGES = {
  dashboard: Dashboard,
  reminders: Reminders,
  notes: Notes,
  expenses: Expenses,
  settings: Settings,
}

export default function App() {
  const [page, setPage] = useState('dashboard')
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
