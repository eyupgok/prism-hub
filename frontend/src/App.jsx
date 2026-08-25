import { useCallback, useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import BottomNav from './components/BottomNav'
import Dashboard from './pages/Dashboard'
import Reminders from './pages/Reminders'
import Notes from './pages/Notes'
import Expenses from './pages/Expenses'
import Settings from './pages/Settings'
import Sohbet from './pages/Sohbet'
import Özel sayfa from './pages/Özel sayfa'
import Login from './pages/Login'
import KisiSeridi from './components/KisiSeridi'
import { KullaniciProvider, useKullanici } from './kullanici'
import { api, setBakilanKisi, UNAUTHORIZED_EVENT } from './api/client'

const PAGES = {
  dashboard: Dashboard,
  reminders: Reminders,
  notes: Notes,
  expenses: Expenses,
  sohbet: Sohbet,
  settings: Settings,
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  // null = oturum durumu henüz bilinmiyor (ilk kontrol sürüyor)
  const [auth, setAuth] = useState(null)

  const checkAuth = useCallback(async () => {
    try {
      setAuth(await api.me())
    } catch {
      // Sunucuya ulaşılamıyorsa giriş ekranını göster — orada anlaşılır bir hata verilir
      setAuth({ authenticated: false, login_required: true, login_enabled: true })
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // Girişten sonra konumu tazele: hava durumu kişinin EN SON girdiği yere göre
  // gösterilsin. İzin verilmezse ya da tarayıcı desteklemezse sessizce geçilir —
  // o zaman kullanıcının kayıtlı son konumu, o da yoksa env'deki varsayılan
  // (Elazığ) kullanılır. Konum API'si yalnız HTTPS ve localhost'ta çalışır;
  // sunucu Caddy ile HTTPS olduğu için orada sorun yok.
  useEffect(() => {
    if (!auth?.authenticated || !navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        api.konumBildir(coords.latitude, coords.longitude)
          .then(checkAuth)      // şehir adı güncellensin
          .catch(() => {})      // konum kaydedilemedi — panel yine de çalışır
      },
      () => {},                 // izin yok / alınamadı — sessizce devam
      { timeout: 8000, maximumAge: 5 * 60 * 1000 },
    )
  }, [auth?.authenticated, checkAuth])

  // Oturum ortada düşerse (çerez süresi dolduysa) giriş ekranına dön
  useEffect(() => {
    const onUnauthorized = () => setAuth((a) => ({ ...a, authenticated: false }))
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  if (auth === null) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-purple-600 border-t-transparent animate-spin" />
      </div>
    )
  }

  if (auth.login_required && !auth.authenticated) {
    // Çıkışta/oturum düşünce "kime bakılıyor" seçimi de sıfırlanmalı, yoksa
    // bir sonraki giriş başkasının verisine bakar hâlde açılır.
    setBakilanKisi(null)
    return <Login onSuccess={checkAuth} />
  }

  return (
    <KullaniciProvider auth={auth}>
      <Kabuk page={page} setPage={setPage} />
    </KullaniciProvider>
  )
}

/**
 * Kabuk, bağlamın İÇİNDE duruyor — çünkü sayfaya verilecek `key` için
 * "kime bakılıyor" bilgisine ihtiyacı var.
 */
function Kabuk({ page, setPage }) {
  const { bakilan } = useKullanici()
  const Page = PAGES[page] || Dashboard

  // Özel sayfa kabuğun DIŞINDA: kendi teması ve tam ekran kurgusu var, kenar
  // çubuğuyla alt gezinmenin arasına sıkışırsa bütün etkisi gidiyor.
  if (page === 'özel sayfa') return <Özel sayfa onClose={() => setPage('dashboard')} />

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Sidebar active={page} onNavigate={setPage} />
      <main className="md:pl-64 pb-20 md:pb-0 min-h-screen">
        <KisiSeridi />
        <div className="max-w-5xl mx-auto p-4 md:p-6 lg:p-8">
          {/* key = bakılan kişi: geçiş yapılınca sayfa baştan kurulur ve verisini
              yeniden çeker. Sayfalar veriyi `useEffect(..., [])` ile bir kez
              çekiyor; key olmadan etiketler değişiyor ama içerik eski kişide
              kalıyordu — panelde Zeynep'in verisi "Eyüp'ün paneli" başlığıyla
              görünüyordu. */}
          <Page key={bakilan?.id ?? 'ben'} onNavigate={setPage} />
        </div>
      </main>
      <BottomNav active={page} onNavigate={setPage} />
    </div>
  )
}
