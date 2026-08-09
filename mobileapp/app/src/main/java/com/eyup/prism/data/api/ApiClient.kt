package com.eyup.prism.data.api

import com.google.gson.JsonParser
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit

/**
 * Retrofit istemcisini ayarlara göre kurar. Ayarlar değişince yeniden oluşturulur.
 * Tüm isteklere X-API-Key header'ı eklenir.
 */
object ApiClient {

    @Volatile private var currentBaseUrl: String = ""
    @Volatile private var currentApiKey: String = ""
    @Volatile private var instance: PrismApi? = null

    fun configure(baseUrl: String, apiKey: String) {
        var normalized = baseUrl.trim().trimEnd('/')
        if (normalized.isBlank()) {
            instance = null
            currentBaseUrl = ""
            return
        }
        if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
            normalized = "https://$normalized"
        }
        val key = apiKey.trim()
        if (normalized == currentBaseUrl && key == currentApiKey && instance != null) return

        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .addInterceptor { chain ->
                    val builder = chain.request().newBuilder()
                    if (key.isNotBlank()) builder.header("X-API-Key", key)
                    chain.proceed(builder.build())
                }
                .build()

            instance = Retrofit.Builder()
                .baseUrl("$normalized/")
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(PrismApi::class.java)
            currentBaseUrl = normalized
            currentApiKey = key
        } catch (_: IllegalArgumentException) {
            // Geçersiz URL — istemci kurulmaz, api() çağrısı anlaşılır hata verir
            instance = null
            currentBaseUrl = ""
        }
    }

    fun api(): PrismApi = instance
        ?: throw IllegalStateException("Sunucu ayarları eksik. Ayarlar sekmesinden URL ve API anahtarını gir.")
}

/** İstisnayı kullanıcıya gösterilebilir Türkçe mesaja çevirir */
fun describeError(e: Throwable): String = when (e) {
    is HttpException -> {
        val detail = try {
            e.response()?.errorBody()?.string()?.let { body ->
                JsonParser.parseString(body).asJsonObject.get("detail")?.asString
            }
        } catch (_: Exception) {
            null
        }
        detail ?: "Sunucu hatası (HTTP ${e.code()})"
    }
    is UnknownHostException -> "Sunucuya ulaşılamadı — URL'i ve internet bağlantını kontrol et"
    is ConnectException -> "Bağlantı kurulamadı — sunucu çalışıyor mu?"
    is SocketTimeoutException -> "İstek zaman aşımına uğradı"
    is IllegalStateException -> e.message ?: "Ayarlar eksik"
    else -> e.message ?: "Bilinmeyen hata"
}
