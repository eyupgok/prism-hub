package com.eyup.prism.data

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File

private const val TAG = "PrismLog"
private const val FILE_NAME = "capture_log.json"
private const val MAX_ENTRIES = 40

/** Dinlenmeyen bir uygulamanın kaydı bu süre içinde yenilenmez */
private const val IGNORED_REFRESH_MS = 60 * 60 * 1000L

/** Bir bildirime ne olduğunun kaydı. Bildirimin METNİ saklanmaz — sadece sonuç. */
data class CaptureLogEntry(
    val packageName: String,
    val appLabel: String,
    val at: Long,
    val outcome: String,
    val detail: String = "",
)

/** Sonuç kodları — arayüzdeki etiket ve renk buna göre seçilir */
object Outcome {
    const val SAVED = "saved"        // sunucu harcama olarak kaydetti
    const val SKIPPED = "skipped"    // sunucuya ulaştı ama harcama sayılmadı (çift kayıt dahil)
    const val QUEUED = "queued"      // gönderilemedi, kuyruğa alındı
    const val IGNORED = "ignored"    // bu uygulama dinlenmiyor
    const val SECRET = "secret"      // şifre/doğrulama mesajı, telefondan hiç çıkmadı
    const val SELF_TEST = "self_test" // "Test bildirimi gönder" düğmesinin bildirimi
    const val ERROR = "error"
}

/**
 * Son yakalanan bildirimlerin sonuç kaydı.
 *
 * Amacı teşhis: bir harcama görünmediğinde sebebinin bildirimin hiç ulaşmaması mı,
 * uygulamanın seçili olmaması mı, yoksa sunucunun "harcama değil" demesi mi olduğunu
 * telefonu bilgisayara bağlamadan görebilmek.
 *
 * Dinlenmeyen uygulamalar için paket başına yalnızca EN SON kayıt tutulur — yoksa
 * gelen her mesaj bildirimi listeyi doldurup asıl aradığın satırı gömerdi.
 */
object CaptureLog {

    private val gson = Gson()
    private val lock = Any()

    private fun file(context: Context) = File(context.filesDir, FILE_NAME)

    fun read(context: Context): List<CaptureLogEntry> = synchronized(lock) {
        val f = file(context)
        if (!f.exists()) return emptyList()
        try {
            val type = object : TypeToken<List<CaptureLogEntry>>() {}.type
            gson.fromJson<List<CaptureLogEntry>>(f.readText(), type) ?: emptyList()
        } catch (e: Exception) {
            Log.w(TAG, "Kayıt okunamadı, sıfırlanıyor: ${e.javaClass.simpleName}")
            f.delete()
            emptyList()
        }
    }

    private fun write(context: Context, entries: List<CaptureLogEntry>) = synchronized(lock) {
        runCatching { file(context).writeText(gson.toJson(entries)) }
            .onFailure { Log.w(TAG, "Kayıt yazılamadı: ${it.javaClass.simpleName}") }
    }

    fun add(context: Context, packageName: String, outcome: String, detail: String = "") {
        val now = System.currentTimeMillis()
        val existing = read(context)

        if (outcome == Outcome.IGNORED) {
            // Dinlenmeyen uygulamalar için paket başına tek satır tutulur. Üstelik son
            // kayıt tazeyse dosyaya hiç dokunulmaz — mesajlaşma uygulamalarından saatte
            // onlarca bildirim gelebiliyor, her biri için disk yazmanın anlamı yok.
            val last = existing.lastOrNull {
                it.packageName == packageName && it.outcome == Outcome.IGNORED
            }
            if (last != null && now - last.at < IGNORED_REFRESH_MS) return
        }

        val entry = CaptureLogEntry(
            packageName = packageName,
            appLabel = appLabel(context, packageName),
            at = now,
            outcome = outcome,
            detail = detail,
        )
        val kept = existing.filterNot {
            outcome == Outcome.IGNORED && it.outcome == Outcome.IGNORED && it.packageName == packageName
        }
        write(context, (kept + entry).takeLast(MAX_ENTRIES))
    }

    fun clear(context: Context) = write(context, emptyList())

    private fun appLabel(context: Context, packageName: String): String = runCatching {
        val pm = context.packageManager
        pm.getApplicationLabel(pm.getApplicationInfo(packageName, 0)).toString()
    }.getOrDefault(packageName)
}
