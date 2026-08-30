import { useEffect, useRef, useState } from 'react'

/**
 * Tarayıcıdan sesli mesaj kaydı.
 *
 * Telegram'da sesle konuşabiliyorduk, panelde konuşamıyorduk; asistanın en
 * rahat kullanıldığı an (eller meşgulken) panelde kapalıydı. Kayıt burada
 * alınıp `/api/chat/voice`'a gidiyor, döküm sunucuda Whisper ile çıkıyor —
 * yani panelin kendi ses tanıması yok, Telegram'la aynı motor.
 */

// Açık unutulmuş mikrofona karşı üst sınır. Sunucunun 25 MB sınırından çok
// önce devreye giriyor; asıl derdi dosya boyutu değil, kullanıcının kaydı
// başlatıp konuşmayı bıraktığını fark etmemesi.
export const AZAMI_SANIYE = 120

// ⚠️ Tarayıcılar aynı biçimi üretmiyor: Chrome webm/opus, Safari (iPhone
// dahil) mp4/aac. Groq Whisper ikisini de kabul ediyor ama DOSYA ADININ
// UZANTISINA bakıyor — yanlış uzantı "unsupported file type" demek.
const BICIMLER = [
  { tur: 'audio/webm;codecs=opus', ad: 'kayit.webm' },
  { tur: 'audio/webm', ad: 'kayit.webm' },
  { tur: 'audio/mp4', ad: 'kayit.m4a' },
  { tur: 'audio/ogg;codecs=opus', ad: 'kayit.ogg' },
]

function bicimSec() {
  for (const b of BICIMLER) {
    if (MediaRecorder.isTypeSupported?.(b.tur)) return b
  }
  // Safari bir dönem isTypeSupported'ı hiç uygulamadı; biçimi ona bırakıp
  // kendi varsayılanını (mp4) kabul ediyoruz.
  return { tur: '', ad: 'kayit.m4a' }
}

/**
 * Kayıt mümkün mü?
 *
 * `navigator.mediaDevices` GÜVENLİ BAĞLAM ister — panel HTTPS'te yayında ama
 * yerel ağdan düz http ile açılırsa bu tanımsız gelir. O durumda düğmeyi hiç
 * çizmemek, basınca patlamasından iyi.
 */
export const sesKaydiDestekli = () =>
  typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia

export function useSesKaydi() {
  const [kayitta, setKayitta] = useState(false)
  const [saniye, setSaniye] = useState(0)
  const kaydediciRef = useRef(null)
  const cozRef = useRef(null)

  // ⚠️ Sayfadan çıkarken mikrofonu MUTLAKA bırak. Bırakılmazsa sekmedeki
  // kayıt göstergesi yanık kalır — kullanıcı dinlendiğini sanar.
  useEffect(() => () => {
    kaydediciRef.current?.stream?.getTracks().forEach((t) => t.stop())
  }, [])

  useEffect(() => {
    if (!kayitta) return
    const sayac = setInterval(() => setSaniye((s) => s + 1), 1000)
    return () => clearInterval(sayac)
  }, [kayitta])

  async function basla() {
    const akis = await navigator.mediaDevices.getUserMedia({ audio: true })
    const bicim = bicimSec()
    const kaydedici = new MediaRecorder(akis, bicim.tur ? { mimeType: bicim.tur } : undefined)
    const parcalar = []

    kaydedici.ondataavailable = (e) => e.data.size && parcalar.push(e.data)
    kaydedici.onstop = () => {
      akis.getTracks().forEach((t) => t.stop())
      setKayitta(false)
      const coz = cozRef.current
      cozRef.current = null
      const blob = parcalar.length
        ? new Blob(parcalar, { type: kaydedici.mimeType || bicim.tur || 'audio/mp4' })
        : null
      // coz yoksa kayıt iptal edilmiş demektir; parçalar sessizce düşer.
      coz?.(blob ? { blob, dosyaAdi: bicim.ad } : null)
    }

    kaydediciRef.current = kaydedici
    setSaniye(0)
    kaydedici.start()
    setKayitta(true)
  }

  /** Kaydı bitirir ve dosyayı döner. İptalde ve boş kayıtta `null`. */
  function bitir() {
    const k = kaydediciRef.current
    if (!k || k.state === 'inactive') return Promise.resolve(null)
    return new Promise((coz) => {
      cozRef.current = coz
      k.stop()
    })
  }

  function iptal() {
    cozRef.current = null
    const k = kaydediciRef.current
    if (k && k.state !== 'inactive') k.stop()
  }

  return { kayitta, saniye, basla, bitir, iptal }
}

export function sureBicimi(saniye) {
  const dk = Math.floor(saniye / 60)
  const sn = saniye % 60
  return `${dk}:${String(sn).padStart(2, '0')}`
}
