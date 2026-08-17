import { Eye, User } from 'lucide-react'
import { useKullanici } from '../kullanici'

/**
 * Üstteki kişi geçişi + salt görüntüleme uyarısı.
 *
 * Tek kullanıcı varsa hiç çizilmiyor — iki kişi olmadan bu şeridin anlamı yok
 * ve paneli boş yere daraltır.
 */
export default function KisiSeridi() {
  const { kullanici, kullanicilar, bakilan, setBakilanId, saltOkunur } = useKullanici()

  if (!kullanici || kullanicilar.length < 2) return null

  return (
    <div
      className="sticky top-0 z-10 border-b backdrop-blur-md animate-fade-in"
      style={{
        borderColor: saltOkunur ? 'var(--border-strong)' : 'var(--border)',
        background: saltOkunur ? 'rgba(139, 92, 246, 0.10)' : 'rgba(10, 10, 15, 0.72)',
      }}
    >
      <div className="max-w-5xl mx-auto px-4 md:px-6 lg:px-8 py-2.5 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--surface)' }}>
          {kullanicilar.map((k) => {
            const secili = k.id === bakilan?.id
            return (
              <button
                key={k.id}
                onClick={() => setBakilanId(k.id)}
                aria-pressed={secili}
                className="px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1.5"
                style={{
                  transition: 'background .25s var(--ease), color .25s var(--ease)',
                  background: secili ? 'var(--accent-deep)' : 'transparent',
                  color: secili ? '#fff' : 'var(--text-soft)',
                }}
              >
                {k.id === kullanici.id ? <User size={14} /> : <Eye size={14} />}
                {k.ad}
              </button>
            )
          })}
        </div>

        {saltOkunur ? (
          <p className="text-xs flex items-center gap-1.5" style={{ color: 'var(--accent-bright)' }}>
            <Eye size={13} />
            <span>
              <strong className="font-semibold">{bakilan.ad}</strong>'ün verilerine bakıyorsun —
              salt görüntüleme, değiştiremezsin
            </span>
          </p>
        ) : (
          <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
            Kendi verilerin
          </p>
        )}
      </div>
    </div>
  )
}
