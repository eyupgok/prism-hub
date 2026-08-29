package com.eyup.prism

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.service.CaptureSyncWorker
import com.eyup.prism.service.ListenerWatchdogWorker
import com.eyup.prism.service.hasNotificationAccess
import com.eyup.prism.service.requestListenerRebind
import com.eyup.prism.ui.screens.SettingsScreen
import com.eyup.prism.ui.theme.PRISMTheme

/**
 * PRISM Köprü — tek ekranlı sensör uygulaması.
 *
 * Bu uygulamanın gündelik hayatta AÇILMASI GEREKMEZ. Tek işi banka
 * bildirimlerini yakalayıp sunucuya iletmek; o iş arka planda, uygulama
 * kapalıyken de yürüyor. Ekran yalnız kurulum ve teşhis için var:
 * sunucu adresi, anahtar, hangi uygulamalar dinlenecek, dinleyici ayakta mı.
 *
 * Hatırlatıcı / not / harcama / sohbet ekranları buradan kaldırıldı — hepsini
 * web paneli daha iyi yapıyor ve panel telefonda ana ekrana eklenmiş bir
 * uygulama olarak duruyor. Bildirim OKUMAK ise web'de mümkün değil
 * (`NotificationListenerService` sistem yetkisi), o yüzden bu uygulama duruyor.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            PrismApp()
        }
    }
}

@Composable
fun PrismApp() {
    val context = LocalContext.current
    val store = remember { SettingsStore(context.applicationContext) }
    val settings by store.settings.collectAsState(initial = null)

    LaunchedEffect(settings) {
        val s = settings ?: return@LaunchedEffect
        ApiClient.configure(s.baseUrl, s.apiKey)
        // Çevrimdışıyken biriken bildirimler varsa uygulama açılınca gönderilmeye çalışılır
        if (s.isConfigured) CaptureSyncWorker.scheduleNow(context.applicationContext)
        // İzin duruyor ama servis kopmuş olabilir (güncelleme sonrası ve süreç
        // öldürüldükten sonra sık oluyor). Bağlıysa bu çağrı hiçbir şey yapmaz.
        if (s.captureEnabled && hasNotificationAccess(context)) {
            requestListenerRebind(context.applicationContext)
            // Uygulama kapalıyken de kontrol eden bekçi. Asıl işi burada değil:
            // süreç öldürüldüğünde onu geri doğurup dinleyiciyi bağlatmak.
            ListenerWatchdogWorker.schedule(context.applicationContext)
        } else {
            ListenerWatchdogWorker.cancel(context.applicationContext)
        }
    }

    PRISMTheme {
        Scaffold(containerColor = MaterialTheme.colorScheme.background) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                SettingsScreen(store)
            }
        }
    }
}
