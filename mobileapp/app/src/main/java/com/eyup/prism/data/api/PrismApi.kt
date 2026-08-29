package com.eyup.prism.data.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/**
 * Sunucunun bu uygulamaya açık iki ucu.
 *
 * ⚠️ Uygulama bir SENSÖR: tek işi banka bildirimlerini sunucuya iletmek.
 * Hatırlatıcı/not/harcama/sohbet uçları buradan kaldırıldı — onları web
 * paneli kullanıyor ve panel aynı sunucuya kendi oturum çereziyle gidiyor.
 */
interface PrismApi {
    /** Ayarlar ekranındaki "Bağlantıyı test et" — adres ve anahtar doğru mu */
    @GET("health")
    suspend fun health(): HealthResponse

    /** Yakalanan bildirim. Harcama değilse 200 + recorded=false döner. */
    @POST("api/expenses/ingest")
    suspend fun ingestNotification(@Body body: NotificationIngest): IngestResult
}
