package com.eyup.prism.data

import android.content.Context

/**
 * Bildirim dinleyicisinin canlılık kaydı.
 *
 * "İzin verildi mi" ile "servis gerçekten bağlı mı" aynı şey DEĞİL. Android, izin
 * listesinde işaretli görünen bir dinleyiciyi uygulama güncellendiğinde ya da servisi
 * öldürdüğünde geri bağlamayabiliyor; ayarlar ekranı yeşil görünürken hiçbir bildirim
 * ulaşmıyor. Teşhis için iki ayrı sinyal tutuluyor:
 *
 *  - `connected`  → servis şu an sisteme bağlı mı (onListenerConnected/Disconnected)
 *  - `lastSeenAt` → dinleyici EN SON ne zaman herhangi bir bildirim gördü
 *
 * İkincisi asıl belirleyici olan: boşsa sorun banka uygulamasında ya da paket
 * seçiminde değil, dinleyicinin kendisinde demektir.
 *
 * DataStore yerine SharedPreferences: arayüzün çizim anında senkron okuyabilmesi gerek.
 */
object ListenerState {

    private const val PREFS = "prism_listener_state"
    private const val KEY_CONNECTED = "connected"
    private const val KEY_CONNECTED_AT = "connected_at"
    private const val KEY_LAST_SEEN_AT = "last_seen_at"

    /** Her bildirimde diske yazmanın anlamı yok — bu aralıkta bir kez yeter */
    private const val SEEN_WRITE_THROTTLE_MS = 5_000L

    @Volatile
    private var lastSeenWrite = 0L

    data class Status(
        val connected: Boolean,
        val connectedAt: Long,
        val lastSeenAt: Long,
    )

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun read(context: Context): Status = prefs(context).let {
        Status(
            connected = it.getBoolean(KEY_CONNECTED, false),
            connectedAt = it.getLong(KEY_CONNECTED_AT, 0L),
            lastSeenAt = it.getLong(KEY_LAST_SEEN_AT, 0L),
        )
    }

    fun markConnected(context: Context) {
        prefs(context).edit()
            .putBoolean(KEY_CONNECTED, true)
            .putLong(KEY_CONNECTED_AT, System.currentTimeMillis())
            .apply()
    }

    fun markDisconnected(context: Context) {
        prefs(context).edit().putBoolean(KEY_CONNECTED, false).apply()
    }

    /**
     * Bir bildirim görüldü. Hangi uygulamadan geldiği burada önemli değil — dinleyicinin
     * nabzı olduğunu göstermesi önemli.
     */
    fun markSaw(context: Context) {
        val now = System.currentTimeMillis()
        if (now - lastSeenWrite < SEEN_WRITE_THROTTLE_MS) return
        lastSeenWrite = now
        prefs(context).edit().putLong(KEY_LAST_SEEN_AT, now).apply()
    }
}
