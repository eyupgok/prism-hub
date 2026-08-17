import { useEffect, useRef, useState } from 'react'
import { Send, ImagePlus, Sparkles, X } from 'lucide-react'
import { api } from '../api/client'
import { useKullanici } from '../kullanici'

/**
 * Panelden asistanla konuşma.
 *
 * Neden var: Zeynep iPhone'da, Android uygulaması kurulamıyor. Onun için
 * asistanla konuşabileceği tek yer Telegram'dı; burası ikinci kapı.
 *
 * Geçmiş SEKMEYE ÖZEL: sunucu konuşmayı `conversations` tablosunda tutuyor ve
 * modele bağlam olarak veriyor, ama orada asistan tarafı ham JSON komut olarak
 * duruyor (modelin ihtiyacı o). İnsan için okunur metin saklanmıyor, o yüzden
 * sayfa yenilenince ekran boşalır — asistan hatırlamaya devam eder, sadece
 * baloncuklar gider.
 */

// Sunucudan gelen yanıt Telegram ile aynı biçimde basit etiketler içerebiliyor
// (<b>, <i>, <s>, <code>). Kullanıcı içeriği sunucuda zaten kaçırılıyor; yine de
// buraya körlemesine HTML basmıyoruz — yalnız bu etiketlere izin veren küçük bir
// çevirici. İzin listesi dışındaki her şey düz metin olarak görünür.
const IZINLI = { b: 'strong', strong: 'strong', i: 'em', em: 'em', s: 'del', code: 'code' }

function parcala(metin) {
  const parcalar = []
  const kalip = /<(\/?)(b|strong|i|em|s|code)>|<br\s*\/?>/gi
  let son = 0
  let yigin = []
  let m
  while ((m = kalip.exec(metin)) !== null) {
    if (m.index > son) parcalar.push({ metin: metin.slice(son, m.index), etiketler: [...yigin] })
    if (m[0].toLowerCase().startsWith('<br')) parcalar.push({ satirSonu: true })
    else if (m[1]) yigin.pop()
    else yigin.push(IZINLI[m[2].toLowerCase()])
    son = kalip.lastIndex
  }
  if (son < metin.length) parcalar.push({ metin: metin.slice(son), etiketler: [...yigin] })
  return parcalar
}

function Zengin({ metin }) {
  return (
    <>
      {parcala(metin || '').map((p, i) => {
        if (p.satirSonu) return <br key={i} />
        let el = p.metin
        for (const etiket of [...(p.etiketler || [])].reverse()) {
          const E = etiket
          el = <E>{el}</E>
        }
        return <span key={i}>{el}</span>
      })}
    </>
  )
}

export default function Sohbet() {
  const { kullanici, saltOkunur } = useKullanici()
  const [mesajlar, setMesajlar] = useState([])
  const [girdi, setGirdi] = useState('')
  const [gorsel, setGorsel] = useState(null)
  const [bekliyor, setBekliyor] = useState(false)
  const alt = useRef(null)
  const dosyaGirdi = useRef(null)

  useEffect(() => {
    alt.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mesajlar, bekliyor])

  async function gonder(e) {
    e?.preventDefault()
    const metin = girdi.trim()
    if ((!metin && !gorsel) || bekliyor) return

    const benim = { kim: 'ben', metin: metin || '(görsel)', gorselAdi: gorsel?.name }
    setMesajlar((m) => [...m, benim])
    setGirdi('')
    const gonderilecekGorsel = gorsel
    setGorsel(null)
    setBekliyor(true)

    try {
      const y = gonderilecekGorsel
        ? await api.sohbetGorsel(gonderilecekGorsel, metin)
        : await api.sohbet(metin)
      setMesajlar((m) => [...m, { kim: 'prism', metin: y.response, aciklama: y.description }])
    } catch (err) {
      setMesajlar((m) => [...m, { kim: 'hata', metin: err.message || 'Gönderilemedi' }])
    } finally {
      setBekliyor(false)
    }
  }

  return (
    <div className="flex flex-col" style={{ minHeight: 'calc(100dvh - 12rem)' }}>
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={20} style={{ color: 'var(--accent-bright)' }} />
        <h1 className="text-2xl font-display font-bold text-white">Sohbet</h1>
      </div>

      {saltOkunur && (
        <p className="glass-card p-3 mb-4 text-xs" style={{ color: 'var(--text-soft)' }}>
          Sohbet her zaman <strong className="text-white">{kullanici?.ad}</strong> adına çalışır —
          yazdığın şey senin hatırlatıcına, notuna, harcamana gider.
        </p>
      )}

      <div className="flex-1 space-y-3 mb-4">
        {mesajlar.length === 0 && !bekliyor && (
          <div className="glass-card p-5 text-sm" style={{ color: 'var(--text-soft)' }}>
            <p className="text-white mb-2">Doğrudan yazabilirsin:</p>
            <ul className="space-y-1">
              <li>• <i>Yarın 10'da diş hekimi hatırlat</i></li>
              <li>• <i>Bugün 250 TL market harcadım</i></li>
              <li>• <i>Alışveriş listeme yumurta ekle</i></li>
              <li>• <i>Bu ay ne kadar harcamışım?</i></li>
            </ul>
            <p className="mt-3 text-xs" style={{ color: 'var(--text-faint)' }}>
              Fiş fotoğrafı da yükleyebilirsin — okuyup harcama olarak kaydeder.
            </p>
          </div>
        )}

        {mesajlar.map((m, i) => (
          <div key={i} className={`flex ${m.kim === 'ben' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed animate-fade-up"
              style={{
                background: m.kim === 'ben' ? 'var(--accent-deep)' : 'var(--surface)',
                color: m.kim === 'hata' ? '#fca5a5' : m.kim === 'ben' ? '#fff' : 'var(--text)',
                border: m.kim === 'ben' ? 'none' : '1px solid var(--border)',
              }}
            >
              <Zengin metin={m.metin} />
              {m.gorselAdi && (
                <p className="text-[11px] mt-1 opacity-70">🖼 {m.gorselAdi}</p>
              )}
            </div>
          </div>
        ))}

        {bekliyor && (
          <div className="flex justify-start">
            <div
              className="rounded-2xl px-4 py-3 flex gap-1.5"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full animate-pulse-glow"
                  style={{ background: 'var(--accent-bright)', animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={alt} />
      </div>

      <form onSubmit={gonder} className="sticky bottom-0 pb-2" style={{ background: 'var(--bg)' }}>
        {gorsel && (
          <div
            className="flex items-center gap-2 mb-2 px-3 py-2 rounded-xl text-xs"
            style={{ background: 'var(--surface)', color: 'var(--text-soft)' }}
          >
            🖼 {gorsel.name}
            <button type="button" onClick={() => setGorsel(null)} className="ml-auto">
              <X size={14} />
            </button>
          </div>
        )}
        <div className="flex gap-2">
          <input
            ref={dosyaGirdi}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => setGorsel(e.target.files?.[0] || null)}
          />
          <button
            type="button"
            onClick={() => dosyaGirdi.current?.click()}
            title="Fiş / görsel yükle"
            className="px-3 rounded-xl flex-shrink-0"
            style={{ background: 'var(--surface)', color: 'var(--text-soft)', border: '1px solid var(--border)' }}
          >
            <ImagePlus size={18} />
          </button>
          <input
            value={girdi}
            onChange={(e) => setGirdi(e.target.value)}
            placeholder="Bir şey yaz…"
            className="input-field flex-1"
            disabled={bekliyor}
          />
          <button
            type="submit"
            disabled={bekliyor || (!girdi.trim() && !gorsel)}
            className="btn-primary flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}
