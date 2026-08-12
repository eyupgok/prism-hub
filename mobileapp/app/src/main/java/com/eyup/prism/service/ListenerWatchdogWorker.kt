package com.eyup.prism.service

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.eyup.prism.data.ListenerState
import com.eyup.prism.data.SettingsStore
import kotlinx.coroutines.flow.first
import java.util.concurrent.TimeUnit

private const val TAG = "PrismWatchdog"

/**
 * Ölen bildirim dinleyicisini geri getirir.
 *
 * Neden gerekli: son kullanılanlar ekranındaki "hepsini kapat" düğmesi uygulamanın
 * sürecini komple öldürüyor (Spotify'ın müziği de aynı düğmeyle susuyor — normal
 * "geri" ile çıkmakla aynı şey değil). Sistem dinleyiciyi çoğu zaman kendiliğinden
 * geri bağlar, ama Xiaomi/HyperOS gibi katmanlarda bağlamayı reddedip bir daha
 * denemiyor: izin ekranı yeşil kalır, hiçbir bildirim gelmez.
 *
 * Bu iş WorkManager'da tutulduğu için süreç ölse de sistemin sırasında kalıyor.
 * Sıradaki tur geldiğinde süreç yeniden doğuyor ve buradan `requestRebind()`
 * çağrılıyor — yani uygulamayı elle açmaya gerek kalmadan dinleme geri geliyor.
 *
 * Sınırı da açık olsun: uygulama tam anlamıyla "durduruldu" durumuna sokulursa
 * (Ayarlar'dan zorla durdur, bazı üreticilerin agresif temizliği) bu iş de iptal
 * edilir. O durumda uygulamayı bir kez açmak şart — açılışta [MainActivity] hem
 * yeniden bağlanmayı ister hem bu işi tekrar kurar.
 */
class ListenerWatchdogWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val ctx = applicationContext
        val settings = SettingsStore(ctx).settings.first()
        if (!settings.captureEnabled || !hasNotificationAccess(ctx)) return Result.success()

        // Her tur tek satır: "bekçi hâlâ tur atıyor mu?" sorusunun logcat'teki cevabı.
        // Sessiz kalırsa iş sıradan düşmüş demektir — sebebi genelde zorla durdurmadır.
        Log.i(TAG, "Bekçi turu — dinleyici bağlı=${ExpenseNotificationListener.isBound}")

        if (ExpenseNotificationListener.isBound) return Result.success()

        // Diskteki kayıt "bağlı" diyor olabilir; süreç öldürüldüğünde
        // onListenerDisconnected hiç çağrılmıyor. Önce doğrusunu yaz — ayarlar
        // ekranındaki yeşil nokta yalan söylemesin — sonra geri bağlanmayı iste.
        ListenerState.markDisconnected(ctx)
        Log.i(TAG, "Dinleyici bağlı değil — yeniden bağlanma isteniyor")
        requestListenerRebind(ctx)
        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "prism-listener-watchdog"

        /**
         * WorkManager'ın izin verdiği en kısa süre 15 dakika. 30 dakika, yapılan iş
         * (iki okuma + bir binder çağrısı) yanında pil açısından yok hükmünde;
         * karşılığında en kötü ihtimalle yarım saatlik bir kör nokta kalıyor.
         */
        private const val INTERVAL_MINUTES = 30L

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<ListenerWatchdogWorker>(
                INTERVAL_MINUTES, TimeUnit.MINUTES
            ).build()

            // UPDATE (KEEP değil): aralığı sonradan değiştirirsem zaten kurulu iş de
            // yenilensin, yoksa eski aralıkla sonsuza kadar devam ederdi.
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME, ExistingPeriodicWorkPolicy.UPDATE, request
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
        }
    }
}
