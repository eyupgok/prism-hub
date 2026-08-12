package com.eyup.prism.service

import android.app.Notification
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.eyup.prism.data.CaptureLog
import com.eyup.prism.data.ListenerState
import com.eyup.prism.data.Outcome
import com.eyup.prism.data.PendingQueue
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.NotificationIngest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Collections

private const val TAG = "PrismCapture"

/** Tek kullanımlık şifre / doğrulama kodu mesajları — telefondan hiç çıkmaz. */
private val SECRET_PATTERN = Regex(
    "(tek\\s*kullanım|otp|onay\\s*kodu|doğrulama\\s*kodu|güvenlik\\s*kodu|işlem\\s*şifre" +
        "|sms\\s*şifre|aktivasyon\\s*kodu|paylaşmayın|kimseyle\\s*paylaş)",
    RegexOption.IGNORE_CASE,
)

fun looksLikeSecret(text: String): Boolean = SECRET_PATTERN.containsMatchIn(text)

/** Bildirim erişimi izni verilmiş mi? */
fun hasNotificationAccess(context: Context): Boolean {
    val flat = Settings.Secure.getString(
        context.contentResolver, "enabled_notification_listeners"
    ) ?: return false
    val target = ComponentName(context, ExpenseNotificationListener::class.java)
    return flat.split(":").any {
        val parsed = ComponentName.unflattenFromString(it)
        parsed != null && parsed.packageName == target.packageName
    }
}

/** Bildirim erişimi ayar ekranını açar (izin uygulama içinden verilemez, sistem ekranından verilir) */
fun notificationAccessIntent(): Intent =
    Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

/**
 * Kalıcı kayıttaki "bağlı" bilgisini gerçekle karşılaştırır.
 *
 * Süreç öldürüldüğünde (son kullanılanlardan "hepsini kapat", pil yöneticisi)
 * `onListenerDisconnected` HİÇ çağrılmıyor — dosyada "bağlı" yazılı kalıyor ve
 * ayarlar ekranı yeşil görünürken hiçbir bildirim gelmiyor. Süreç içindeki canlı
 * bayrak yeniden doğuşta false başladığı için doğruyu o söylüyor.
 */
fun reconcileListenerState(context: Context) {
    val bound = ExpenseNotificationListener.isBound
    val stored = ListenerState.read(context).connected
    if (bound == stored) return
    if (bound) ListenerState.markConnected(context) else ListenerState.markDisconnected(context)
}

/**
 * Seçilen bankacılık uygulamalarının bildirimlerini yakalayıp sunucuya yollar.
 *
 * Tasarım kararları:
 * - Sadece kullanıcının Ayarlar'dan işaretlediği paketler okunur; gerisi hiç ele alınmaz.
 * - Şifre/doğrulama kodu içeren metinler sunucuya gönderilmez (sunucuda ikinci kez elenir).
 * - Bildirim metni cihazda saklanmaz, sadece aynı bildirimi iki kez yollamamak için
 *   bellekte kısa bir anahtar listesi tutulur (uygulama kapanınca gider; sunucu da ayrıca eler).
 * - Log'lara metin basılmaz — yalnız paket adı ve sonuç.
 */
class ExpenseNotificationListener : NotificationListenerService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val store by lazy { SettingsStore(applicationContext) }

    /** Son gönderilenler — Android aynı bildirimi güncellendikçe tekrar bildiriyor */
    private val recentKeys = Collections.synchronizedSet(LinkedHashSet<String>())

    override fun onListenerConnected() {
        isBound = true
        ListenerState.markConnected(applicationContext)
        Log.i(TAG, "Bildirim dinleyici bağlandı")
        catchUpMissed()
    }

    override fun onListenerDisconnected() {
        isBound = false
        ListenerState.markDisconnected(applicationContext)
        Log.w(TAG, "Bildirim dinleyici koptu — yeniden bağlanma isteniyor")
        // Sistem servisi kapattığında kendiliğinden geri gelmeyebiliyor; kendimiz isteyelim.
        requestListenerRebind(applicationContext)
    }

    override fun onDestroy() {
        isBound = false
        scope.cancel()
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null) return

        // Dinleyicinin nabzı: hangi uygulamadan geldiği önemli değil, bir şey GÖRÜYOR
        // olması önemli. Teşhiste ilk bakılacak yer burası.
        ListenerState.markSaw(applicationContext)

        handle(sbn, fromCatchUp = false)
    }

    /**
     * Dinleyici ölüyken düşen bildirimleri, geri bağlanınca panelden toplar.
     *
     * Süreç öldürüldüğünde (son kullanılanlardaki "hepsini kapat" düğmesi) o aralıkta
     * gelen bildirimler `onNotificationPosted`'a hiç uğramaz — ama çoğu banka bildirimi
     * bildirim panelinde durmaya devam ediyor. Geri bağlanır bağlanmaz paneldeki listeyi
     * okuyup "en son bir şey gördüğüm andan sonrasını" işliyoruz; böylece kapalı geçen
     * süre tamamen kayıp olmuyor.
     *
     * Aynı bildirimi ikinci kez göndermek risksiz: sunucu `source_hash` (paket + metin +
     * dakika) ile tanıyıp "zaten işlenmiş" diyor.
     */
    private fun catchUpMissed() {
        val lastSeen = ListenerState.read(applicationContext).lastSeenAt
        // Hiç bildirim görmemişsek panelde ne varsa "geçmiş" sayılır — ilk kurulumda
        // haftalık birikmiş bildirimleri harcamaya çevirmenin anlamı yok.
        if (lastSeen == 0L) return

        val cutoff = maxOf(lastSeen, System.currentTimeMillis() - CATCH_UP_MAX_AGE_MS)
        val active = runCatching { activeNotifications }.getOrNull() ?: return
        val missed = active.filter { it.postTime > cutoff }
        if (missed.isEmpty()) return

        Log.i(TAG, "Kopukluk sonrası panelde ${missed.size} bildirim bulundu, işleniyor")
        missed.forEach { handle(it, fromCatchUp = true) }
        ListenerState.markSaw(applicationContext)
    }

    private fun handle(sbn: StatusBarNotification, fromCatchUp: Boolean) {
        val notification = sbn.notification ?: return
        val packageName = sbn.packageName ?: return

        val isSelfTest = packageName == applicationContext.packageName && sbn.tag == SELF_TEST_TAG
        if (packageName == applicationContext.packageName && !isSelfTest) return

        val title = notification.extras
            ?.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty().trim()
        val body = extractText(notification)

        // Bu iki eleme eskiden burada sessizce yapılıyordu. Artık aşağıya taşındı:
        // SEÇİLİ bir uygulamanın bildirimi elenirse sebebi kayda düşsün, yoksa
        // "bildirim geldi ama hiçbir şey olmadı" durumunun izahı kalmıyor.
        val isOngoing = sbn.isOngoing
        val isGroupSummary = notification.flags and Notification.FLAG_GROUP_SUMMARY != 0

        val postedAt = isoFromMillis(sbn.postTime)
        val isSecret = looksLikeSecret(body) || looksLikeSecret(title)

        scope.launch {
            try {
                val settings = store.settings.first()
                if (!settings.captureEnabled) return@launch

                if (isSelfTest) {
                    CaptureLog.add(
                        applicationContext,
                        packageName,
                        Outcome.SELF_TEST,
                        "Dinleyici bildirimi gördü — yakalama çalışıyor",
                    )
                    return@launch
                }

                if (packageName !in settings.watchedPackages) {
                    // Sonradan toplarken panelde ne varsa geliyor — seçili olmayan her
                    // uygulama için satır açmak listeyi anlamsızca doldurur.
                    if (!fromCatchUp) {
                        CaptureLog.add(applicationContext, packageName, Outcome.IGNORED, "Dinlenmiyor")
                    }
                    return@launch
                }

                if (isOngoing || isGroupSummary) {
                    CaptureLog.add(
                        applicationContext,
                        packageName,
                        Outcome.SKIPPED,
                        if (isOngoing) "Kalıcı bildirim, atlandı" else "Grup başlığı, atlandı",
                    )
                    return@launch
                }

                if (body.isEmpty()) {
                    CaptureLog.add(
                        applicationContext,
                        packageName,
                        Outcome.ERROR,
                        "Bildirim metni okunamadı",
                    )
                    return@launch
                }

                // Şifre/doğrulama mesajları telefondan hiç çıkmaz
                if (isSecret) {
                    Log.d(TAG, "Şifre mesajı atlandı ($packageName)")
                    CaptureLog.add(applicationContext, packageName, Outcome.SECRET, "Şifre mesajı")
                    return@launch
                }

                if (!settings.isConfigured) {
                    Log.w(TAG, "Sunucu ayarlı değil, bildirim gönderilemedi")
                    CaptureLog.add(applicationContext, packageName, Outcome.ERROR, "Sunucu ayarlı değil")
                    return@launch
                }

                // Aynı bildirimin tekrarını gönderme (dakika hassasiyetinde)
                val key = "$packageName|${body.hashCode()}|${postedAt.take(16)}"
                if (!recentKeys.add(key)) return@launch
                trimRecentKeys()

                val ingest = NotificationIngest(
                    packageName = packageName,
                    title = title,
                    text = body,
                    postedAt = postedAt,
                    source = "notification",
                )

                // Kopukluk sonrası toplananları ayırt edebilelim: "bu harcamayı ben
                // düşerken değil, geri geldiğimde gördüm" bilgisi teşhiste işe yarıyor.
                val late = if (fromCatchUp) " · sonradan yakalandı" else ""

                try {
                    ApiClient.configure(settings.baseUrl, settings.apiKey)
                    val result = ApiClient.api().ingestNotification(ingest)
                    Log.i(TAG, "$packageName → kaydedildi=${result.recorded} (${result.reason})")
                    CaptureLog.add(
                        applicationContext,
                        packageName,
                        if (result.recorded) Outcome.SAVED else Outcome.SKIPPED,
                        (result.expense?.let { "${it.amount} ₺ · ${it.category}" } ?: result.reason) + late,
                    )
                } catch (e: Exception) {
                    // Ağ yoksa veya sunucu ulaşılamazsa kaybetme — kuyruğa al, sonra gönder.
                    // postedAt bildirimle birlikte saklandığı için harcama doğru zamana yazılır.
                    Log.w(TAG, "Gönderilemedi ($packageName): ${e.javaClass.simpleName} → kuyruğa alındı")
                    PendingQueue.add(applicationContext, ingest)
                    CaptureSyncWorker.schedule(applicationContext)
                    CaptureLog.add(applicationContext, packageName, Outcome.QUEUED, "Gönderilemedi, kuyrukta")
                }
            } catch (e: Exception) {
                Log.w(TAG, "Bildirim işlenemedi ($packageName): ${e.javaClass.simpleName}")
                CaptureLog.add(applicationContext, packageName, Outcome.ERROR, e.javaClass.simpleName)
            }
        }
    }

    /**
     * Bildirim metnini çıkarır.
     *
     * Tek bir alana güvenilemiyor: kısaltılmış `EXTRA_TEXT`te tutar eksik kalabiliyor,
     * bazı bankalar metni satır listesi (InboxStyle) olarak koyuyor. Hepsini toplayıp
     * en uzun olanı seçmek pratikte en doğru sonucu veriyor.
     */
    private fun extractText(notification: Notification): String {
        val extras = notification.extras ?: return ""
        val candidates = mutableListOf<String?>(
            extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString(),
            extras.getCharSequence(Notification.EXTRA_TEXT)?.toString(),
            extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
                ?.joinToString("\n") { it.toString() },
            extras.getCharSequence(Notification.EXTRA_SUMMARY_TEXT)?.toString(),
            notification.tickerText?.toString(),
        )
        return candidates
            .mapNotNull { it?.trim() }
            .filter { it.isNotEmpty() }
            .maxByOrNull { it.length }
            .orEmpty()
    }

    private fun trimRecentKeys() {
        synchronized(recentKeys) {
            while (recentKeys.size > 200) {
                val oldest = recentKeys.firstOrNull() ?: break
                recentKeys.remove(oldest)
            }
        }
    }

    private fun isoFromMillis(millis: Long): String =
        ISO_LOCAL.withZone(ZoneId.systemDefault()).format(Instant.ofEpochMilli(millis))

    companion object {
        /**
         * Servis şu an sisteme bağlı mı — SÜREÇ İÇİ gerçek.
         *
         * Diskteki [ListenerState] bu konuda yalan söyleyebiliyor: süreç öldürüldüğünde
         * `onListenerDisconnected` çağrılmadan gidiyor, dosyada "bağlı" yazılı kalıyor.
         * Süreç yeniden doğduğunda bu bayrak false başlar; doğrusu budur.
         */
        @Volatile
        var isBound: Boolean = false
            private set

        private val ISO_LOCAL: DateTimeFormatter =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

        /** Geri bağlanınca bildirim panelinde en fazla bu kadar geriye bakılır */
        private const val CATCH_UP_MAX_AGE_MS = 24L * 60 * 60 * 1000
    }
}
