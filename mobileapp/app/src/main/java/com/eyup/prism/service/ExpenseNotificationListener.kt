package com.eyup.prism.service

import android.app.Notification
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
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
        Log.i(TAG, "Bildirim dinleyici bağlandı")
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val notification = sbn?.notification ?: return
        val packageName = sbn.packageName ?: return

        if (packageName == applicationContext.packageName) return
        if (sbn.isOngoing) return
        // Grup başlığı bildirimleri ("3 yeni mesaj") içerik taşımaz
        if (notification.flags and Notification.FLAG_GROUP_SUMMARY != 0) return

        val extras = notification.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty().trim()
        // Uzun metin varsa onu tercih et — kısaltılmış hâlinde tutar eksik kalabiliyor
        val body = listOfNotNull(
            extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString(),
            extras.getCharSequence(Notification.EXTRA_TEXT)?.toString(),
        ).maxByOrNull { it.length }.orEmpty().trim()

        if (body.isEmpty()) return
        if (looksLikeSecret(body) || looksLikeSecret(title)) {
            Log.d(TAG, "Şifre mesajı atlandı ($packageName)")
            return
        }

        val postedAt = isoFromMillis(sbn.postTime)

        scope.launch {
            try {
                val settings = store.settings.first()
                if (!settings.captureEnabled) return@launch
                if (packageName !in settings.watchedPackages) return@launch
                if (!settings.isConfigured) {
                    Log.w(TAG, "Sunucu ayarlı değil, bildirim gönderilemedi")
                    return@launch
                }

                // Aynı bildirimin tekrarını gönderme (dakika hassasiyetinde)
                val key = "$packageName|${body.hashCode()}|${postedAt.take(16)}"
                if (!recentKeys.add(key)) return@launch
                trimRecentKeys()

                ApiClient.configure(settings.baseUrl, settings.apiKey)
                val result = ApiClient.api().ingestNotification(
                    NotificationIngest(
                        packageName = packageName,
                        title = title,
                        text = body,
                        postedAt = postedAt,
                        source = "notification",
                    )
                )
                Log.i(TAG, "$packageName → kaydedildi=${result.recorded} (${result.reason})")
            } catch (e: Exception) {
                // Metni loglama — sadece hata türü
                Log.w(TAG, "Bildirim gönderilemedi ($packageName): ${e.javaClass.simpleName}")
            }
        }
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

    private companion object {
        val ISO_LOCAL: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
    }
}
