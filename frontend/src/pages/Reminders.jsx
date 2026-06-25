import { useState, useEffect } from 'react'
import { Plus, Check, Clock, Trash2, Bell, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'

const PRIORITY_BADGE = {
  1: 'text-red-400 bg-red-400/10 border-red-400/30',
  2: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  3: 'text-green-400 bg-green-400/10 border-green-400/30',
}
const PRIORITY_DOT = { 1: 'bg-red-400', 2: 'bg-amber-400', 3: 'bg-green-400' }
const PRIORITY_LABEL = { 1: 'Kritik', 2: 'Önemli', 3: 'Normal' }
const RECURRENCE_LABEL = { none: null, daily: 'Günlük', weekly: 'Haftalık', monthly: 'Aylık' }

const FILTERS = [
  { id: 'all', label: 'Tümü' },
  { id: '1', label: '🔴 Kritik' },
  { id: '2', label: '🟡 Önemli' },
  { id: '3', label: '🟢 Normal' },
  { id: 'recurring', label: '🔄 Tekrarlananlar' },
  { id: 'done', label: '✅ Tamamlananlar' },
]

function timeLeft(dueStr) {
  const diff = new Date(dueStr) - new Date()
  if (diff < 0) return { text: 'Geçti', cls: 'text-red-500' }
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (h === 0) return { text: `${m} dk`, cls: 'text-red-400', pulse: true }
  if (h < 24) return { text: `${h}s ${m}dk`, cls: 'text-amber-400' }
  return { text: `${Math.floor(h / 24)} gün`, cls: 'text-green-400' }
}

function defaultDT() {
  const d = new Date(Date.now() + 30 * 60000)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function Reminders() {
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ title: '', due_datetime: '', priority: 3, recurrence: 'none' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    api.getReminders(true)
      .then(setItems)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const filtered = items.filter(r => {
    if (filter === 'done') return r.is_completed
    if (filter === 'recurring') return !r.is_completed && r.recurrence && r.recurrence !== 'none'
    if (filter === 'all') return !r.is_completed
    return !r.is_completed && r.priority === Number(filter)
  })

  const activeCount = items.filter(r => !r.is_completed).length

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createReminder(form)
      setShowModal(false)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleComplete = async (id) => {
    await api.completeReminder(id).catch(e => setError(e.message))
    load()
  }

  const handleSnooze = async (id, minutes) => {
    await api.snoozeReminder(id, minutes).catch(e => setError(e.message))
    load()
  }

  const handleDelete = async (id) => {
    await api.deleteReminder(id).catch(e => setError(e.message))
    load()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell className="text-purple-400" size={22} />
            Hatırlatıcılar
          </h1>
          <p className="text-slate-500 text-sm mt-1">{activeCount} aktif</p>
        </div>
        <button
          onClick={() => { setShowModal(true); setForm({ title: '', due_datetime: defaultDT(), priority: 3, recurrence: 'none' }) }}
          className="btn-primary"
        >
          <Plus size={16} />
          Yeni
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-xl text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`filter-btn ${filter === f.id ? 'filter-btn-active' : 'filter-btn-inactive'}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-slate-600">
          <Bell size={48} className="mx-auto mb-3 opacity-20" />
          <p>Hatırlatıcı bulunamadı</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(r => {
            const tl = timeLeft(r.due_datetime)
            const recurrence = RECURRENCE_LABEL[r.recurrence]
            return (
              <div key={r.id} className="glass-card p-4 flex items-start gap-3">
                <div className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${PRIORITY_DOT[r.priority]}`} />

                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <p className={`text-sm font-medium ${r.is_completed ? 'line-through text-slate-600' : 'text-slate-100'}`}>
                      {r.title}
                    </p>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${PRIORITY_BADGE[r.priority]}`}>
                      {PRIORITY_LABEL[r.priority]}
                    </span>
                    {recurrence && (
                      <span className="text-xs px-2 py-0.5 rounded-full text-purple-400 flex items-center gap-1"
                        style={{ background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.25)' }}>
                        <RefreshCw size={10} />
                        {recurrence}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600">
                    {new Date(r.due_datetime).toLocaleString('tr-TR', {
                      day: '2-digit', month: 'long', hour: '2-digit', minute: '2-digit',
                    })}
                  </p>
                </div>

                {!r.is_completed && (
                  <span className={`text-xs font-semibold flex-shrink-0 ${tl.cls} ${tl.pulse ? 'animate-pulse' : ''}`}>
                    {tl.text}
                  </span>
                )}

                {!r.is_completed && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleSnooze(r.id, 15)}
                      title="15 dk ertele"
                      className="p-1.5 text-slate-600 hover:text-amber-400 hover:bg-amber-400/10 rounded-lg transition-colors"
                    >
                      <Clock size={15} />
                    </button>
                    <button
                      onClick={() => handleComplete(r.id)}
                      title="Tamamla"
                      className="p-1.5 text-slate-600 hover:text-green-400 hover:bg-green-400/10 rounded-lg transition-colors"
                    >
                      <Check size={15} />
                    </button>
                    <button
                      onClick={() => handleDelete(r.id)}
                      title="Sil"
                      className="p-1.5 text-slate-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}

                {r.is_completed && (
                  <button
                    onClick={() => handleDelete(r.id)}
                    className="p-1.5 text-slate-700 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors flex-shrink-0"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <Modal title="Yeni Hatırlatıcı" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Başlık</label>
              <input
                required
                type="text"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                placeholder="Ne hatırlatayım?"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Tarih ve Saat</label>
              <input
                required
                type="datetime-local"
                value={form.due_datetime}
                onChange={e => setForm(f => ({ ...f, due_datetime: e.target.value }))}
                className="input-field [color-scheme:dark]"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Öncelik</label>
              <select
                value={form.priority}
                onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))}
                className="select-field"
              >
                <option value={1}>🔴 Kritik</option>
                <option value={2}>🟡 Önemli</option>
                <option value={3}>🟢 Normal</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Tekrar</label>
              <select
                value={form.recurrence}
                onChange={e => setForm(f => ({ ...f, recurrence: e.target.value }))}
                className="select-field"
              >
                <option value="none">Yok</option>
                <option value="daily">Her gün</option>
                <option value="weekly">Her hafta</option>
                <option value="monthly">Her ay</option>
              </select>
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-3 pt-1">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary flex-1">İptal</button>
              <button type="submit" disabled={saving} className="btn-primary flex-1">
                {saving ? 'Kaydediliyor...' : 'Ekle'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
