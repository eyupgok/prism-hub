/**
 * Kim giriş yaptı, kime bakılıyor.
 *
 * İki ayrı kavram var, karıştırılmamalı:
 *  - `kullanici`  → giriş yapan kişi. Yazma her zaman ona gider, değişmez.
 *  - `bakilan`    → panelde şu an kimin verisine bakılıyor. Üstteki geçişle değişir.
 *
 * İkisi farklıysa `saltOkunur` true olur ve arayüz bütün ekleme/düzenleme/silme
 * düğmelerini gizler. Sunucu zaten 403 döndürüyor; buradaki gizleme, kullanıcının
 * yapamayacağı bir şeyi denemesini önlemek için.
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { setBakilanKisi } from './api/client'

const Ctx = createContext(null)

export function KullaniciProvider({ auth, children }) {
  const kullanici = auth?.kullanici ?? null
  const kullanicilar = auth?.kullanicilar?.length ? auth.kullanicilar : kullanici ? [kullanici] : []

  const [bakilanId, setBakilanIdState] = useState(null)
  const aktifId = bakilanId ?? kullanici?.id ?? null

  const setBakilanId = useCallback((id) => {
    // Kendine dönerken parametreyi tamamen kaldır: istekler sade kalsın
    setBakilanKisi(id === kullanici?.id ? null : id)
    setBakilanIdState(id)
  }, [kullanici?.id])

  const deger = useMemo(() => {
    const bakilan = kullanicilar.find((k) => k.id === aktifId) ?? kullanici
    return {
      kullanici,
      kullanicilar,
      bakilan,
      setBakilanId,
      saltOkunur: Boolean(kullanici && bakilan && bakilan.id !== kullanici.id),
    }
  }, [kullanici, kullanicilar, aktifId, setBakilanId])

  return <Ctx.Provider value={deger}>{children}</Ctx.Provider>
}

export function useKullanici() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useKullanici, KullaniciProvider içinde çağrılmalı')
  return v
}
