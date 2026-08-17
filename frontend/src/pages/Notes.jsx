import { useState, useEffect } from 'react'
import { Plus, Search, Trash2, FileText } from 'lucide-react'
import { api } from '../api/client'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'
import { useKullanici } from '../kullanici'

const CATEGORIES = ['iş', 'kişisel', 'genel', 'ders', 'fikir']
const CAT_STYLE = {
  iş: 'text-blue-400 border-blue-400/30 bg-blue-400/10',
  kişisel: 'text-purple-400 border-purple-400/30 bg-purple-400/10',
  genel: 'text-slate-400 border-slate-400/30 bg-slate-400/10',
  ders: 'text-amber-400 border-amber-400/30 bg-amber-400/10',
  fikir: 'text-green-400 border-green-400/30 bg-green-400/10',
}

export default function Notes() {
  const { saltOkunur } = useKullanici()
  const [notes, setNotes] = useState([])
  const [category, setCategory] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ title: '', content: '', category: 'genel' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const t = setTimeout(() => {
      const req = search.trim()
        ? api.searchNotes(search.trim(), category)
        : api.getNotes(category)
      req
        .then(setNotes)
        .catch(e => setError(e.message))
        .finally(() => setLoading(false))
    }, search ? 300 : 0)
    return () => clearTimeout(t)
  }, [category, search])

  const refresh = () => {
    setLoading(true)
    const req = search.trim() ? api.searchNotes(search.trim(), category) : api.getNotes(category)
    req.then(setNotes).catch(e => setError(e.message)).finally(() => setLoading(false))
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createNote(form)
      setShowModal(false)
      setForm({ title: '', content: '', category: 'genel' })
      refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Bu notu silmek istiyor musun?')) return
    await api.deleteNote(id).catch(e => setError(e.message))
    refresh()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileText className="text-blue-400" size={22} />
            Notlar
          </h1>
          <p className="text-slate-500 text-sm mt-1">{notes.length} not</p>
        </div>
        {!saltOkunur && (
          <button onClick={() => setShowModal(true)} className="btn-primary">
            <Plus size={16} />
            Yeni Not
          </button>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-xl text-sm text-red-400"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-600" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Notlarda ara..."
          className="input-field pl-10"
        />
      </div>

      {/* Category Chips */}
      {!search && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setCategory(null)}
            className={`filter-btn ${!category ? 'filter-btn-active' : 'filter-btn-inactive'}`}
          >
            Tümü
          </button>
          {CATEGORIES.map(c => (
            <button
              key={c}
              onClick={() => setCategory(c === category ? null : c)}
              className={`filter-btn ${category === c ? 'filter-btn-active' : 'filter-btn-inactive'}`}
            >
              {c}
            </button>
          ))}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : notes.length === 0 ? (
        <div className="text-center py-20 text-slate-600">
          <FileText size={48} className="mx-auto mb-3 opacity-20" />
          <p>{search ? 'Arama sonucu bulunamadı' : 'Henüz not yok'}</p>
        </div>
      ) : (
        <div className="columns-1 sm:columns-2 lg:columns-3 gap-4">
          {notes.map(n => (
            <div key={n.id} className="glass-card p-4 mb-4 break-inside-avoid group">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="text-slate-100 font-medium text-sm leading-snug flex-1">{n.title}</h3>
                {!saltOkunur && (
                  <button
                    onClick={() => handleDelete(n.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-700 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all flex-shrink-0"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
              <p className="text-slate-500 text-xs leading-relaxed whitespace-pre-wrap line-clamp-6">
                {n.content}
              </p>
              <div className="flex items-center justify-between mt-3">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${CAT_STYLE[n.category] || CAT_STYLE['genel']}`}>
                  {n.category}
                </span>
                <span className="text-xs text-slate-700">
                  {new Date(n.created_at).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' })}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <Modal title="Yeni Not" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Başlık</label>
              <input
                required
                type="text"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                placeholder="Not başlığı"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">İçerik</label>
              <textarea
                required
                value={form.content}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                placeholder="Not içeriği..."
                rows={5}
                className="input-field resize-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">Kategori</label>
              <select
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="select-field"
              >
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-3 pt-1">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary flex-1">İptal</button>
              <button type="submit" disabled={saving} className="btn-primary flex-1">
                {saving ? 'Kaydediliyor...' : 'Kaydet'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
