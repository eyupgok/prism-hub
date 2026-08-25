import { useState, useEffect } from 'react'
import { Bell, FileText, Cloud, TrendingUp, ArrowRight } from 'lucide-react'
import LiraSign from '../components/LiraSign'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import OzelKarti from '../components/OzelKarti'
import { useKullanici } from '../kullanici'

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
  4: 'text-slate-400 bg-slate-400/10 border-slate-400/30',
}
const PRIORITY_DOT = { 1: 'bg-red-400', 2: 'bg-amber-400', 3: 'bg-green-400', 4: 'bg-slate-500' }
const PRIORITY_LABEL = { 1: 'Kritik', 2: 'Önemli', 3: 'Normal', 4: 'Sessiz' }

// Tailwind sınıf adlarını kaynakta birebir arar — `stagger-${i}` gibi birleştirilmiş
// adları göremez ve kuralları çıktıdan siler. O yüzden düz liste.
const STAGGER = ['stagger-1', 'stagger-2', 'stagger-3', 'stagger-4', 'stagger-5', 'stagger-6']

function StatCard({ icon, iconBg, label, value, sub, onClick, delay = '' }) {
  return (
    <div
      className={`glass glass-hover animate-fade-up ${delay} rounded-2xl p-5 ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className={`w-11 h-11 rounded-2xl flex items-center justify-center mb-4 ${iconBg}`}>
        {icon}
      </div>
      <p className="text-white text-2xl font-display font-bold leading-none tracking-tight">
        {value}
      </p>
      <p className="text-xs mt-2" style={{ color: 'var(--text-faint)' }}>{label}</p>
      {sub && <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>{sub}</p>}
    </div>
  )
}

export default function Dashboard({ onNavigate }) {
  const { kullanici, bakilan, saltOkunur } = useKullanici()
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
    <div className="space-y-6 animate-fade-in">
      {/* Karşılama kartı */}
      <div className="glass glass-hover animate-fade-up relative overflow-hidden rounded-3xl p-6 sm:p-8">
        {/* Sağ üstten yayılan mor ışıma */}
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.18), transparent 70%)' }}
        />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] tracking-[0.18em] uppercase" style={{ color: 'var(--text-faint)' }}>
              {now.toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' })}
            </span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-display font-bold tracking-tight text-white">
            {saltOkunur ? (
              <><span className="accent-text">{bakilan.ad}</span>'ün paneli</>
            ) : (
              <>{greeting()}, <span className="accent-text">{kullanici?.ad}</span></>
            )}
          </h1>

          <p className="mt-2 text-sm min-h-[20px]" style={{ color: 'var(--text-soft)' }}>
            {!loading && (
              <>
                {todayReminders.length > 0
                  ? `Bugün ${todayReminders.length} görevin var.`
                  : 'Bugün için planlanmış görev yok.'}
                {weather && ` ${weatherEmoji(weather.weather_code)} ${weather.city} ${weather.temperature}°C.`}
              </>
            )}
          </p>

          <p className="mt-4 font-mono text-2xl tabular-nums tracking-tight" style={{ color: 'var(--accent-bright)' }}>
            {now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </p>
        </div>
      </div>

      {/* Selamlamanın hemen altında: telefonda ilk ekranda görünsün diye.
          Veri beklemiyor, `loading` bloğunun dışında duruyor. */}
      <OzelKarti onAc={() => onNavigate('özel sayfa')} />

      {error && (
        <div className="p-4 rounded-xl border text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.25)' }}>
          ⚠️ API bağlantı hatası: {error}
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
              delay={STAGGER[0]}
            />
            <StatCard
              icon={<LiraSign size={18} className="text-amber-400" />}
              iconBg="bg-amber-400/10"
              label="Bu Ay Harcama"
              value={`${(summary?.total || 0).toLocaleString('tr-TR')} ₺`}
              onClick={() => onNavigate('expenses')}
              delay={STAGGER[1]}
            />
            <StatCard
              icon={<FileText size={18} className="text-blue-400" />}
              iconBg="bg-blue-400/10"
              label="Aktif Not"
              value={notes.length}
              onClick={() => onNavigate('notes')}
              delay={STAGGER[2]}
            />
            <StatCard
              icon={<Cloud size={18} className="text-teal-400" />}
              iconBg="bg-teal-400/10"
              label={weather?.city || 'Hava Durumu'}
              value={weather ? `${weatherEmoji(weather.weather_code)} ${weather.temperature}°C` : '—'}
              sub={weather?.description}
              delay={STAGGER[3]}
            />
          </div>

          {/* Middle Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Upcoming Reminders */}
            <div className="lg:col-span-2 glass glass-hover animate-fade-up stagger-4 rounded-2xl p-5">
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
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[r.priority]}`} />
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
            <div className="glass glass-hover animate-fade-up stagger-5 rounded-2xl p-5">
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
          <div className="glass glass-hover animate-fade-up stagger-6 rounded-2xl p-5">
            <div className="mb-5">
              <h2 className="text-white font-display font-semibold text-base flex items-center gap-2">
                <TrendingUp size={16} style={{ color: 'var(--accent-bright)' }} />
                Bu Hafta Harcamalar
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>
                Pazartesiden bugüne günlük toplam
              </p>
            </div>
            {weekData.every(d => d.amount === 0) ? (
              <p className="text-slate-600 text-sm text-center py-8">Bu hafta harcama kaydı yok</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={weekData} barSize={26} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
                  <defs>
                    {/* Çubuklar üstte parlak, dipte sönük — düz renkten daha canlı durur */}
                    <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.95} />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: '#6b6b7e', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    dy={6}
                  />
                  <YAxis
                    tick={{ fill: '#6b6b7e', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                    tickFormatter={v => `${v}₺`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(18,18,26,0.95)',
                      backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(139,92,246,0.28)',
                      borderRadius: 14,
                      color: '#f4f4f8',
                      fontSize: 12,
                      boxShadow: '0 16px 32px -12px rgba(0,0,0,0.6)',
                    }}
                    labelStyle={{ color: '#a1a1b5', marginBottom: 4 }}
                    formatter={v => [`${Number(v).toLocaleString('tr-TR')} ₺`, 'Harcama']}
                    cursor={{ fill: 'rgba(139,92,246,0.06)' }}
                  />
                  <Bar
                    dataKey="amount"
                    fill="url(#barGrad)"
                    radius={[8, 8, 0, 0]}
                    animationDuration={900}
                    animationEasing="ease-out"
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </>
      )}
    </div>
  )
}
