import { useEffect, useState } from 'react'
import { Plus, Trash2, AlertTriangle } from 'lucide-react'
import { api } from '../api/client'
import LoadingSpinner from './LoadingSpinner'
import { useKullanici } from '../kullanici'

// Harcamalar sayfasının "Bütçe" sekmesi. Ayrı sayfa değil — limit belirlemek
// harcamaya bakarken akla gelen bir iş, menüde ayrı durunca kopuk kalıyordu.

const CATEGORIES = ['yemek', 'ulaşım', 'eğlence', 'fatura', 'alışveriş', 'diğer']

const CATEGORY_EMOJI = {
  yemek: '🍔',
  ulaşım: '🚗',
  eğlence: '🎮',
  fatura: '💡',
  alışveriş: '🛒',
  diğer: '📦',
}

function money(value) {
  return Number(value || 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })
}

/** Kullanım oranına göre renk: %80 sarı, %100 kırmızı */
function barColor(pct) {
  if (pct >= 100) return '#f87171'
  if (pct >= 80) return '#fbbf24'
  return 'var(--accent)'
}

export default function BudgetPanel() {
  const { saltOkunur } = useKullanici()
  const [budgets, setBudgets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ category: 'yemek', monthly_limit: '' })

  async function load() {
    try {
      setBudgets(await api.getBudgets())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function save(e) {
    e.preventDefault()
    const limit = parseFloat(form.monthly_limit)
    if (!limit || limit <= 0 || saving) return
    setSaving(true)
    try {
      await api.setBudget({ category: form.category, monthly_limit: limit })
      setForm({ category: 'yemek', monthly_limit: '' })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function remove(category) {
    if (!window.confirm(`"${category}" limitini kaldırmak istiyor musun?`)) return
    try {
      await api.deleteBudget(category)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {error && (
        <div className="p-4 rounded-xl border text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.25)' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Yeni limit */}
      {!saltOkunur && (
      <form onSubmit={save} className="glass-card p-5 space-y-4">
        <div>
          <h2 className="text-white font-display font-semibold text-base">Limit belirle</h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-faint)' }}>
            %80'i geçince Telegram'dan uyarı gelir. Aynı kategoriye tekrar limit verirsen eskisinin üzerine yazılır.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={form.category}
            onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
            className="select-field sm:w-48"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_EMOJI[c]} {c}
              </option>
            ))}
          </select>
          <input
            type="number"
            inputMode="decimal"
            min="1"
            step="any"
            value={form.monthly_limit}
            onChange={(e) => setForm((f) => ({ ...f, monthly_limit: e.target.value }))}
            placeholder="Aylık limit (₺)"
            className="input-field flex-1"
          />
          <button type="submit" className="btn-primary sm:w-36" disabled={saving || !form.monthly_limit}>
            <Plus size={15} />
            {saving ? 'Kaydediliyor' : 'Kaydet'}
          </button>
        </div>
      </form>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <LoadingSpinner size="lg" />
        </div>
      ) : budgets.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p style={{ color: 'var(--text-faint)' }}>Henüz limit belirlenmedi.</p>
          <p className="text-sm mt-1" style={{ color: 'var(--text-faint)' }}>
            Yukarıdan bir kategori seçip aylık limitini yaz.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {budgets.map((b) => {
            const spent = b.current_spent || 0
            const pct = b.monthly_limit > 0 ? (spent / b.monthly_limit) * 100 : 0
            const remaining = b.monthly_limit - spent

            return (
              <div key={b.category} className="glass-card p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{CATEGORY_EMOJI[b.category] || '📦'}</span>
                    <span className="text-white font-medium capitalize">{b.category}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm tabular-nums" style={{ color: 'var(--text-soft)' }}>
                      {money(spent)} / {money(b.monthly_limit)} ₺
                    </span>
                    <button
                      onClick={() => remove(b.category)}
                      hidden={saltOkunur}
                      className="p-1.5 rounded-lg transition-colors hover:text-red-400"
                      style={{ color: 'var(--text-faint)' }}
                      aria-label={`${b.category} limitini kaldır`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(pct, 100)}%`,
                      background: barColor(pct),
                      transition: 'width 0.6s var(--ease)',
                    }}
                  />
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: 'var(--text-faint)' }}>%{pct.toFixed(0)} kullanıldı</span>
                  <span style={{ color: remaining < 0 ? '#f87171' : 'var(--text-faint)' }}>
                    {remaining < 0
                      ? `${money(Math.abs(remaining))} ₺ aşıldı`
                      : `${money(remaining)} ₺ kaldı`}
                  </span>
                </div>

                {b.alert && (
                  <div className="flex items-start gap-2 text-xs rounded-xl px-3 py-2"
                    style={{ background: 'rgba(251,191,36,0.08)', color: '#fbbf24' }}>
                    <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
                    <span>{b.alert}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
