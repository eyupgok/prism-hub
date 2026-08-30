import { useEffect, useRef, useState } from 'react'
import { Send, ImagePlus, Sparkles, X, Volume2, Square, Mic, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import { useKullanici } from '../kullanici'
import { AZAMI_SANIYE, sesKaydiDestekli, sureBicimi, useSesKaydi } from '../sesKaydi'

/**
 * Panelden asistanla konuşma.
 *
 * Neden var: Zeynep iPhone'da, Android uygulaması kurulamıyor. Onun için
 * asistanla konuşabileceği tek yer Telegram'dı; burası ikinci kapı.
 *
 * Geçmiş SUNUCUDA duruyor (`conversations` tablosu, `panel:<id>` kovası) ve
 * sayfa açılınca geri çekiliyor — yani baloncuklar sayfa yenilenince
 * kaybolmuyor. Asistan tarafında iki metin saklanıyor: modele giden ham JSON
 * komut ve insana görünen cevap (bkz. `database.save_message`).
 *
 * ⚠️ Telegram'daki konuşma buraya karışmaz, iki kanal ayrı bağlam. Ekranda
 * birleştirseydik asistanın hatırladığı şeyle kullanıcının gördüğü şey
 * ayrışırdı. ⚠️ Geçmiş 30 günlük: `conversations` her gece temizleniyor.
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

/** "Bugün" / "Dün" / "14 Ağustos" — Telegram'daki gün ayracının karşılığı. */
function gunEtiketi(iso) {
  const t = new Date(iso)
  if (Number.isNaN(t.getTime())) return ''
  const bugun = new Date()
  const gun = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
  if (gun(t) === gun(bugun)) return 'Bugün'
  const dun = new Date(bugun)
  dun.setDate(dun.getDate() - 1)
  if (gun(t) === gun(dun)) return 'Dün'
  return t.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })
}

function saatEtiketi(iso) {
  const t = new Date(iso)
  return Number.isNaN(t.getTime())
    ? ''
    : t.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
}

export default function Sohbet() {
  const { kullanici, saltOkunur } = useKullanici()
  const [mesajlar, setMesajlar] = useState([])
  const [yukleniyor, setYukleniyor] = useState(true)
  // Hangi baloncuk şu an konuşuyor (index) — aynı anda yalnız biri çalar
  const [calan, setCalan] = useState(null)
  const sesRef = useRef(null)
  const [girdi, setGirdi] = useState('')
  const [gorsel, setGorsel] = useState(null)
  const [bekliyor, setBekliyor] = useState(false)
  const alt = useRef(null)
  const ilkKaydirma = useRef(true)
  const dosyaGirdi = useRef(null)
  const kayit = useSesKaydi()

  // Geçmişi çek. Başarısız olursa sohbet boş başlar ama YAZILABİLİR kalır —
  // geçmişi okuyamamak konuşmayı engellememeli.
  useEffect(() => {
    api.sohbetGecmisi()
      .then((d) => setMesajlar(
        (d.mesajlar || []).map((m) => ({
          kim: m.role === 'user' ? 'ben' : 'prism',
          metin: m.metin,
          an: m.created_at,
        }))
      ))
      .catch(() => {})
      .finally(() => setYukleniyor(false))
  }, [])

  useEffect(() => {
    if (yukleniyor) return
    // İlk çizimde geçmişin dibine ANINDA in; her açılışta sayfanın kendi
    // kendine kayması izlemesi hoş değil.
    alt.current?.scrollIntoView({ behavior: ilkKaydirma.current ? 'auto' : 'smooth' })
    ilkKaydirma.current = false
  }, [mesajlar, bekliyor, yukleniyor])

  // Sayfadan çıkarken çalanı sustur. Olmasaydı başka sekmeye geçince ses
  // arkadan konuşmaya devam ederdi ve durduracak düğme ekranda kalmazdı.
  useEffect(() => () => sesRef.current?.pause(), [])

  // Açık unutulmuş mikrofon: süre dolunca kayıt kendiliğinden gönderilir.
  useEffect(() => {
    if (kayit.kayitta && kayit.saniye >= AZAMI_SANIYE) sesiGonder()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kayit.kayitta, kayit.saniye])

  /**
   * Baloncuğu sesli okut.
   *
   * Ses SUNUCUDA üretiliyor (`/api/chat/ses`), tarayıcının kendi
   * `speechSynthesis`'i ile değil: o bedava ve anında ama sesi her cihazda
   * başka. Asistanın sesi kimliğinin parçası, telefon değişince değişmemeli —
   * bu yüzden panel de Telegram'la aynı motoru kullanıyor.
   */
  async function seslendir(i, metin) {
    sesRef.current?.pause()
    if (calan === i) return setCalan(null)   // aynı düğme: durdur

    setCalan(i)
    let adres
    try {
      adres = await api.seslendir(metin)
      const ses = new Audio(adres)
      sesRef.current = ses
      const bitir = () => {
        setCalan((s) => (s === i ? null : s))
        URL.revokeObjectURL(adres)
      }
      ses.onended = bitir
      ses.onerror = bitir
      await ses.play()
    } catch {
      // Seslendirme bir ikram; başarısızlığı sohbete hata baloncuğu olarak
      // düşürmek gereksiz gürültü olurdu. Düğme eski hâline döner, metin durur.
      if (adres) URL.revokeObjectURL(adres)
      setCalan((s) => (s === i ? null : s))
    }
  }

  async function kaydaBasla() {
    try {
      await kayit.basla()
    } catch {
      // Mikrofon izni reddedildi ya da cihaz yok. Kullanıcı ne yaptığını
      // biliyor; ona ne yapması gerektiğini söylemek yeter.
      setMesajlar((m) => [...m, {
        kim: 'hata',
        metin: 'Mikrofona erişemedim. Tarayıcı ayarlarından bu siteye mikrofon izni vermelisin.',
      }])
    }
  }

  async function sesiGonder() {
    const kayitli = await kayit.bitir()
    if (!kayitli) return

    // Döküm sunucudan geliyor, yani baloncuk önce "yer tutucu" olarak çiziliyor
    // ve dönüşte metinle DEĞİŞTİRİLİYOR. Yer tutucuyu sırasıyla değil kendi
    // işaretiyle buluyoruz: arada başka bir baloncuk düşerse sıra kayar.
    const isaret = Symbol('ses')
    setMesajlar((m) => [
      ...m,
      { kim: 'ben', metin: '🎤 Ses gönderiliyor…', an: new Date().toISOString(), isaret },
    ])
    setBekliyor(true)
    try {
      const y = await api.sohbetSes(kayitli.blob, kayitli.dosyaAdi)
      // Dökümü göstermek şart: asistan yanlış anladığında sebebi görünsün.
      setMesajlar((m) => [
        ...m.map((x) => (x.isaret === isaret ? { ...x, metin: `🎤 ${y.transcript}` } : x)),
        { kim: 'prism', metin: y.response, an: new Date().toISOString() },
      ])
    } catch (err) {
      // Yer tutucuyu bırakmıyoruz: "gönderiliyor…" diye asılı kalan bir
      // baloncuk, hatanın kendisinden daha çok kafa karıştırır.
      setMesajlar((m) => [
        ...m.filter((x) => x.isaret !== isaret),
        { kim: 'hata', metin: err.message || 'Ses gönderilemedi' },
      ])
    } finally {
      setBekliyor(false)
    }
  }

  async function gonder(e) {
    e?.preventDefault()
    const metin = girdi.trim()
    if ((!metin && !gorsel) || bekliyor) return

    const simdi = new Date().toISOString()
    const benim = {
      kim: 'ben',
      metin: gorsel ? `🖼 ${metin || 'Görsel'}` : metin,
      gorselAdi: gorsel?.name,
      an: simdi,
    }
    setMesajlar((m) => [...m, benim])
    setGirdi('')
    const gonderilecekGorsel = gorsel
    setGorsel(null)
    setBekliyor(true)

    try {
      const y = gonderilecekGorsel
        ? await api.sohbetGorsel(gonderilecekGorsel, metin)
        : await api.sohbet(metin)
      setMesajlar((m) => [...m, {
        kim: 'prism', metin: y.response, aciklama: y.description, an: new Date().toISOString(),
      }])
    } catch (err) {
      setMesajlar((m) => [...m, { kim: 'hata', metin: err.message || 'Gönderilemedi' }])
    } finally {
      setBekliyor(false)
    }
  }

  let oncekiGun = null

  return (
    <div className="flex flex-col" style={{ minHeight: 'calc(100dvh - 12rem)' }}>
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={20} style={{ color: 'var(--accent-bright)' }} />
        <h1 className="text-2xl font-display font-bold text-white">PRISM</h1>
      </div>

      {saltOkunur && (
        <p className="glass-card p-3 mb-4 text-xs" style={{ color: 'var(--text-soft)' }}>
          Sohbet her zaman <strong className="text-white">{kullanici?.ad}</strong> adına çalışır —
          yazdığın şey senin hatırlatıcına, notuna, harcamana gider.
        </p>
      )}

      <div className="flex-1 space-y-3 mb-4">
        {mesajlar.map((m, i) => {
          const gun = m.an ? gunEtiketi(m.an) : null
          const ayrac = gun && gun !== oncekiGun ? gun : null
          if (gun) oncekiGun = gun

          return (
            <div key={i}>
              {ayrac && (
                <p className="text-center text-[11px] my-4" style={{ color: 'var(--text-faint)' }}>
                  {ayrac}
                </p>
              )}
              <div className={`flex ${m.kim === 'ben' ? 'justify-end' : 'justify-start'}`}>
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
                    <p className="text-[11px] mt-1 opacity-70">{m.gorselAdi}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    {m.kim === 'prism' && (
                      <button
                        type="button"
                        onClick={() => seslendir(i, m.metin)}
                        className="flex items-center gap-1 text-[11px] transition-opacity hover:opacity-100"
                        style={{ color: 'var(--text-faint)', opacity: calan === i ? 1 : 0.6 }}
                        aria-label={calan === i ? 'Durdur' : 'Sesli dinle'}
                      >
                        {calan === i ? <Square size={11} /> : <Volume2 size={11} />}
                        {calan === i ? 'Durdur' : 'Dinle'}
                      </button>
                    )}
                    {m.an && (
                      <span
                        className="text-[10px] ml-auto"
                        style={{ color: m.kim === 'ben' ? 'rgba(255,255,255,0.5)' : 'var(--text-faint)' }}
                      >
                        {saatEtiketi(m.an)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )
        })}

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

        {kayit.kayitta ? (
          // Kayıt sırasında yazı alanı yerine bu şerit: iptal solda, gönder
          // sağda — yanlışlıkla gönderme ile vazgeçme birbirine karışmasın.
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={kayit.iptal}
              className="px-3 py-2.5 rounded-xl flex-shrink-0"
              style={{ background: 'var(--surface)', color: '#fca5a5', border: '1px solid var(--border)' }}
              aria-label="Kaydı sil"
            >
              <Trash2 size={18} />
            </button>
            <div className="flex-1 flex items-center gap-2 text-sm" style={{ color: 'var(--text-soft)' }}>
              <span
                className="w-2 h-2 rounded-full animate-pulse-glow flex-shrink-0"
                style={{ background: '#f87171' }}
              />
              Dinliyorum… {sureBicimi(kayit.saniye)}
            </div>
            <button type="button" onClick={sesiGonder} className="btn-primary flex-shrink-0">
              <Send size={16} />
            </button>
          </div>
        ) : (
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
            {/* Mikrofon yalnız yazı yokken görünür: yazarken ses düğmesi
                göndermenin yerini alıp yanlış tuşa bastırıyordu. */}
            {sesKaydiDestekli() && !girdi.trim() && !gorsel ? (
              <button
                type="button"
                onClick={kaydaBasla}
                disabled={bekliyor}
                title="Sesli mesaj"
                className="px-3 rounded-xl flex-shrink-0"
                style={{ background: 'var(--surface)', color: 'var(--text-soft)', border: '1px solid var(--border)' }}
              >
                <Mic size={18} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={bekliyor || (!girdi.trim() && !gorsel)}
                className="btn-primary flex-shrink-0"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        )}
      </form>
    </div>
  )
}
