import { useState, useEffect } from 'react'
import { Bell, FileText, DollarSign, Cloud, TrendingUp, ArrowRight } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

function useNow() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return now
}

function greeting() {
  const h = new Date().getHours()
  if (h < 5) return 'İyi geceler'
  if (h < 12) return 'Günaydın'
  if (h < 17) return 'İyi öğlenler'
  if (h < 21) return 'İyi akşamlar'
  return 'İyi geceler'
}

function weatherEmoji(code) {
  if (code == null) return '🌡'
  if (code === 0) return '☀️'
  if (code <= 2) return '🌤'
  if (code === 3) return '☁️'
  if (code <= 48) return '🌫'
  if (code <= 67) return '🌧'
  if (code <= 77) return '❄️'
  if (code <= 82) return '🌦'
  return '⛈'
}

function toLocalDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function thisWeekData(expenses) {
  const today = new Date()
  const dow = today.getDay()
  const daysFromMon = dow === 0 ? 6 : dow - 1
  const monday = new Date(today)
  monday.setDate(today.getDate() - daysFromMon)
  monday.setHours(0, 0, 0, 0)

  const labels = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
  const days = labels.map((label, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return { label, date: toLocalDateStr(d), amount: 0 }
  })

  for (const e of expenses) {
    const bucket = days.find(d => d.date === e.expense_date)
    if (bucket) bucket.amount += e.amount
  }
  return days
}

function timeLeft(dueStr) {
  const diff = new Date(dueStr) - new Date()
  if (diff < 0) return { text: 'Geçti', cls: 'text-red-500' }
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (h === 0) return { text: `${m} dk`, cls: 'text-red-400 animate-pulse' }
  if (h < 24) return { text: `${h}s`, cls: 'text-amber-400' }
  return { text: `${Math.floor(h / 24)} gün`, cls: 'text-green-400' }
}

const PRIORITY_BADGE = {
  1: 'text-red-400 bg-red-400/10 border-red-400/30',
  2: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  3: 'text-green-400 bg-green-400/10 border-green-400/30',
}
const PRIORITY_LABEL = { 1: 'Kritik', 2: 'Önemli', 3: 'Normal' }

function StatCard({ icon, iconBg, label, value, sub, onClick }) {
  return (
    <div
      className={`glass-card p-5 ${onClick ? 'cursor-pointer hover:bg-white/5 transition-colors' : ''}`}
      onClick={onClick}
      style={onClick ? { '--tw-border-opacity': 1 } : {}}
    >
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${iconBg}`}>
        {icon}
      </div>
      <p className="text-slate-500 text-xs mb-1">{label}</p>
      <p className="text-white text-xl font-bold leading-tight">{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Dashboard({ onNavigate }) {
  const [reminders, setReminders] = useState([])
  const [notes, setNotes] = useState([])
  const [summary, setSummary] = useState(null)
  const [weather, setWeather] = useState(null)
  const [expenses, setExpenses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const now = useNow()

  useEffect(() => {
    const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    Promise.all([
      api.getReminders(false),
      api.getNotes(),
      api.getExpenseSummary(month),
      api.getWeather(),
      api.getExpenses(month),
    ])
      .then(([r, n, s, w, e]) => {
        setReminders(r)
        setNotes(n)
        setSummary(s)
        setWeather(w)
        setExpenses(e)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const todayStr = toLocalDateStr(now)
  const todayReminders = reminders.filter(r => {
    const d = new Date(r.due_datetime)
    return toLocalDateStr(d) === todayStr
  })
  const upcoming = [...reminders]
    .sort((a, b) => new Date(a.due_datetime) - new Date(b.due_datetime))
    .slice(0, 5)
  const weekData = thisWeekData(expenses)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-white">
          {greeting()}, Eyüp ☀️
        </h1>
        <p className="text-slate-400 mt-1 text-sm">
          {now.toLocaleDateString('tr-TR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          <span className="mx-2 text-slate-700">·</span>
          <span className="text-purple-400 font-mono tabular-nums">
            {now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl border text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.25)' }}>
          ⚠️ API bağlantı hatası: {error}. VITE_API_URL ayarını kontrol et.
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={<Bell size={18} className="text-purple-400" />}
              iconBg="bg-purple-400/10"
              label="Bugünkü Görev"
              value={todayReminders.length}
              sub={`${reminders.length} aktif toplam`}
              onClick={() => onNavigate('reminders')}
            />
            <StatCard
              icon={<DollarSign size={18} className="text-amber-400" />}
              iconBg="bg-amber-400/10"
              label="Bu Ay Harcama"
              value={`${(summary?.total || 0).toLocaleString('tr-TR')} ₺`}
              onClick={() => onNavigate('expenses')}
            />
            <StatCard
              icon={<FileText size={18} className="text-blue-400" />}
              iconBg="bg-blue-400/10"
              label="Aktif Not"
              value={notes.length}
              onClick={() => onNavigate('notes')}
            />
            <StatCard
              icon={<Cloud size={18} className="text-teal-400" />}
              iconBg="bg-teal-400/10"
              label={weather?.city || 'Hava Durumu'}
              value={weather ? `${weatherEmoji(weather.weather_code)} ${weather.temperature}°C` : '—'}
              sub={weather?.description}
            />
          </div>

          {/* Middle Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Upcoming Reminders */}
            <div className="lg:col-span-2 glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-white font-semibold text-sm flex items-center gap-2">
                  <Bell size={15} className="text-purple-400" />
                  Yaklaşan Hatırlatıcılar
                </h2>
                <button
                  onClick={() => onNavigate('reminders')}
                  className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                >
                  Tümü <ArrowRight size={12} />
                </button>
              </div>
              {upcoming.length === 0 ? (
                <p className="text-slate-600 text-sm text-center py-8">Aktif hatırlatıcı yok</p>
              ) : (
                <div className="space-y-2">
                  {upcoming.map(r => {
                    const tl = timeLeft(r.due_datetime)
                    return (
                      <div key={r.id} className="flex items-center gap-3 p-3 rounded-xl transition-colors"
                        style={{ background: 'rgba(255,255,255,0.03)' }}>
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          r.priority === 1 ? 'bg-red-400' : r.priority === 2 ? 'bg-amber-400' : 'bg-green-400'
                        }`} />
                        <span className={`text-xs px-2 py-0.5 rounded-full border flex-shrink-0 ${PRIORITY_BADGE[r.priority]}`}>
                          {PRIORITY_LABEL[r.priority]}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-slate-200 text-sm truncate">{r.title}</p>
                          <p className="text-slate-600 text-xs">
                            {new Date(r.due_datetime).toLocaleString('tr-TR', {
                              day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                            })}
                          </p>
                        </div>
                        <span className={`text-xs font-semibold flex-shrink-0 ${tl.cls}`}>{tl.text}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Recent Notes */}
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-white font-semibold text-sm flex items-center gap-2">
                  <FileText size={15} className="text-blue-400" />
                  Son Notlar
                </h2>
                <button
                  onClick={() => onNavigate('notes')}
                  className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                >
                  Tümü <ArrowRight size={12} />
                </button>
              </div>
              {notes.length === 0 ? (
                <p className="text-slate-600 text-sm text-center py-8">Not yok</p>
              ) : (
                <div className="space-y-3">
                  {notes.slice(0, 3).map(n => (
                    <div key={n.id} className="p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)' }}>
                      <p className="text-slate-200 text-sm font-medium truncate">{n.title}</p>
                      <p className="text-slate-500 text-xs mt-1 line-clamp-2 leading-relaxed">{n.content}</p>
                      <span className="inline-block mt-2 text-xs px-2 py-0.5 rounded-full text-purple-400"
                        style={{ background: 'rgba(167,139,250,0.1)' }}>
                        {n.category}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Weekly Chart */}
          <div className="glass-card p-5">
            <h2 className="text-white font-semibold text-sm flex items-center gap-2 mb-5">
              <TrendingUp size={15} className="text-amber-400" />
              Bu Hafta Harcamalar
            </h2>
            {weekData.every(d => d.amount === 0) ? (
              <p className="text-slate-600 text-sm text-center py-8">Bu hafta harcama kaydı yok</p>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={weekData} barSize={24}>
                  <XAxis
                    dataKey="label"
                    tick={{ fill: '#64748b', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                    tickFormatter={v => `${v}₺`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#12101e',
                      border: '1px solid rgba(109,40,217,0.4)',
                      borderRadius: 10,
                      color: '#e2e8f0',
                      fontSize: 12,
                    }}
                    formatter={v => [`${Number(v).toLocaleString('tr-TR')} ₺`, 'Harcama']}
                    cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  />
                  <Bar dataKey="amount" fill="#7c3aed" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </>
      )}
    </div>
  )
}
