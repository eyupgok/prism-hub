import { useEffect, useRef, useState } from 'react'
import { Volume2, Square, Save, AudioLines } from 'lucide-react'
import { api } from '../api/client'

/**
 * Asistanın sesi — Ayarlar sayfasındaki bölüm.
 *
 * Neden panelde: ses "kurcalayarak" bulunan bir şey ("biraz daha yavaş, biraz
 * daha düz"). Ayar .env'de olsaydı her deneme sunucuya girip servisi yeniden
 * başlatmak demekti; Android uygulamasında olsaydı her deneme APK derleyip
 * telefona kurmak demekti. İkisi de o döngüyü öldürürdü.
 *
 * ⚠️ Önizleme KAYDETMEDEN çalışıyor: seçilen değerler istekle birlikte
 * gönderiliyor, sunucu onları geçici olarak kullanıcının üstüne biniyor.
 * Aksi hâlde her deneme "kaydet, dinle, beğenme, geri al" olurdu.
 */

const ORNEK = 'Günaydın efendim. Bugün üç göreviniz var, ilki saat onda.'

export default function SesAyari() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState('')
  const [ses, setSes] = useState('')
  const [sakinlik, setSakinlik] = useState(0.6)
  const [hiz, setHiz] = useState(0.95)
  const [calisiyor, setCalisiyor] = useState(false)
  const [kaydediliyor, setKaydediliyor] = useState(false)
  const [kaydedildi, setKaydedildi] = useState(false)
  const sesRef = useRef(null)

  useEffect(() => {
    api.sesSecenekleri()
      .then((d) => {
        setVeri(d)
        setSes(d.ayar?.ses_id || '')
        setSakinlik(d.ayar?.stability ?? 0.6)
        setHiz(d.ayar?.speed ?? 0.95)
      })
      .catch((e) => setHata(e.message))
  }, [])

  // Sayfadan çıkarken sustur — yoksa başka sekmeye geçince arkadan konuşur
  useEffect(() => () => sesRef.current?.pause(), [])

  async function onizle() {
    sesRef.current?.pause()
    if (calisiyor) return setCalisiyor(false)

    setCalisiyor(true)
    setHata('')
    let adres
    try {
      adres = await api.seslendir(ORNEK, { ses_id: ses, ses_sakinlik: sakinlik, ses_hiz: hiz })
      const parca = new Audio(adres)
      sesRef.current = parca
      const bitir = () => {
        setCalisiyor(false)
        URL.revokeObjectURL(adres)
      }
      parca.onended = bitir
      parca.onerror = bitir
      await parca.play()
    } catch (e) {
      if (adres) URL.revokeObjectURL(adres)
      setCalisiyor(false)
      setHata(e.message)
    }
  }

  async function kaydet() {
    setKaydediliyor(true)
    setHata('')
    try {
      await api.sesAyariKaydet({ ses_id: ses, ses_sakinlik: sakinlik, ses_hiz: hiz })
      setKaydedildi(true)
      setTimeout(() => setKaydedildi(false), 2500)
    } catch (e) {
      setHata(e.message)
    } finally {
      setKaydediliyor(false)
    }
  }

  if (hata && !veri) {
    return (
      <div className="glass-card p-5">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2 mb-2">
          <AudioLines size={15} className="text-purple-400" />
          Asistanın Sesi
        </h2>
        <p className="text-sm" style={{ color: '#fca5a5' }}>{hata}</p>
      </div>
    )
  }

  if (!veri) return null

  const kota = veri.kota
  // Kota bitince ses sessizce kesilir; sebebini görmezse arıza sanır
  const kotaDusuk = kota && kota.sinir > 0 && kota.kalan / kota.sinir < 0.15

  return (
    <div className="glass-card p-5 space-y-4">
      <h2 className="text-white font-semibold text-sm flex items-center gap-2">
        <AudioLines size={15} className="text-purple-400" />
        Asistanın Sesi
      </h2>

      <p className="text-slate-500 text-xs leading-relaxed">
        Sesli mesaj attığında asistan sesli cevap verir; sohbette de her yanıtın altında
        Dinle düğmesi vardır. Bu ayar yalnız seni ilgilendirir — herkes kendi sesini seçer.
      </p>

      <div>
        <label className="block text-xs text-slate-600 mb-1.5">Ses</label>
        <select
          className="input-field w-full"
          value={ses}
          onChange={(e) => setSes(e.target.value)}
        >
          {veri.sesler.map((s) => (
            <option key={s.id} value={s.id}>
              {s.ad}{s.tarif ? ` — ${s.tarif}` : ''}{s.aksan ? ` (${s.aksan})` : ''}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="flex justify-between text-xs text-slate-600 mb-1.5">
          <span>Sakinlik</span>
          <span className="text-slate-400">{sakinlik.toFixed(2)}</span>
        </label>
        <input
          type="range" min={veri.sinirlar.sakinlik[0]} max={veri.sinirlar.sakinlik[1]} step="0.05"
          value={sakinlik} onChange={(e) => setSakinlik(parseFloat(e.target.value))}
          className="w-full" style={{ accentColor: 'var(--accent-bright)' }}
        />
        <p className="text-[11px] text-slate-700 mt-1">
          Yükseldikçe okuma düzleşir, duygusal dalgalanma azalır.
        </p>
      </div>

      <div>
        <label className="flex justify-between text-xs text-slate-600 mb-1.5">
          <span>Hız</span>
          <span className="text-slate-400">{hiz.toFixed(2)}×</span>
        </label>
        <input
          type="range" min={veri.sinirlar.hiz[0]} max={veri.sinirlar.hiz[1]} step="0.05"
          value={hiz} onChange={(e) => setHiz(parseFloat(e.target.value))}
          className="w-full" style={{ accentColor: 'var(--accent-bright)' }}
        />
      </div>

      <div className="flex gap-2">
        <button type="button" onClick={onizle} className="btn-secondary flex-1">
          {calisiyor ? <Square size={15} /> : <Volume2 size={15} />}
          {calisiyor ? 'Durdur' : 'Önizle'}
        </button>
        <button type="button" onClick={kaydet} disabled={kaydediliyor} className="btn-primary flex-1">
          <Save size={15} />
          {kaydedildi ? 'Kaydedildi' : kaydediliyor ? 'Kaydediliyor...' : 'Kaydet'}
        </button>
      </div>

      {hata && <p className="text-xs" style={{ color: '#fca5a5' }}>{hata}</p>}

      {kota && (
        <p className="text-[11px]" style={{ color: kotaDusuk ? '#fbbf24' : 'var(--text-faint)' }}>
          Kalan seslendirme hakkı: <strong>{kota.kalan.toLocaleString('tr-TR')}</strong> /{' '}
          {kota.sinir.toLocaleString('tr-TR')} karakter ({kota.kademe})
          {kotaDusuk && ' — bitince ses susar, yazılı cevap devam eder.'}
        </p>
      )}
    </div>
  )
}
