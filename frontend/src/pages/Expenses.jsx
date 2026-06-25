import { useState, useEffect } from 'react'
import { Plus, Trash2, DollarSign, TrendingDown } from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../api/client'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'

const CATEGORIES = ['yemek', 'ulaşım', 'eğlence', 'fatura', 'alışveriş', 'diğer']
const CAT_ICON = { yemek: '🍔', ulaşım: '🚗', eğlence: '🎮', fatura: '💡', alışveriş: '🛒', diğer: '📦' }
const CAT_COLOR = { yemek: '#f59e0b', ulaşım: '#3b82f6', eğlence: '#ec4899', fatura: '#8b5cf6', alışveriş: '#10b981', diğer: '#6b7280' }

const MONTH_NAMES = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

function formatMonth(m) {
  const [y, mo] = m.split('-')
  return `${MONTH_NAMES[parseInt(mo) - 1]} ${y}`
}

function nowMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function Expenses() {
  const [expenses, setExpenses] = useState([])
  const [summary, setSummary] = useState(null)
  const [month, setMonth] = useState(nowMonth)
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ amount: '', category: 'yemek', description: '', expense_date: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([api.getExpenses(month), api.getExpenseSummary(month)])
      .then(([e, s]) => { setExpenses(e); setSummary(s) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [month])

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createExpense({
        amount: parseFloat(form.amount),
        category: form.category,
        description: form.description || '',
        expense_date: form.expense_date || undefined,
      })
      setShowModal(false)
      setForm({ amount: '', category: 'yemek', description: '', expense_date: '' })
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Bu harcamayı silmek istiyor musun?')) return
    await api.deleteExpense(id).catch(e => setError(e.message))
    load()
  }

  const pieData = Object.entries(summary?.by_category || {})
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  const categoryEntries = Object.entries(summary?.by_category || {})
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="text-amber-400" size={22} />
            Harcamalar
          </h1>
          <p className="text-slate-500 text-sm mt-1">{formatMonth(month)}</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="input-field w-auto [color-scheme:dark]"
          />
          <button onClick={() => setShowModal(true)} className="btn-primary">
            <Plus size={16} />
            Ekle
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : (
        <>
          {/* Summary + Pie */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Total Card */}
            <div className="glass-card p-6">
              <p className="text-slate-500 text-xs mb-1">Aylık Toplam</p>
              <p className="text-4xl font-bold text-white">
                {(summary?.total || 0).toLocaleString('tr-TR')} ₺
              </p>
              <p className="text-slate-600 text-xs mt-0.5">{formatMonth(month)}</p>

              {categoryEntries.length > 0 && (
                <div className="mt-5 space-y-3">
                  {categoryEntries.slice(0, 5).map(([cat, amount]) => {
                    const pct = (amount / (summary?.total || 1)) * 100
                    return (
                      <div key={cat}>
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>{CAT_ICON[cat] || '📦'} <span className="capitalize">{cat}</span></span>
                          <span>{amount.toLocaleString('tr-TR')} ₺</span>
                        </div>
                        <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }}>
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${Math.min(100, pct)}%`, background: CAT_COLOR[cat] || '#6b7280' }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Pie Chart */}
            <div className="glass-card p-6">
              <h2 className="text-white font-semibold text-sm mb-4">Kategori Dağılımı</h2>
              {pieData.length === 0 ? (
                <div className="flex items-center justify-center h-48 text-slate-600 text-sm">
                  Bu ay harcama yok
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="48%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={CAT_COLOR[entry.name] || '#6b7280'} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#12101e',
                        border: '1px solid rgba(109,40,217,0.4)',
                        borderRadius: 10,
                        color: '#e2e8f0',
                        fontSize: 12,
                      }}
                      formatter={(v, name) => [`${Number(v).toLocaleString('tr-TR')} ₺`, name]}
                    />
                    <Legend
                      iconType="circle"
                      iconSize={8}
                      formatter={(value) => (
                        <span style={{ color: '#94a3b8', fontSize: 12 }}>
                          {CAT_ICON[value] || '📦'} {value}
                        </span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Transaction List */}
          <div className="glass-card overflow-hidden">
            <div className="px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
              <h2 className="text-white font-semibold text-sm flex items-center gap-2">
                <TrendingDown size={15} className="text-amber-400" />
                İşlemler ({expenses.length})
              </h2>
            </div>
            {expenses.length === 0 ? (
              <div className="text-center py-12 text-slate-600">
                <DollarSign size={48} className="mx-auto mb-3 opacity-20" />
                <p>Bu ay harcama kaydı yok</p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                {expenses.map(e => (
                  <div key={e.id} className="flex items-center gap-4 px-5 py-3 group transition-colors hover:bg-white/[0.02]">
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0"
                      style={{ background: `${CAT_COLOR[e.category] || '#6b7280'}18` }}
                    >
                      {CAT_ICON[e.category] || '📦'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-200 truncate">
                        {e.description || <span className="capitalize text-slate-400">{e.category}</span>}
                      </p>
                      <p className="text-xs text-slate-600">
                        {new Date(e.expense_date + 'T12:00:00').toLocaleDateString('tr-TR', {
                          day: '2-digit', month: 'long',
                        })}
                        <span className="mx-1.5 text-slate-800">·</span>
                        <span className="capitalize">{e.category}</span>
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-amber-400 flex-shrink-0">
                      -{e.amount.toLocaleString('tr-TR', { minimumFractionDigits: 0 })} ₺
                    </span>
                    <button
                      onClick={() => handleDelete(e.id)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-700 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Modal */}
      {showModal && (
        <Modal title="Yeni Harcama" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Tutar (₺)</label>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                placeholder="0.00"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Kategori</label>
              <select
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="select-field"
              >
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{CAT_ICON[c]} {c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Açıklama (opsiyonel)</label>
              <input
                type="text"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Ne için?"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Tarih (opsiyonel, boş = bugün)</label>
              <input
                type="date"
                value={form.expense_date}
                onChange={e => setForm(f => ({ ...f, expense_date: e.target.value }))}
                className="input-field [color-scheme:dark]"
              />
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
