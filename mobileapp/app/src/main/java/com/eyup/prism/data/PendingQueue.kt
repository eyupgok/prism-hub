package com.eyup.prism.data

import android.content.Context
import android.util.Log
import com.eyup.prism.data.api.NotificationIngest
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File

private const val TAG = "PrismQueue"
private const val FILE_NAME = "pending_notifications.json"

/** Kuyrukta en fazla kaç bildirim tutulur — taşarsa en eskiler düşer */
private const val MAX_ITEMS = 300

/** Bu kadar günden eski bildirimler gönderilmez; geçmişe harcama yazmanın anlamı yok */
private const val MAX_AGE_DAYS = 7L

/**
 * Kuyruk kaydı. `queuedAt` sadece yerelde eskime hesabı için tutulur — sunucuya
 * gönderilen gövde `ingest` alanıdır, bu sarmalayıcı değil.
 */
data class QueuedItem(
    val ingest: NotificationIngest,
    val queuedAt: Long = System.currentTimeMillis(),
) {
    /** Kuyrukta aynı bildirimi iki kez tutmamak için basit anahtar */
    val key: String
        get() = "${ingest.packageName}|${ingest.text.hashCode()}|${ingest.postedAt.orEmpty()}"
}

/**
 * Telefon çevrimdışıyken yakalanan bildirimleri diske yazar; bağlantı gelince
 * `CaptureSyncWorker` buradan okuyup gönderir.
 *
 * Neden Room değil de düz dosya: kuyrukta bir avuç kayıt olur, sorgu yapılmaz,
 * sadece "hepsini oku / hepsini yaz" gerekir. Veritabanı katmanı bu iş için fazlaydı.
 *
 * Not: bildirim metni gönderilene kadar diskte durur — uygulamanın kendi özel
 * alanında, başka uygulamaların erişemeyeceği yerde. Şifre/OTP metinleri kuyruğa
 * hiç girmez, dinleyici onları daha önce eler.
 */
object PendingQueue {

    private val gson = Gson()
    private val lock = Any()

    private fun file(context: Context) = File(context.filesDir, FILE_NAME)

    private fun readAll(context: Context): List<QueuedItem> = synchronized(lock) {
        val f = file(context)
        if (!f.exists()) return emptyList()
        try {
            val type = object : TypeToken<List<QueuedItem>>() {}.type
            gson.fromJson<List<QueuedItem>>(f.readText(), type) ?: emptyList()
        } catch (e: Exception) {
            // Dosya bozulduysa kuyruğu sıfırla — birkaç harcama kaybı, sonsuza kadar
            // çöken bir kuyruğa yeğdir
            Log.w(TAG, "Kuyruk okunamadı, sıfırlanıyor: ${e.javaClass.simpleName}")
            f.delete()
            emptyList()
        }
    }

    private fun write(context: Context, items: List<QueuedItem>) = synchronized(lock) {
        runCatching { file(context).writeText(gson.toJson(items)) }
            .onFailure { Log.w(TAG, "Kuyruk yazılamadı: ${it.javaClass.simpleName}") }
    }

    fun add(context: Context, ingest: NotificationIngest) {
        val item = QueuedItem(ingest)
        val items = readAll(context).filterNot { it.key == item.key } + item
        write(context, items.takeLast(MAX_ITEMS))
        Log.i(TAG, "Kuyruğa alındı (${items.size} bekliyor)")
    }

    /** Eskimiş kayıtları atar, gönderilmeye hazır olanları döner */
    fun readFresh(context: Context, nowMillis: Long = System.currentTimeMillis()): List<QueuedItem> {
        val all = readAll(context)
        val cutoff = nowMillis - MAX_AGE_DAYS * 24 * 3600 * 1000
        val fresh = all.filter { it.queuedAt >= cutoff }
        if (fresh.size != all.size) {
            Log.i(TAG, "${all.size - fresh.size} eskimiş kayıt atıldı")
            write(context, fresh)
        }
        return fresh
    }

    /** Gönderimi biten kayıtları kuyruktan düşürür */
    fun remove(context: Context, done: Collection<QueuedItem>) {
        if (done.isEmpty()) return
        val keys = done.map { it.key }.toSet()
        write(context, readAll(context).filterNot { it.key in keys })
    }

    fun size(context: Context): Int = readAll(context).size
}
