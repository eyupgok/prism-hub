package com.eyup.prism.service

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.service.notification.NotificationListenerService
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

/**
 * Yakalamanın uçtan uca çalışıp çalışmadığını sınamak için uygulamanın kendine
 * bildirim göndermesi.
 *
 * Neden gerekli: gerçek bir banka bildirimini beklemek teşhisi saatlere yayıyor ve
 * bir şey gelmediğinde sebebini söylemiyor — dinleyici mi ölü, paket mi seçili değil,
 * metin mi okunamadı? Bu düğmeye basıldığında zincirin tamamı üç saniyede sınanıyor:
 * bildirim düşer → dinleyici görür → "Son Yakalananlar"a satır düşer.
 *
 * Dinleyici normalde kendi paketimizin bildirimlerini yok sayar; sadece bu etiketi
 * taşıyan bildirime izin verilir.
 */
const val SELF_TEST_TAG = "prism-selftest"

private const val CHANNEL_ID = "prism_selftest"
private const val NOTIFICATION_ID = 4242

/** Android 13+ bildirim göndermek için ayrı izin istiyor */
fun canPostNotifications(context: Context): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
        PackageManager.PERMISSION_GRANTED

/** @return izin yoksa false — çağıran tarafın izni istemesi gerekir */
fun sendSelfTestNotification(context: Context): Boolean {
    if (!canPostNotifications(context)) return false

    val manager = context.getSystemService(NotificationManager::class.java) ?: return false
    manager.createNotificationChannel(
        NotificationChannel(CHANNEL_ID, "PRISM testi", NotificationManager.IMPORTANCE_LOW)
    )

    val notification = NotificationCompat.Builder(context, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_dialog_info)
        .setContentTitle("PRISM test bildirimi")
        .setContentText("Dinleyici bunu görebiliyorsa bildirim yakalama çalışıyor demektir.")
        .setAutoCancel(true)
        .setTimeoutAfter(30_000)
        .build()

    return runCatching {
        NotificationManagerCompat.from(context).notify(SELF_TEST_TAG, NOTIFICATION_ID, notification)
        true
    }.getOrDefault(false)
}

/**
 * Sisteme "dinleyicimi yeniden bağla" der.
 *
 * Uygulama güncellendikten sonra izin listede işaretli kalır ama servis bağlanmamış
 * olabiliyor — izni kapatıp açmanın yazılımla yapılan karşılığı bu. İzin hiç yoksa
 * ya da servis zaten bağlıysa sessizce hiçbir şey olmaz.
 */
fun requestListenerRebind(context: Context) {
    runCatching {
        NotificationListenerService.requestRebind(
            ComponentName(context.applicationContext, ExpenseNotificationListener::class.java)
        )
    }
}
