package com.eyup.prism.service

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.eyup.prism.data.CaptureLog
import com.eyup.prism.data.Outcome
import com.eyup.prism.data.PendingQueue
import com.eyup.prism.data.QueuedItem
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.api.ApiClient
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
import java.io.IOException
import java.util.concurrent.TimeUnit

private const val TAG = "PrismSync"
private const val WORK_NAME = "prism-capture-sync"

/**
 * Çevrimdışıyken kuyruğa alınan bildirimleri gönderir.
 *
 * WorkManager kullanmamızın sebebi: iş, uygulama kapalıyken ve telefon yeniden
 * başladıktan sonra da hatırlanmalı, ayrıca "internet gelince çalış" koşulunu
 * sistemin kendisi yönetmeli. Kendi zamanlayıcımızı yazsak pil optimizasyonu
 * bunu ilk fırsatta öldürürdü.
 */
class CaptureSyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val ctx = applicationContext
        val queued = PendingQueue.readFresh(ctx)
        if (queued.isEmpty()) return Result.success()

        val settings = SettingsStore(ctx).settings.first()
        if (!settings.isConfigured) {
            Log.w(TAG, "Sunucu ayarlı değil — kuyruk bekletiliyor (${queued.size})")
            return Result.success()  // Ayar girilince yeniden denenecek, burada tekrar tekrar uğraşma
        }
        ApiClient.configure(settings.baseUrl, settings.apiKey)

        val done = mutableListOf<QueuedItem>()
        var networkProblem = false

        for (item in queued) {
            try {
                val result = ApiClient.api().ingestNotification(item.ingest)
                Log.i(TAG, "${item.ingest.packageName} → kaydedildi=${result.recorded}")
                CaptureLog.add(
                    ctx,
                    item.ingest.packageName,
                    if (result.recorded) Outcome.SAVED else Outcome.SKIPPED,
                    result.expense?.let { "${it.amount} ₺ · ${it.category}" } ?: result.reason,
                )
                done += item
            } catch (e: IOException) {
                // Ağ yok / kesildi — kalanları bir dahaki sefere bırak
                networkProblem = true
                break
            } catch (e: HttpException) {
                if (e.code() in RETRYABLE_CODES) {
                    networkProblem = true
                    break
                }
                // 400/422 gibi hatalar tekrar denemekle düzelmez — kuyruğu tıkamasın
                Log.w(TAG, "Kalıcı hata (HTTP ${e.code()}), kayıt atılıyor")
                CaptureLog.add(ctx, item.ingest.packageName, Outcome.ERROR, "Sunucu HTTP ${e.code()}")
                done += item
            } catch (e: Exception) {
                Log.w(TAG, "Beklenmeyen hata: ${e.javaClass.simpleName}, kayıt atılıyor")
                done += item
            }
        }

        PendingQueue.remove(ctx, done)
        val remaining = PendingQueue.size(ctx)
        Log.i(TAG, "${done.size} gönderildi, $remaining bekliyor")

        return if (networkProblem && remaining > 0) Result.retry() else Result.success()
    }

    companion object {
        /** Geçici sorunlar — tekrar denemeye değer */
        private val RETRYABLE_CODES = setOf(401, 403, 408, 425, 429, 500, 502, 503, 504)

        /**
         * Kuyruğu boşaltmayı planlar. Aynı isimli iş zaten varsa yenisi eklenmez
         * (KEEP) — her bildirimde yeni iş kurup sırayı şişirmesin.
         */
        fun schedule(context: Context) {
            val request = OneTimeWorkRequestBuilder<CaptureSyncWorker>()
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context)
                .enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request)
        }

        /** Uygulama açılışında: bekleyen varsa hemen dene (KEEP yerine REPLACE) */
        fun scheduleNow(context: Context) {
            if (PendingQueue.size(context) == 0) return
            val request = OneTimeWorkRequestBuilder<CaptureSyncWorker>()
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context)
                .enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.REPLACE, request)
        }
    }
}
